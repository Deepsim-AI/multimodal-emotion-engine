"""In-process client for the out-of-process MEE voice worker.

See ``mee/voice/voice_worker.py`` for the worker and the rationale (native
runtime collision between the SpeechBrain/torch voice stack and the MediaPipe
vision stack on this Jetson host).

The client owns a long-lived ``python3 -m mee.voice.voice_worker`` subprocess
and speaks newline-delimited JSON over its stdin/stdout. The engine uses this
instead of importing ``VoiceProcessor`` directly, so the voice runtime never
shares an address space with the vision runtime.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
from typing import Optional


class VoiceWorkerClient:
    """Spawns + drives the out-of-process voice worker.

    Thread-safe: a single lock serializes request/response exchanges (the
    worker is a single-threaded stdin loop). If the worker process is not
    (or can't be) started, :meth:`available` is False and :meth:`infer`
    returns a degraded dict instead of raising — matching the engine's
    existing graceful-degradation contract.
    """

    def __init__(self, module: str = "mee.voice.voice_worker",
                 python: Optional[str] = None,
                 cwd: Optional[str] = None,
                 ready_timeout: float = 60.0):
        self._module = module
        self._python = python or sys.executable
        self._cwd = cwd
        self._ready_timeout = ready_timeout
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._ready = False
        self._backend = "none"
        self._started = False  # guarded by _lock

    # ---- lifecycle -------------------------------------------------------
    def _ensure_started(self) -> bool:
        """Start the worker on first use (lazy). Returns True if ready."""
        if self._ready:
            return True
        with self._lock:
            if self._ready or self._started:
                return self._ready
            self._started = True
            try:
                env = dict(os.environ)
                # The worker imports the `mee` package — make sure the repo
                # root is on PYTHONPATH regardless of the caller's cwd.
                repo = os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))))
                if repo and repo not in env.get("PYTHONPATH", ""):
                    env["PYTHONPATH"] = repo + (os.pathsep + env["PYTHONPATH"]
                                                if env.get("PYTHONPATH") else "")
                self._proc = subprocess.Popen(
                    [self._python, "-m", self._module],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    cwd=self._cwd, env=env, text=True, bufsize=1,
                )
            except Exception:
                self._proc = None
                return False
            # Wait for the {"type":"ready"} line (model load can take ~30-60s).
            ready = self._read_ready()
            self._ready = ready
            return ready

    def _read_ready(self) -> bool:
        """Consume worker lines until ready/error/EOF (bounded by timeout)."""
        import select
        proc = self._proc
        if proc is None or proc.stdout is None:
            return False
        deadline = self._ready_timeout
        while True:
            if select.select([proc.stdout], [], [], 1.0)[0]:
                line = proc.stdout.readline()
                if not line:
                    return False
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                if msg.get("type") == "ready":
                    self._backend = msg.get("backend", "unknown")
                    return bool(msg.get("available", True))
                if msg.get("type") == "error":
                    return False
            # If the process died while loading, stop waiting.
            if proc.poll() is not None:
                return False
            # Coarse wall-clock guard (select has no total timeout on this path).
            # We rely on the 1s select slices; cap total iterations.
            # (kept simple: break after ~ready_timeout seconds of slices)
            # -- use a counter as the deadline guard --
            self._iter_guard = getattr(self, "_iter_guard", 0) + 1
            if self._iter_guard > max(1, int(self._ready_timeout)):
                return False

    # ---- inference -------------------------------------------------------
    def available(self) -> bool:
        return self._ensure_started()

    @property
    def backend(self) -> str:
        return self._backend

    def infer(self, audio, sample_rate: int = 16000) -> dict:
        """Run one voice inference. Returns a result dict (never raises)."""
        degraded = {"emotion": "neutral", "confidence": 0.0, "scores": {}}
        import numpy as np
        if audio is None or len(audio) == 0:
            return degraded
        if not self._ensure_started() or self._proc is None:
            return degraded
        if isinstance(audio, list):
            audio = np.array(audio, dtype=np.float32)
        b64 = base64.b64encode(np.ascontiguousarray(audio).tobytes()).decode()
        req = {"type": "infer", "audio_b64": b64, "sample_rate": int(sample_rate)}
        with self._lock:
            try:
                self._proc.stdin.write(json.dumps(req) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
                if not line:
                    return degraded
                msg = json.loads(line.strip())
            except Exception:
                return degraded
        if msg.get("type") == "result":
            return {
                "emotion": msg.get("emotion", "neutral"),
                "confidence": msg.get("confidence", 0.0),
                "scores": msg.get("scores", {}),
            }
        return degraded

    def shutdown(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
            self._ready = False
        if proc is None:
            return
        try:
            proc.stdin.write(json.dumps({"type": "shutdown"}) + "\n")
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
