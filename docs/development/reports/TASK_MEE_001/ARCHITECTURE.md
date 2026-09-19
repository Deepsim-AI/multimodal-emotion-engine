# MEE V1 Architecture & Stable API Boundary

**Document:** ARCHITECTURE.md  
**Version:** 1.1 (Finalized TASK_MEE_001)  
**Status:** Draft — awaiting user approval at G2  
**Created:** 2026-09-18 | **Updated:** 2026-09-18

---

## 1. Scope & Constraints

MEE is an independent, local-first AI perception component that estimates affective state from observable signals (facial-expression estimation and voice/acoustic emotion estimation). It does **not** claim to determine a person's true internal psychological state. MEE remains fully independent of the AI Companion book Chapter 15.

---

## 2. Stable Public API (Locked for V1)

This is the ONLY interface external consumers use:

```python
from mee.api.engine import EmotionEngine

engine = EmotionEngine()

result = engine.process(
    video_frame: Optional[np.ndarray] = None,   # BGR frame from webcam (H×W×3 uint8) or None
    audio: Optional[np.ndarray] = None,          # 1-D float32 audio samples at 16kHz or None
)
```

### Return Type (JSON-serializable dict)

```python
{
    "face": {                              # None if no face / frame not provided
        "emotion": str | None,             # one of model's native labels
        "confidence": float,               # 0.0–1.0
        "scores": dict[str, float],        # raw softmax per label (optional)
        "has_face": bool                   # True if face detected at all
    } | None,

    "voice": {                             # None if no audio / chunk not provided
        "emotion": str | None,             # one of model's native labels
        "confidence": float,               # 0.0–1.0
        "scores": dict[str, float],        # raw softmax per label (optional)
    } | None,

    "overall": {
        "emotion": str,                    # fused label; never None
        "confidence": float,               # 0.0–1.0
        "conflict": bool,                  # True if face & voice disagree significantly
    },

    "trend": str,                          # "increasing" | "stable" | "decreasing" | "unknown"
    "latency_ms": float,                   # end-to-end pipeline latency
}
```

### V1 Default Emotion Labels

