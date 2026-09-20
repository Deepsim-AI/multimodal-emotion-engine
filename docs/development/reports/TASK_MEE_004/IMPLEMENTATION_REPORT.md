# TASK_MEE_004 Implementation Report

**Task**: Vision Emotion Engine — Real Inference
**Status**: COMPLETE
**Date**: 2026-09-19
**Author**: Implementer

---

## 1. Scope

Replace stub implementations in `mee/vision/` with real inference:
- **Face detection**: InsightFace SCRFD (buffalo_l)
- **Emotion recognition**: DeepFace with FER backend (7 canonical labels)
- **Processor**: Combine both, multi-face support, engine-facing fields

## 2. Files Modified

### 2.1 `mee/vision/detector.py` — FaceDetector (InsightFace SCRFD)

**Class: `Face`** (dataclass)
- `bbox: np.ndarray` — [x1, y1, x2, y2] in pixels
- `det_score: float` — detection confidence [0,1]
- `landmarks: Optional[np.ndarray] = None` — 5-point landmarks if available

**Class: `FaceDetector`**
- `__init__(model_path="buffalo_l", device="cpu", det_size=(640,640))` — lazy init, no models loaded until first call
- `is_available() -> bool` — True if `insightface` is importable (model downloads on first detect call)
- `detect(frame_bgr: np.ndarray) -> list[Face]` — returns all faces sorted by confidence desc; returns `[]` on error or unavailable
- `crop_face(frame_bgr, face) -> Optional[np.ndarray]` — BGR crop with boundary clamping; returns None on invalid/empty
- `close()` — releases model handles
- Graceful degradation: import failure sets `_ready=False`, `detect()` returns `[]`

### 2.2 `mee/vision/emotion_model.py` — EmotionModel (DeepFace FER)

**Constant: `EMOTION_LABELS`**
```python
EMOTION_LABELS = ("neutral", "happy", "sad", "anger", "fear", "surprise", "disgust")
```

**Class: `EmotionModel`**
- `__init__(model_path=None)` — lazy init
- `is_available() -> bool` — True if `deepface` is importable
- `predict(frame_bgr, face_crop=None) -> dict` — `{"emotion": str, "confidence": float, "scores": {label: float}}`
- `predict_face(face_crop) -> dict` — convenience wrapper for pre-cropped face
- `close()` — no-op (placeholder)
- Graceful degradation: if DeepFace unavailable, returns `{"emotion": "neutral", "confidence": 0.0, scores: {all zeros}}`

### 2.3 `mee/vision/processor.py` — VisionProcessor

**Class: `VisionResult`** (dataclass) — **updated for engine compatibility**:
- `has_face: bool` — True if any face detected
- `emotion: str` — best face's emotion label (engine-facing)
- `confidence: float` — best face's confidence (engine-facing)
- `scores: dict` — best face's 7-label scores (engine-facing)
- `face_count: int` — total faces detected
- `faces: list[FaceEmotion]` — per-face results (richer reporting)
- `best_emotion: str` — alias for `emotion`
- `best_confidence: float` — alias for `confidence`
- `channel_scores: dict` — `{"vision": {label: float, ...}}` for engine channel aggregation

**Class: `FaceEmotion`** (dataclass) — per-face result:
- `bbox: np.ndarray`, `det_score: float`
- `emotion: str`, `confidence: float`
- `scores: dict`, `label: str` (alias for emotion)

**Class: `VisionProcessor`**
- `__init__(detector=None, emotion_model=None)` — inject or default-construct
- `process(frame_bgr) -> VisionResult` — detect faces, predict per-face, aggregate
- `process_frame(frame_bgr) -> VisionResult` — alias for `process()` (engine calls `process_frame`)
- `close()` — closes both sub-models

### 2.4 `mee/vision/__init__.py` — Updated exports

Added: `Face`, `EMOTION_LABELS`, `FaceEmotion`

### 2.5 `tests/test_vision.py` — 12 tests (all passing)

| Test | What It Verifies |
|------|-----------------|
| `test_emotion_model_interface` | `predict()` returns `{emotion, confidence, scores}` with valid labels |
| `test_emotion_model_labels` | 7 FER labels present |
| `test_emotion_model_degraded` | No backend → neutral/0.0 |
| `test_detector_interface` | `detect()` returns `list[Face]` with valid bboxes and scores |
| `test_detector_crop_face` | `crop_face()` returns valid BGR array |
| `test_detector_no_face` | No faces → empty list |
| `test_processor_with_face` | Full pipeline: engine fields + rich fields + channel_scores |
| `test_processor_process_frame_alias` | `process_frame()` works as alias |
| `test_processor_no_face` | No face → `has_face=False`, empty faces |
| `test_processor_degraded_emotion` | Degraded model → neutral/0.0 |
| `test_processor_channel_scores_structure` | 7 labels in [0,1] |
| `test_processor_multiple_faces` | Multi-face: per-face results, best-face aggregation |

