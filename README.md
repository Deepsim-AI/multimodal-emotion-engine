# Multimodal Emotion Engine (MEE) v0.1.0

An independent, locally-deployable AI capability that estimates a user's affective state from multiple input modalities: visual (facial expression) and voice (acoustic characteristics).

## Overview

MEE processes webcam video and microphone audio to produce:

- Per-modality emotion estimates with confidence scores
- Multimodal fused emotion estimate
- Temporal state trend (increasing / stable / decreasing)
- Structured JSON output

## Key Principles

- **Local-first** — core inference runs on-device; no cloud dependency
- **Commercially safe** — all model weights use commercial-safe licenses (MIT/Apache-2.0)
- **Edge-optimized** — designed for Jetson AGX Orin and similar edge devices
- **Modular** — vision and voice models are interchangeable behind a stable API
- **Independent** — does not depend on the AI Companion Book Chapter 15

## Install

### Core package (includes basic face detection)
```bash
pip install multimodal-emotion-engine
```

### With optional feature sets
```bash
# Full vision + voice pipeline
pip install multimodal-emotion-engine[vision]
pip install multimodal-emotion-engine[voice]

# Demo UI (Streamlit-based)
pip install multimodal-emotion-engine[demo]

# Development/testing
pip install multimodal-emotion-engine[dev]
```

### Jetson AGX Orin deployment
See [`docs/JETSON_DEPLOYMENT.md`](docs/JETSON_DEPLOYMENT.md) for complete deployment guide including TensorRT optimization.

## Usage Examples

### Basic usage
```python
from mee.api.engine import EmotionEngine, MEEConfig

engine = EmotionEngine(MEEConfig(
    face_confidence_threshold=0.3,
    trend_window=30,
    trend_min_samples=5,
))

result = engine.process(video_frame=frame, audio=audio_array)
# result["face"]["emotion"], result["voice"]["emotion"]
# result["overall"]["emotion"], result["trend"]
```

### Detection frequency (TASK_MEE_013)
On CPU-only hosts (e.g. Jetson Orin without a detection GPU path), face detection
is the dominant cost (~1 s/face vs ~50 ms for emotion). Set
`detect_every_n_frames` to run detection once every N vision passes and reuse
its result (bounding box + landmarks) for alignment and emotion on the
intermediate passes:

```python
engine = EmotionEngine(MEEConfig(
    detect_every_n_frames=4,  # detect on pass 1, reuse on passes 2-4, re-detect on 5
))
```

- `1` (default) is fully backward-compatible: detection runs on every pass.
- The cached result is automatically invalidated when the frame's array object
  or shape changes, and `VisionProcessor.process(frame, force_detection=True)`
  forces an immediate re-detection.
- Not thread-safe: use one `VisionProcessor` per thread (or `n=1`).

### Headless JSON output for evaluation
```bash
python -m demo.emotion_demo --headless  # Outputs JSON results
```

## Architecture

```
multimodal-emotion-engine/
├── mee/              # Core Python package
│   ├── vision/       # Facial expression pipeline
│   │   ├── detector.py        # Stage 1: Face detection (retina-face)
│   │   ├── alignment.py       # Stage 2: Face alignment/cropping (face-alignment)
│   │   └── emotion_model.py   # Stage 3: Expression classification (EmotiEffLib)
│   ├── voice/        # Voice emotion pipeline
│   ├── fusion/       # Multimodal fusion
│   ├── state/        # Temporal state tracking
│   └── api/          # Public API (EmotionEngine)
├── demo/             # Demonstration UI
├── tests/            # Unit and integration tests
└── docs/             # Architecture and deployment docs
```

## Status

**✅ v0.1.0 — All tasks complete** (G1→G5 for all MEE_001 through MEE_011)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for detailed design documentation.

## Limitations & Disclaimer

- **Emotion estimates are probabilistic**, not psychological assessments. They represent statistical inferences from facial expressions and vocal characteristics — they do not "read true emotion."
- **Single-session state only:** `EmotionHistory` resets per `EmotionEngine` instance (session restart = history reset). No cross-session persistence.
- **Window-based trend estimation:** The dominant-emotion approach with confidence delta comparison has known limitations:
  - Very short interactions (<3 samples) → "unstable" by design
  - Rapid emotion changes may not be captured accurately
  - Confidence thresholds are configurable but require tuning for specific use cases

## Third-Party Components & Licensing

See [`docs/THIRD_PARTY_LICENSES.md`](docs/THIRD_PARTY_LICENSES.md) for the complete inventory of third-party components used by MEE, including their licenses and commercial-use status.

### Summary

| Category | License | Commercial Use? |
|----------|---------|-----------------|
| Core package code | Apache-2.0 ✅ | Yes |
| Vision pipeline (retina-face, face-alignment, EmotiEffLib) | MIT/Apache-2.0 ✅ | Yes |
| Voice pipeline (SpeechBrain RavNet) | Apache-2.0 ✅ | Yes |
| OpenCV, librosa, streamlit, etc. | Various open-source ✅ | Yes |

All model weights used in production are released under commercial-safe licenses by their respective authors. AGPL/NC models were explicitly excluded from the MEE design.

---
*MEE remains an independent capability, not tied to the AI Companion book or any specific robot.*
*“Affective-state estimation” — never “reads true emotion.”*
