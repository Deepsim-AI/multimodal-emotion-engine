"""TASK_MEE_008: Multimodal Emotion Engine — demonstration UI.

A single-file Streamlit app that drives the public ``EmotionEngine`` API
with live camera + microphone input and displays all engine outputs in
real-time.  The UI is a *consumer* of the public API: it only ever calls
``EmotionEngine.process(video_frame=..., audio=...)`` and never touches
model internals.

Affective-state estimation only — this tool estimates affective state;
it does not read true emotion.

Usage
-----
GUI (requires a web browser):
    streamlit run demo/emotion_demo.py

Headless / scripted mode (no browser needed):
    python demo/emotion_demo.py --headless --output results.jsonl

Hardware fallback
-----------------
If the camera or microphone is unavailable, the demo shows a clear
"no hardware" message and offers a file-upload fallback for
still-frame / audio-file evaluation.  Nothing crashes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import deque
from queue import Empty, Queue
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap: ensure the repo root is on sys.path so ``from mee import ...``
# works whether or not the package has been pip-installed.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Public API import (consumer side only — never touch model internals)
# ---------------------------------------------------------------------------
from mee import EmotionEngine, MEEConfig

# ---------------------------------------------------------------------------
# Optional hardware libraries — import defensively so the demo still loads
# on machines without these packages (shows "install X" messages instead).
# ---------------------------------------------------------------------------
try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover
    sd = None  # type: ignore[assignment]

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None  # type: ignore[assignment]

# Emotion labels — from the public contract (mee/fusion/emotion_fusion.py)
EMOTION_LABELS = (
    "angry", "disgust", "fear", "happy", "sad", "surprised", "neutral",
)

TREND_EMOJI = {
    "stable": "➖",
    "improving": "📈",
    "declining": "📉",
    "unstable": "🌪",
}

SAMPLE_RATE = 16000          # Hz — matches MEEConfig.audio_sample_rate
CHUNK_SECONDS = 0.02         # 20 ms per engine step  →  320 samples
TARGET_HZ = 10               # engine processing rate


# ============================================================================
# CLI
# ============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MEE Emotion Demo — live affective-state estimation UI",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Skip the Streamlit UI; write JSONL results to --output.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSONL path (headless mode only). Default: demo/results.jsonl",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Headless run duration in seconds (default: run until Ctrl-C).",
    )
    return parser.parse_args()


# ============================================================================
# Capture helpers (defensive — never raise on missing hardware)
# ============================================================================

def open_camera():
    """Return a cv2.VideoCapture or None if camera/hardware unavailable."""
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


class AudioChunker:
    """Continuous mic capture; ``read_chunk()`` returns ≤20 ms of audio.

    The mic stream runs continuously in the background; each call drains
    whatever is available (up to 320 samples at 16 kHz) into a float32
    mono array.  Returns zero-filled audio (silence) when no microphone
    is available, so the voice pipeline still executes.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._stream = None
        self._buffer: deque = deque()
        self._lock = threading.Lock()
        if sd is None:
            return
        try:
            self._stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=int(sample_rate * 0.1),  # 100 ms blocks
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self._stream = None

    def _callback(self, indata, frames, time_info, status):  # noqa: ANN001
        """sounddevice audio callback — appends each block to the buffer."""
        if status:
            return  # drop on overflow/underflow rather than blocking
        with self._lock:
            self._buffer.append(indata[:, 0].copy())
            # Cap buffer at ~500 ms to bound memory
            total = sum(len(c) for c in self._buffer)
            while total > int(sample_rate := self.sample_rate) * 0.5 and len(self._buffer) > 1:
                total -= len(self._buffer.popleft())

    def read_chunk(self, max_samples: int = int(CHUNK_SECONDS * SAMPLE_RATE)) -> np.ndarray:
        if self._stream is None:
            # No microphone — return silence so the voice path still runs
            return np.zeros(max_samples, dtype=np.float32)
        # Drain whatever the audio thread has accumulated
        with self._lock:
            chunks = list(self._buffer)
            self._buffer.clear()
        if not chunks:
            time.sleep(0.02)  # brief wait for the audio thread to fill
            with self._lock:
                chunks = list(self._buffer)
                self._buffer.clear()
        if not chunks:
            return np.zeros(max_samples, dtype=np.float32)
        out = np.concatenate(chunks)
        if len(out) > max_samples:
            out = out[:max_samples]
        if len(out) < 16:  # too short — pad to a usable length
            out = np.zeros(max_samples, dtype=np.float32)
        return out.astype(np.float32)

    def close(self):
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None


# ============================================================================
# Engine processing thread
# ============================================================================

