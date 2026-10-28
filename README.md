# Multimodal Emotion Engine (MEE) v0.4.5

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

## License & Access

**MEE is a commercial product.** The core package (`mee/`) is distributed under the
**Deepsim Commercial Software License v1.1** (proprietary). A valid license key is
required to run inference — `pip install` gives you the code, but the engine is
locked until you activate a key.

- **Free (Community/Academic):** request a key via the License UI in the remote
demo, or email `licensing@deepsim.com`. No credit card required.
- **Paid plans (Developer, Commercial, Enterprise, OEM/Embedded):** see the
[Licensing & Plans](#licensing--plans-task_mee_019) section below for checkout links.
- **Verify a release:** every GitHub release ships with a Sigstore signature bundle
  (`.sigstore.json`) and a SHA-256 manifest. Verify with:
  ```bash
  pip install sigstore
  ./tools/verify_release.sh multimodal_emotion_engine-*.whl MEE_RELEASE_MANIFEST.json multimodal_emotion_engine-*.whl.sigstore.json
  ```

## Install

MEE is distributed as a **signed wheel from GitHub Releases** (not on PyPI).
Download the latest release assets, then install the wheel:

```bash
# 1. Download the latest release artifacts
#    (wheel, sdist, MEE_RELEASE_MANIFEST.json, MEE_INTEGRITY_HASHES.txt, .sigstore.json bundles)
git clone --depth 1 https://github.com/Deepsim-AI/multimodal-emotion-engine.git
cd multimodal-emotion-engine

# 2. Install from the signed wheel in the GitHub release (preferred)
#    Grab the .whl from https://github.com/Deepsim-AI/multimodal-emotion-engine/releases
pip install multimodal_emotion_engine-0.4.5-py3-none-any.whl

#    — or install from source (repo checkout) —
pip install .
```

### With optional feature sets
```bash
# Full vision + voice pipeline
pip install ".[vision]"
pip install ".[voice]"

# Demo UI (Streamlit-based)
pip install ".[demo]"

# Development/testing
pip install ".[dev]"
```

> **Tip:** to install a specific release, download the matching `.whl` from the
> [Releases](https://github.com/Deepsim-AI/multimodal-emotion-engine/releases) page and run
> `pip install <that-file>.whl`. The optional extras above work the same way once the
> base wheel is installed (e.g. `pip install multimodal_emotion_engine-0.4.5-py3-none-any.whl[vision]`).

### Download model weights
The production weights live in the canonical `models/` tree (not shipped with the
pip wheel). On a fresh host, populate + verify them once:
```bash
python3 tools/download_models.py           # vision (models/vision_emotion) + voice (models/voice)
python3 tools/download_models.py --verify  # re-check sizes / checksums
```
The engine resolves `models/` automatically (resolver layer; override with
`MEE_MODEL_ROOT` / `MEE_VISION_MODEL_PATH` / `MEE_VOICE_MODEL_PATH`).
See [`models/README.md`](models/README.md) and [`docs/MODELS.md`](docs/MODELS.md).

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
│   ├── voice/        # Voice emotion pipeline (+ out-of-process voice_worker.py / voice_worker_client.py on hosts where the voice+vision runtimes collide)
│   ├── fusion/       # Multimodal fusion
│   ├── state/        # Temporal state tracking
│   └── api/          # Public API (EmotionEngine)
├── demo/             # Demonstration UI
├── tests/            # Unit and integration tests
└── docs/             # Architecture and deployment docs
```

## Status

**✅ v0.4.5 — All tasks complete** (G1→G5 for all MEE tasks through MEE_020; signed distribution pipeline operational)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for detailed design documentation.

**Model weights** live in a single canonical tree inside the repo —
[`models/`](models/README.md) (`models/vision_emotion/`, `models/voice/`,
`models/voice_gpu/`). On a fresh host, populate it with
`python3 tools/download_models.py`. The engine resolves these paths directly
(resolver layer; env `MEE_MODEL_ROOT` / `MEE_VISION_MODEL_PATH` /
`MEE_VOICE_MODEL_PATH` override). See
[`docs/MODELS.md`](docs/MODELS.md) for the full layout, the resolver layer, and
the MediaPipe pip package that ships vision face-detection.

## Limitations & Disclaimer

- **Emotion estimates are probabilistic**, not psychological assessments. They represent statistical inferences from facial expressions and vocal characteristics — they do not "read true emotion."
- **Single-session state only:** `EmotionHistory` resets per `EmotionEngine` instance (session restart = history reset). No cross-session persistence.
- **Window-based trend estimation:** The dominant-emotion approach with confidence delta comparison has known limitations:
  - Very short interactions (<3 samples) → "unstable" by design
  - Rapid emotion changes may not be captured accurately
  - Confidence thresholds are configurable but require tuning for specific use cases

## Third-Party Components & Licensing

See [`docs/THIRD_PARTY_LICENSES.md`](docs/THIRD_PARTY_LICENSES.md) for the complete inventory of third-party components used by MEE, including their licenses and commercial-use status.

The MEE core package is distributed under the **Deepsim Commercial Software License v1.1** (`LICENSE.txt`). Previous versions are retained in `LICENSE_1.0` for reference. License activation is managed via the `mee-lic` CLI against the Keygate server (see `docs/development/reports/TASK_MEE_015/` for the Gate C specification).

### Licensing & Plans (TASK_MEE_019)

MEE offers five license plans. The remote demo (`mee-remotedemo`) includes a built-in License UI
(license status card, plan selection grid, key activation, deactivation, and free Community/Academic
request) at the bottom of the right column.

| Plan | Type | Purchase / Request | Max Activations | Billing |
|------|------|--------------------|-----------------|---------|
| **Community / Academic** | Free | Self-service request via License UI (name + email, institution optional) | 1 | — |
| **Developer** | Paid | [Checkout](https://licenses.deepsim.ai:8443/pay/6c5bce2c) | 3 | Yearly |
| **Commercial** | Paid | [Checkout](https://licenses.deepsim.ai:8443/pay/7d44a91b) | 3 | Yearly |
| **Enterprise** | Paid | [Checkout](https://licenses.deepsim.ai:8443/pay/d09d97da) | 5 | Yearly |
| **OEM / Embedded** | Paid | [Checkout](https://licenses.deepsim.ai:8443/pay/15f2f3d7) | 5 | Yearly |

**Free Community/Academic request:** Click the Community/Academic card in the License UI, fill in
your name, email, and (optionally) institution, then click **Request Free License**. A real license
key is returned immediately via the Keygate admin API (server-side proxy — no card required).
Rate-limited: 1 request per email per 24 h, 3 per IP per hour.

**Paid plans:** Clicking a paid plan card opens the Keygate Stripe Checkout page in a new tab.
After payment the license key is created in Keygate and can be activated from the License UI or
via `mee-lic activate <key>`.

**CLI (unchanged, TASK_MEE_015):**

```bash
mee-lic status                        # show current license status
mee-lic activate <KEY>                # activate a license key
mee-lic deactivate                    # deactivate the current license
```

**Keygate server:** `https://licenses.deepsim.ai:8443` (configurable via `MEE_LICENSE_SERVER`).

### Summary

| Category | License | Commercial Use? |
|----------|---------|-----------------|
| Core package code | Deepsim Commercial Software License v1.1 (proprietary) — see `LICENSE.txt` | Yes (licensed) |
| Vision pipeline (retina-face, face-alignment, EmotiEffLib) | MIT/Apache-2.0 ✅ | Yes |
| Voice pipeline (SpeechBrain RavNet) | Apache-2.0 ✅ | Yes |
| OpenCV, librosa, streamlit, etc. | Various open-source ✅ | Yes |

All model weights used in production are released under commercial-safe licenses by their respective authors. AGPL/NC models were explicitly excluded from the MEE design.

---
*MEE remains an independent capability, not tied to the AI Companion book or any specific robot.*
*“Affective-state estimation” — never “reads true emotion.”*

---

**Suggested Citation:**

Wei, S. (2026). *MEE: A Multimodal Affective State Estimation Engine for AI Companions and Intelligent Robots*. Deepsim AI Lab Research & Technical Notes, DAI-LAB-TN-2026-003. Version 1.0. Deepsim Press. DOI: https://doi.org/10.5281/zenodo.23669367  