The fusion layer normalizes to a fixed vocabulary (regardless of model's native labels):

```
neutral, happy, sad, angry, frustrated, surprised, fearful, disgust
```

Model-native labels not in this set are mapped or clamped. The mapping is documented in each model backend.

### Temporal State

- `trend` derives from a sliding window (default 30 frames) over previous `overall.emotion` values.
- `conflict` is True when two modalities predict different labels AND both confidence > threshold (default 0.5).

---

## 3. Architecture Diagram (Minimal — V1)

```
  Application
      │
      ▼  engine.process(video_frame, audio)
┌─────────────────────────────────────┐
│          EmotionEngine              │
│  ┌─────────┐   ┌──────────────┐    │
│  │  State  │◄──┤    Fusion    │    │
│  │Tracker   │   │   Engine     │    │
│  └─────────┘   └──────┬───────┘    │
│                        │            │
│         ┌──────────────┼───────────┐│
│         ▼             ▼           ▼│
│   ┌──────────┐  ┌──────────┐       │
│   │  Vision  │  │  Voice   │       │
│   │Processor │  │Processor │       │
│   └──────────┘  └──────────┘       │
└─────────────────────────────────────┘
```

### Module Summary

| Module | Purpose | Dependencies on Other MEE Modules |
|---|---|---|
| `mee.api.engine` | Public API boundary; instantiates all submodules | Imports fusion, state, vision, voice |
| `mee.vision.processor` | Face detection → crop → expression inference | Depends only on model backend (ONNX/runtime) |
| `mee.vision.detector` | Face box localization from raw frame | None (pure function on numpy arrays) |
| `mee.vision.emotion_model` | Abstract + concrete expression model wrapper | ONNX Runtime or equivalent; model file path via config |
| `mee.voice.processor` | Audio capture → feature extraction → emotion inference | Depends only on model backend |
| `mee.voice.features` | MFCC, pitch, energy, spectral stats | NumPy/Librosa (no MEE deps) |
| `mee.fusion.emotion_fusion` | Weighted-vote + conflict detection | None (pure function) |
| `mee.state.history` | Ring-buffer of emotion events | None |
| `mee.state.estimator` | Trend analysis over history buffer | history.py only |

---

## 4. V1 Model Selection (Preview — full eval in MODEL_EVALUATION.md)

Per the task's Phase 1 requirement, models must be configurable via `pyproject.toml` extras or a config file. V1 ships with one recommended per modality:

| Modality | Recommended V1 Model | License | Format | Size | ONNX/Jetson |
|---|---|---|---|---|---|
| Vision (face expr.) | **DeepFace + InsightFace** (VGG-Face/Buffalo_L) | MIT / Apache-2.0 | onnxruntime | ~50-150 MB | ONNX → TensorRT via trtexec |
| Voice (acoustic emotion) | **OpenSMILE features + pre-trained SVM/RF** or **Wav2Vec 2.0 fairseq checkpoint** | MIT / CC-BY-NC per checkpoint variant | onnxruntime / fairseq | ~350 MB max | ONNX feasible for smaller; TensorRT for Wav2Vec |

See `docs/MODEL_EVALUATION.md` for full evaluation table and justification.

---

## 5. Package Layout (Final V1)

```
multimodal-emotion-engine/
├── README.md
├── LICENSE
├── pyproject.toml
├── .gitignore
│
├── mee/
│   ├── __init__.py          # EmotionEngine = alias for api.engine.EmotionEngine
│   ├── api/
│   │   ├── __init__.py      # re-export EmotionEngine, MEEConfig
│   │   └── engine.py        # ★ EMOTIONENGINE CLASS — THE ONLY PUBLIC API
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── detector.py
│   │   ├── emotion_model.py
│   │   └── processor.py
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── recorder.py
│   │   ├── features.py
│   │   ├── emotion_model.py
│   │   └── processor.py
│   ├── fusion/
│   │   ├── __init__.py
│   │   └── emotion_fusion.py
│   ├── state/
│   │   ├── __init__.py
│   │   ├── history.py
│   │   └── estimator.py
│
├── demo/
│   └── emotion_demo.py      # streamlit / curses placeholder
│
├── tests/
│   ├── __init__.py
│   ├── test_vision.py
│   ├── test_voice.py
│   ├── test_fusion.py
│   └── test_state.py
│
└── docs/
    ├── ARCHITECTURE.md      # this file
    ├── MODEL_EVALUATION.md  # Phase 1 deliverable
    └── JETSON_DEPLOYMENT.md (future TASK_MEE_009)
```

---

## 6. Configuration (Minimal for V1)

Config is a simple YAML dict loaded at `EmotionEngine()` instantiation:

```python
class MEEConfig:
    """V1 configuration — all defaults work without user input."""
    
    # Fusion weights (defaults to V1 starting point)
    fusion_weights: dict[str, float] = {"vision": 0.5, "voice": 0.5}
    
    # Conflict threshold
    conflict_threshold: float = 0.5
    
    # State window (frames)
    trend_window: int = 30
    trend_min_samples: int = 5
    
    # Vision defaults
    vision_model_path: Optional[str] = None       # or auto-download
    face_confidence_threshold: float = 0.7
    
    # Voice defaults  
    voice_model_path: Optional[str] = None
    audio_sample_rate: int = 16000
    
    # Output
    output_format: str = "json"                    # always JSON dict for V1
```

---

## 7. Error Model (Graceful Degradation)

| Failure Mode | Behavior |
|---|---|
| No face detected | `face` → `{"emotion": None, "confidence": 0.0, "scores": {}, "has_face": False}`; overall = voice-only if available |
| No audio chunk | `voice` → `None`; overall = vision-only |
| Model load failure | Raise `MEEInitError` at construction; do not silently degrade to bad results |
| Inference exception | Return nulls for that modality's output; log warning; continue pipeline |
| Fusion with all-null inputs | Raise `ValueError("Both modalities are None")`; user must supply at least one input |

---

## 8. Performance Targets (V1 Benchmarks — to be measured in TASK_MEE_009)

| Component | Target (PC CPU) | Target (Jetson Orin) |
|---|---|---|
| Face detection | < 50 ms | < 30 ms (GPU) |
| Expression inference | < 100 ms | < 50 ms (TensorRT) |
| Audio feature extraction | < 20 ms | < 20 ms |
| Voice emotion inference | < 100 ms | < 60 ms (TensorRT) |
| Fusion + state update | < 5 ms | < 5 ms |
| **Total pipeline** | **< 300 ms** | **< 150 ms** |

---

## 9. Non-Goals (Explicitly Out of Scope for V1)

- Robot/hardware control
- LLM integration, sentiment analysis from transcript
- TTS or speech synthesis
- Long-term memory beyond 30-frame trend window
- Cloud-based processing
- Mobile app
- Production web service / SDK
- Model training (only inference with pretrained models)

---

## 10. Open Questions for User Decision

| # | Question | CTO Recommendation |
|---|---|---|
| 1 | Emotion label set: use MEE's fixed 8-label set or defer to model-native labels? | **Recommend:** Fixed 8-label set (V1) with per-model mapping table documented in MODEL_EVALUATION.md |
| 2 | Fusion weighting starting point? | **Recommend:** Default 50/50 vision/voice; context-weighted only when both available. Configurable via MEEConfig. |
| 3 | Conflict policy: preserve disagreement vs majority vote? | **Recommend:** Preserve disagreement — emit `conflict: True` with reduced confidence per project plan Test E. |
| 4 | ASR passthrough in V1? | **Recommend:** No ASR in V1. Voice = acoustic features only. Add transcript passthrough as optional V1.1. |
| 5 | Model download at first use vs vendor-provided weights? | **Recommend:** Auto-download with sha256 verification on first import (with `--offline` flag to skip). Weights stored in `~/.cache/mee/models/`. |

---

**This architecture document is frozen for V1 scope.** Any changes beyond API contract require a new task.