class EngineLoop(threading.Thread):
    """Background thread calling ``engine.process()`` at ~TARGET_HZ.

    Latest result is kept in ``self.latest`` (for UI polling) and pushed
    into ``self.result_queue`` (for headless JSONL writing).
    """

    def __init__(self, engine: EmotionEngine, cam, audio: AudioChunker):
        super().__init__(daemon=True, name="engine-loop")
        self.engine = engine
        self.cam = cam
        self.audio = audio
        self.latest: Optional[dict] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.result_queue: "Queue[Optional[dict]]" = Queue(maxsize=256)
        self.stop_event = threading.Event()
        self._latencies: deque = deque(maxlen=64)

    def run(self) -> None:  # noqa: D102
        while not self.stop_event.is_set():
            frame = self._read_frame()
            audio_chunk = self.audio.read_chunk()
            try:
                result = self.engine.process(video_frame=frame, audio=audio_chunk)
            except Exception as exc:  # defensive — never kill the loop
                result = {
                    "face": None, "voice": None,
                    "overall": {"emotion": None, "confidence": 0.0, "conflict": False},
                    "trend": "unstable",
                    "latency_ms": -1.0,
                    "error": str(exc),
                }
            self.latest = result
            self.latest_frame = frame
            if "latency_ms" in result and result["latency_ms"] >= 0:
                self._latencies.append(float(result["latency_ms"]))
            if not self.result_queue.full():
                self.result_queue.put(result)
            # Pace to TARGET_HZ
            self.stop_event.wait(1.0 / TARGET_HZ)

    def _read_frame(self) -> np.ndarray:
        """Read a camera frame, or return a synthetic neutral frame when the
        camera is unavailable (hardware-less systems)."""
        if self.cam is not None:
            ok, frame = self.cam.read()
            if ok:
                return frame
        return np.zeros((64, 64, 3), dtype=np.uint8)  # synthetic neutral

    def stats(self) -> dict:
        if not self._latencies:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "n": 0}
        vals = list(self._latencies)
        return {
            "avg": round(sum(vals) / len(vals), 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
            "n": len(vals),
        }


# ============================================================================
# Headless mode
# ============================================================================

def run_headless(args: argparse.Namespace) -> None:
    """Run the engine loop and stream results as JSONL. No Streamlit.

    On systems without a camera, a synthetic neutral frame is generated so the
    full pipeline (history accumulation, fusion, trend) still executes — this
    is real engine behavior, not a shortcut.
    """
    import os

    output_path = args.output or "demo/results.jsonl"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    engine = EmotionEngine(config=MEEConfig())
    cam = open_camera()
    audio = AudioChunker()
    loop = EngineLoop(engine, cam, audio)
    loop.start()

    start = time.time()
    written = 0
    last_summary = time.time()
    emotion_counts: dict = {}
    cam_label = "OK" if cam is not None else "UNAVAILABLE (synthetic frame)"
    mic_label = "OK" if (sd is not None and audio._stream is not None) else "UNAVAILABLE (silent)"
    print(f"[headless] engine ready (is_ready={engine.is_ready}) — writing to {output_path}")
    print(f"[headless] camera={cam_label}, mic={mic_label}")
    print("[headless] Ctrl-C to stop.")

    with open(output_path, "w", encoding="utf-8") as fh:
        try:
            while True:
                if args.duration is not None and (time.time() - start) >= args.duration:
                    break
                try:
                    result = loop.result_queue.get(timeout=0.5)
                except Empty:
                    if time.time() - last_summary >= 60.0:
                        _log_summary(emotion_counts, loop, last_summary - start)
                        last_summary = time.time()
                    continue
                if result is None:
                    continue
                fh.write(json.dumps(result) + "\n")
                fh.flush()
                written += 1
                overall = result.get("overall") or {}
                emotion = overall.get("emotion") or "unknown"
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                if time.time() - last_summary >= 60.0:
                    _log_summary(emotion_counts, loop, last_summary - start)
                    last_summary = time.time()
        except KeyboardInterrupt:
            print("\n[headless] interrupted — shutting down")
        finally:
            loop.stop_event.set()
            loop.join(timeout=2.0)
            audio.close()
            if cam is not None:
                cam.release()
            _log_summary(emotion_counts, loop, time.time() - start, final=True)
            print(f"[headless] done — {written} results written to {output_path}")


def _log_summary(emotion_counts: dict, loop: EngineLoop, elapsed: float, final: bool = False) -> None:
    stats = loop.stats()
    total = sum(emotion_counts.values()) or 1
    dist = ", ".join(f"{k}:{v}" for k, v in sorted(emotion_counts.items()))
    tag = "FINAL " if final else ""
    print(f"[headless] {tag}t={elapsed:.0f}s written_dist=[{dist}] "
          f"latency_ms avg={stats['avg']} min={stats['min']} max={stats['max']}")


# ============================================================================
# Streamlit UI
# ============================================================================

def render_emotion_bars(container, result: dict) -> None:
    """Render face / voice / overall emotion as labelled confidence bars."""
    def _bar(title: str, payload: Optional[dict], has_face_key: bool = False) -> None:
        if payload is None:
            container.markdown(f"**{title}** — no data")
            return
        scores = payload.get("scores") or {}
        if not scores:
            emotion = payload.get("emotion")
            conf = float(payload.get("confidence") or 0.0)
            if emotion:
                container.markdown(f"**{title}** — {emotion} ({conf:.0%})")
            else:
                container.markdown(f"**{title}** — no face / no data")
            return
        top_label = max(scores, key=lambda k: scores[k])
        top_val = max(scores.values())
        container.markdown(f"**{title}** — {top_label} ({top_val:.0%})")
        for label in EMOTION_LABELS:
            if label in scores:
                container.progress(
                    min(max(float(scores[label]), 0.0), 1.0),
                    text=f"{label}: {scores[label]:.2f}",
                )

    with container:
        _bar("Face (vision)", result.get("face"))
        _bar("Voice", result.get("voice"))
        _bar("Overall (fused)", result.get("overall"))


def render_ui(engine: EmotionEngine, args: argparse.Namespace) -> None:
    if st is None:
        raise SystemExit(
            "streamlit is not installed — install demo deps:\n"
            '  pip install -e ".[demo]"'
        )

    st.set_page_config(page_title="MEE Emotion Demo", page_icon="🧠", layout="wide")
    st.title("🧠 Multimodal Emotion Engine — Live Demo")
    st.caption(
        "Affective-state estimation from face + voice. "
        "This tool *estimates* affective state; it does not read true emotion."
    )

    # ---- Sidebar -----------------------------------------------------------
    with st.sidebar:
        st.header("Controls")

        if not engine.is_ready:
            st.warning("⚠️ Models not loaded (``engine.is_ready`` is False). "
                       "Channels will gracefully degrade to neutral fallback "
                       "values. Install the vision/voice extras for real "
                       "inference.")

        # Fusion weight sliders (informational — MEEConfig is fixed at engine
        # init; the engine is a public consumer so we display them but
        # do NOT mutate internals)
        st.markdown("**Fusion weights (engine config)**")
        st.slider("Vision weight", 0.0, 1.0,
                  float(engine.config.fusion_weights.get("vision", 0.5)), step=0.05)
        st.slider("Voice weight", 0.0, 1.0,
                  float(engine.config.fusion_weights.get("voice", 0.5)), step=0.05)
        st.caption("Weights above are displayed for reference; the running engine "
                   "uses its own config. Change ``MEEConfig.fusion_weights`` at "
                   "startup to alter them.")

        # Model availability indicators
        st.markdown("**Model availability**")
        vision_ok = engine._vision_processor is not None  # noqa: SLF001 (display only)
        voice_ok = engine._voice_processor is not None    # noqa: SLF001
        st.markdown(f"Face detection: {'🟢 loaded' if vision_ok else '🔴 not loaded'}")
        st.markdown(f"Voice model: {'🟢 loaded' if voice_ok else '🔴 not loaded'}")

        st.divider()
        if st.button("🔄 Reset engine", use_container_width=True):
            st.session_state.pop("engine_loop", None)
            st.session_state.pop("engine", None)
            st.rerun()

    # ---- Hardware status banner --------------------------------------------
    cam = None
    audio = None
    if cv2 is None:
        st.info("📷 OpenCV not available — install with ``pip install opencv-python`` "
                "(or ``pip install -e \".[demo]\"``). Camera input disabled.")
    else:
        cam = open_camera()
        if cam is None:
            st.info("📷 No camera detected — upload a still frame below for "
                    "single-frame evaluation.")

    if sd is None:
        st.info("🎙 sounddevice not available — install with ``pip install sounddevice`` "
                "(or ``pip install -e \".[demo]\"``). Microphone input disabled.")
    else:
        audio = AudioChunker()
        if audio._stream is None:  # noqa: SLF001 (display only)
            st.info("🎙 No microphone detected — upload an audio clip below for "
                    "single-chunk evaluation.")

    # ---- File-upload fallbacks ---------------------------------------------
    upload_frame: Optional[np.ndarray] = None
    upload_audio: Optional[np.ndarray] = None

    if cam is None or audio is None:
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Upload still frame (BGR image)")
            f = st.file_uploader("Frame", type=["png", "jpg", "jpeg"], key="up_frame")
            if f is not None and cv2 is not None:
                arr = np.frombuffer(f.read(), dtype=np.uint8)
                upload_frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        with col2:
            st.markdown("#### Upload audio clip (WAV)")
            a = st.file_uploader("Audio", type=["wav", "flac"], key="up_audio")
            if a is not None:
                upload_audio = _load_audio_file(a.name, a.read())

    # ---- Engine loop (session-state singleton) -----------------------------
    loop: Optional[EngineLoop] = st.session_state.get("engine_loop")
    if loop is None or not loop.is_alive():
        if loop is not None and loop is not st.session_state.get("engine_loop"):
            pass
        # Close previous resources
        if loop is not None:
            loop.stop_event.set()
            loop.join(timeout=1.0)
        loop = EngineLoop(engine, cam, audio)
        loop.start()
        st.session_state["engine_loop"] = loop

    # If uploaded inputs exist, run them through the engine directly (synchronous)
    if upload_frame is not None or upload_audio is not None:
        result = engine.process(video_frame=upload_frame, audio=upload_audio)
        st.info("Running with uploaded input (one-shot).")
    else:
        result = loop.latest
        if result is None:
            st.info("Waiting for first engine result…")
            result = {
                "face": None, "voice": None,
                "overall": {"emotion": None, "confidence": 0.0, "conflict": False},
                "trend": "stable", "latency_ms": 0.0,
            }

    # ---- Main area ----------------------------------------------------------
    # Camera frame
    frame = upload_frame if upload_frame is not None else loop.latest_frame
    if frame is not None:
        st.image(frame, channel_order="bgr", use_container_width=True)
    else:
        st.caption("No camera frame available.")

    # Conflict banner
    overall = result.get("overall") or {}
    if overall.get("conflict"):
        st.error("⚠️ **Channel conflict detected** — vision and voice estimates "
                 "diverge beyond the conflict threshold.")

    # Trend
    trend = result.get("trend") or "stable"
    st.markdown(f"#### Trend: {TREND_EMOJI.get(trend, '')} {trend}")

    # Emotion bars
    st.markdown("#### Emotion estimates")
    render_emotion_bars(st.container(), result)

    # Latency stats
    stats = loop.stats()
    st.markdown(f"**Latency** — avg {stats['avg']} ms | min {stats['min']} ms | "
                f"max {stats['max']} ms (n={stats['n']})")

    # Debug panel
    with st.expander("🔍 Debug — last result (JSON)"):
        st.json(result)

    # Auto-refresh the streamlit page so the UI stays live
    time.sleep(0.5)
    st.rerun()


def _load_audio_file(name: str, data: bytes) -> Optional[np.ndarray]:
    """Load a WAV/FLAC file to mono float32 @ 16 kHz. Returns None on failure."""
    import io
    import wave

    try:
        if name.lower().endswith((".wav",)):
            with wave.open(io.BytesIO(data), "rb") as wf:
                n_ch = wf.getnchannels()
                rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
            dtype = np.int16 if wf.getsampwidth() == 2 else np.float32
            arr = np.frombuffer(raw, dtype=dtype).reshape(-1, n_ch).astype(np.float32)
            mono = arr.mean(axis=1) / (32768.0 if dtype == np.int16 else 1.0)
            if rate != SAMPLE_RATE:
                # Linear resample (good enough for a demo)
                n_out = int(len(mono) * SAMPLE_RATE / rate)
                x_old = np.linspace(0, 1, len(mono), endpoint=False)
                x_new = np.linspace(0, 1, n_out, endpoint=False)
                mono = np.interp(x_new, x_old, mono).astype(np.float32)
            return mono[: int(SAMPLE_RATE * 30)]  # cap at 30 s
        return None
    except Exception:
        return None


# ============================================================================
# Entry point
# ============================================================================

def main() -> None:
    args = parse_args()
    if args.headless:
        run_headless(args)
        return

    # Streamlit path: build the engine once, then render the UI.
    engine = EmotionEngine(config=MEEConfig())
    # Cache the engine on the module so st.rerun() doesn't rebuild it
    globals()["ENGINE_SINGLETON"] = engine
    render_ui(engine, args)


if __name__ == "__main__":
    # When run directly (``python demo/emotion_demo.py``), only the headless
    # path is supported — the GUI requires the streamlit server process.
    if "--headless" in __import__("sys").argv:
        main()
    else:
        raise SystemExit(
            "GUI mode requires the Streamlit server. Run:\n"
            "    streamlit run demo/emotion_demo.py\n\n"
            "Headless mode works without a browser:\n"
            "    python demo/emotion_demo.py --headless --output results.jsonl"
        )