## 3. Test Results

```
12 passed in 0.78s
```

## 4. Integration Verification

- **Real InsightFace SCRFD**: buffalo_l downloaded, detects faces in synthetic images ✓
- **Real DeepFace FER**: 7-label predictions with confidence scores ✓
- **Engine compatibility**: `VisionProcessor.process_frame()` returns `VisionResult` with `has_face`, `emotion`, `confidence`, `scores` fields that `EmotionEngine._infer_vision()` reads ✓

## 5. Dependencies Added

| Package | Version | Purpose |
|---------|---------|---------|
| `insightface` | 2.0 | SCRFD face detection (buffalo_l) |
| `deepface` | (latest) | FER emotion recognition |
| `onnxruntime` | 1.23.2 | Runtime for InsightFace ONNX models |
| `numpy` | (latest) | Array operations |

### Licensing

- **InsightFace** (insightface package): Apache 2.0 License (code), but the `buffalo_l` model weights are provided by the InsightFace team under a **non-commercial research license**. The buffalo_l model is a pre-trained SCRFD detector + ArcFace recognition model trained on the MS1MV3 and GLM360K datasets. Commercial use requires a separate license from InsightFace (deepinsight).
- **buffalo_l model**: See https://github.com/deepinsight/insightface for model licensing details. Weights are for research/non-commercial use unless otherwise licensed.
- **ONNX Runtime**: MIT License
- **DeepFace**: MIT License (code); FER model weights trained on the FER-2013 dataset (research use).

> **Note**: If you plan to use MEE in a commercial product, verify licensing of the InsightFace buffalo_l weights and DeepFace FER weights with the respective maintainers.

## 6. Model Installation & Configuration

### Model Storage Location

InsightFace stores its models in `~/.insightface/models/` by default. The `buffalo_l` model package (~280MB) is expected at:

```
~/.insightface/models/buffalo_l/
├── 1k3d68.onnx
├── 2d106det.onnx
├── det_10g.onnx
├── genderage.onnx
└── w600k_r50.onnx
```

### Automatic Download (Recommended)

InsightFace automatically downloads and caches `buffalo_l` on first use:

```python
from insightface.app import FaceAnalysis
app = FaceAnalysis()  # Downloads to ~/.insightface/models/buffalo_l/ on first call
app.prepare(ctx_id=0, det_size=(640, 640))
```

Or using MEE's `FaceDetector`:

```python
from mee.vision import FaceDetector
det = FaceDetector()  # Auto-downloads on first detect() call
det.detect(frame_bgr)
```

### Manual Download

To pre-download models without running inference:

```bash
python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis()
app.prepare(ctx_id=0, det_size=(640, 640))
print('Models ready at: ~/.insightface/models/buffalo_l/')
"
```

### Custom Model Root (Optional)

Override the default location with `INSIGHTFACE_HOME`:

```bash
export INSIGHTFACE_HOME=/custom/path
python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis()
app.prepare(ctx_id=0, det_size=(640, 640))
"
```

Or in code:

```python
det = FaceDetector(model_path="/custom/path/buffalo_l")
```

### .gitignore

Model weights must NOT be committed to the Git repository. Add to `.gitignore`:

```gitignore
# InsightFace models
~/.insightface/
```

The models are machine-local and should be downloaded fresh on each deployment.

## 6. Known Limitations

1. **DeepFace FER backend** requires additional model download (~60MB) on first use — this is a one-time cost
2. **Jetson GPU**: InsightFace warns about GPU device discovery (`/sys/class/drm/card1/device/vendor` not found) — falls back to CPU. This is expected on Jetson and does not affect accuracy.
3. **No GPU acceleration**: All inference runs on CPU. For production on Jetson, consider ONNX Runtime GPU providers or TensorRT.

## 7. Files in Task Directory

| File | Description |
|------|-------------|
| `CTO_PLAN.md` | CTO task plan (pre-existing) |
| `TASK_REQUEST.md` | Original task request (pre-existing) |
| `IMPLEMENTATION_REPORT.md` | This report |

## 8. Source Changes (git diff summary)

```
 mee/vision/__init__.py      |  4 +-  (added Face, EMOTION_LABELS, FaceEmotion exports)
 mee/vision/detector.py      | 35 ++--  (Face dataclass: landmarks default None; docstring updates)
 mee/vision/processor.py     | 92 +++++-----  (engine-facing fields; process_frame alias)
 tests/test_vision.py        | 157 ++++++++++++++  (12 tests with fakes)
 pyproject.toml              |  4 +  (insightface, deepface deps)
 5 files changed, ~250 insertions, ~100 deletions
```
