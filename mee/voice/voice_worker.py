"""MEE voice worker — runs SpeechBrain/torch in a SEPARATE process.

Why this exists (2026-10-17):
    On this Jetson AGX Orin host, loading the SpeechBrain/torch voice runtime
    and the MediaPipe vision runtime in the *same* process segfaults (native
    C-runtime collision — verified: each works alone, the combined load dumps
    core). To keep both camera and mic recognition alive, the voice runtime
    runs here, in its own process, and the EmotionEngine talks to it over
    stdin/stdout (JSON lines). The vision runtime stays in the engine process.

Protocol (one JSON object per line, newline-delimited):
    client -> worker:
        {"type": "ping"}
        {"type": "infer", "audio_b64": "<base64 float32 little-endian>", "sample_rate": 16000}
    worker -> client:
        {"type": "ready", "backend": "speechbrain|wav2vec|tensorrt|none"}
        {"type": "pong"}
        {"type": "result", "emotion": ..., "confidence": ..., "scores": {...}}
        {"type": "error", "message": ...}

The worker NEVER imports mee.vision / mediapipe, so the two native runtimes
never coexist in one address space.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import warnings

# Silence the noisy native-runtime warnings (mediapipe is NOT imported here, but
# torch/speechbrain still print cpuinfo/absl/oneDNN noise) before heavy imports.
warnings.filterwarnings("ignore")


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    # Import numpy + the voice stack HERE (worker process only).
    import numpy as np

    from mee.voice.processor import VoiceProcessor
    from mee.voice.emotion_model import EmotionModel

    # 2026-10-17: honor the canonical models/ tree. The engine exports
    # MEE_VOICE_MODEL_PATH (default <repo>/models/voice) into this worker's
    # environment; fall back to VoiceProcessor's own default if unset.
    model_path = os.environ.get("MEE_VOICE_MODEL_PATH") or None
    if model_path:
        vp = VoiceProcessor(emotion_model=EmotionModel(model_path=model_path))
    else:
        vp = VoiceProcessor()
    backend = getattr(getattr(vp, "_emotion", None), "_backend", None) or "unknown"
    _emit({"type": "ready", "backend": backend, "available": bool(vp.available)})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as exc:  # noqa: BLE001
            _emit({"type": "error", "message": f"bad request: {exc}"})
            continue

        rtype = req.get("type")
        if rtype == "ping":
            _emit({"type": "pong"})
        elif rtype == "infer":
            try:
                b64 = req.get("audio_b64", "")
                if not b64:
                    _emit({"type": "result",
                           "emotion": "neutral", "confidence": 0.0, "scores": {}})
                    continue
                raw = base64.b64decode(b64)
                audio = np.frombuffer(raw, dtype=np.float32).copy()
                sr = int(req.get("sample_rate", 16000))
                result = vp.process(audio, sr)
                _emit({
                    "type": "result",
                    "emotion": result.get("emotion", "neutral"),
                    "confidence": result.get("confidence", 0.0),
                    "scores": result.get("scores", {}),
                })
            except Exception as exc:  # noqa: BLE001
                _emit({"type": "error", "message": f"infer failed: {exc}"})
        elif rtype == "shutdown":
            break
        else:
            _emit({"type": "error", "message": f"unknown request type {rtype!r}"})

    _emit({"type": "bye"})


if __name__ == "__main__":
    main()
