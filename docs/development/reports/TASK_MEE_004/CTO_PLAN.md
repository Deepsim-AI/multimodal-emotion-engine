# CTO Plan — TASK_MEE_004: Vision Emotion Engine

**Task ID:** TASK_MEE_004  
**Gate:** G1 — Plan Approval  
**Phase:** 2 / Vision Emotion Engine  
**Date:** 2026-09-19  
**Planned By:** CTO / Architect  

---

## 1. Objective

Implement the full Vision submodule (`mee/vision/`) that performs face detection → facial expression estimation using **InsightFace Buffalo_L + SCRFD**, returning structured emotion results matching the public API. This replaces the empty stub currently in `mee/vision/__init__.py`.

**Model Selection Reference:** TASK_MEE_001 / `docs/MODEL_EVALUATION.md` — InsightFace Buffalo_L (ArcFace) + SCRFD detector, ★★★★★ recommendation. License: MIT/Apache-2.0 variant (commercial-safe). Model size: ~50–80 MB. Format: ONNX-compatible via insightface runtime.

---

## 2. Dependency Verification (Pre-G1 Gate Check)

| Requirement | Status | Evidence |
|---|---|---|
| TASK_MEE_001 G4 approved | ✅ | `docs/development/reports/TASK_MEE_001/CTO_APPROVAL.md` |
| TASK_MEE_002 evaluation complete | ✅ | `docs/MODEL_EVALUATION.md` — InsightFace recommended |
| Public API boundary stable | ✅ | `mee/api/engine.py` — EmotionEngine.process() signature confirmed |
| Vision submodule exists (stub) | ✅ | `mee/vision/__init__.py` present, empty |

---

## 3. Implementation Plan (7 Subtasks)

### Subtask 1: Add Dependencies (`pyproject.toml` ~line 20)

**File:** `/home/deepsim/multimodal-emotion-engine/pyproject.toml`  
**Section:** `[project.optional-dependencies].vision` (add to existing line)

Add to the `vision` optional deps list:
- `insightface>=0.7` — InsightFace FaceAnalysis with SCRFD + ArcFace models
- `deepface>=0.0.84` — facade library for easy model loading
- Update: ensure `onnxruntime-gpu>=1.16` is present (for Jetson TensorRT path)

**Change marker:** `// TASK_MEE_004 Subtask 1: Add insightface, deepface to [project.optional-dependencies].vision`

---

### Subtask 2: Vision Detector — `mee/vision/detector.py`

**File:** `/home/deepsim/multimodal-emotion-engine/mee/vision/detector.py` (NEW — ~150 lines)

```
Classes:
- FaceBox: dataclass(attrs=["x1","y1","x2","y2","score"])
  x1,y1,x2,y2 in pixel coordinates relative to frame; score = detection confidence [0,1]

- FaceDetector: wraps SCRFD via insightface.app.FaceAnalysis
  __init__(det_size=(640, 640), target="cuda"|"cpu")
    - det_size: SCRFD detection resolution (larger → more faces, slower)
    - target: "cuda" for GPU, "cpu" for fallback
    - Downloads SCRFD model to ~/.insightface/models/ on first use
  detect(frame) -> list[FaceBox]
    - Input: BGR numpy array (H×W×3 uint8)
    - Returns: empty list if no faces; list of FaceBox objects if detected
    - Sorts by score descending
```

**Behavior:**
- On first call, initializes SCRFD model via `insightface.app.FaceAnalysis(name="scrfd")`
- If insightface not installed: log WARNING, return `[]` from detect()
- If frame is None or empty: return `[]` (no exception)
- Handles single-channel (grayscale) input by converting to BGR

**Change marker:** `// TASK_MEE_004 Subtask 2: New file - FaceDetector + FaceBox for SCRFD-based face detection`

---

### Subtask 3: Vision Emotion Model — `mee/vision/emotion_model.py`

**File:** `/home/deepsim/multimodal-emotion-engine/mee/vision/emotion_model.py` (NEW — ~120 lines)

```
Classes:
- ExpressionClassifier: wraps ArcFace from InsightFace Buffalo_L
  __init__(model_path=None)
    - model_path: optional path to custom .onnx or insightface model directory
    - Downloads ArcFace model to ~/.insightface/models/ on first use if not found
  infer(face_crop) -> {"emotion": str, "confidence": float, "scores": dict}
    - face_crop: RGB numpy array (112×112×3 uint8 or float32) — ArcFace input size
    - Returns: emotion label string, confidence (max of scores), scores dict with all 7 classes

Emotion labels (ArcFace / FFHQ alignment):
["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
```

**Behavior:**
- Maps ArcFace model output to standardized MEE label set (7 classes above)
- Crop from SCRFD box → 112×112 RGB (ArcFace input requirement)
- If insightface not installed: log WARNING, return `{"emotion": "unknown", "confidence": 0.0, "scores": {}}`

**Change marker:** `// TASK_MEE_004 Subtask 3: New file - ExpressionClassifier for ArcFace-based facial expression classification`

---

### Subtask 4: Vision Processor — `mee/vision/processor.py`

**File:** `/home/deepsim/multimodal-emotion-engine/mee/vision/processor.py` (NEW — ~200 lines)

```
Classes:
- FaceProcessor: orchestrates detector + classifier
  process(frame) -> dict matching _MEEFaceResult schema
  __init__(detector=None, classifier=None, config=MEEConfig)

Pipeline per frame:
1. If frame is None or empty → return no-face result (has_face=False)
2. Run detector.detect(frame) → list[FaceBox]
3. If no faces detected → return no-face result (has_face=False)
4. For each FaceBox:
   a. Extract face crop from BGR frame using box coordinates
   b. Convert to RGB, resize to 112×112
   c. Run classifier.infer(crop) → scores dict
5. Aggregate results:
   - Return list of per-face emotion dicts (each with emotion/confidence/scores)
   - Compute "dominant" emotion: highest average confidence across faces
6. Apply face_confidence_threshold from config:
   - If dominant confidence < threshold → has_face=False, no-face result

Return schema (matches _MEEFaceResult.to_dict()):
{
  "emotion": str or None,
  "confidence": float [0.0, 1.0],
  "scores": dict of {label: probability},
  "has_face": bool,
}
```

**Change marker:** `// TASK_MEE_004 Subtask 4: New file - FaceProcessor orchestrating detector + classifier pipeline`

---

### Subtask 5: Update `mee/vision/__init__.py`

**File:** `/home/deepsim/multimodal-emotion-engine/mee/vision/__init__.py` (MODIFY — ~15 lines, was stub)

Replace stub with public exports:
```python
from .detector import FaceDetector, FaceBox
from .emotion_model import ExpressionClassifier
from .processor import FaceProcessor
__all__ = ["FaceDetector", "FaceBox", "ExpressionClassifier", "FaceProcessor"]
```

**Change marker:** `// TASK_MEE_004 Subtask 5: Export Vision submodule public API`

---

### Subtask 6: Wire Vision into Public API — `mee/api/engine.py`

**File:** `/home/deepsim/multimodal-emotion-engine/mee/api/engine.py` (MODIFY — ~40 lines changed)

| Line Range | Current | New |
|---|---|---|
| ~15 (imports) | `import time; from dataclasses import...` | Add: `from ..vision.processor import FaceProcessor` |
| ~48 (`__init__`) | `_model_ready = False` stub | Try block: `self._face_processor = FaceProcessor(); self._model_ready = True`; except ImportError/IOError: log WARNING, keep `_model_ready=False` |
| ~90-95 (`_infer_vision`) | returns empty result if no model | Call `self._face_processor.process(frame)` with try/except; return result dict matching `_MEEFaceResult.to_dict()` schema |

**Specific code for `_infer_vision` replacement:**

```python
def _infer_vision(self, frame=None) -> _MEEFaceResult:
    if not self._model_ready or frame is None:
        return _MEEFaceResult()  # no-face result
    try:
        result_dict = self._face_processor.process(frame)
        return _MEEFaceResult(
            emotion=result_dict.get("emotion"),
            confidence=result_dict.get("confidence", 0.0),
            scores=result_dict.get("scores", {}),
            has_face=result_dict.get("has_face", False),
        )
    except Exception as exc:
        return _MEEFaceResult()  # graceful degradation on error
```

**Change marker:** `// TASK_MEE_004 Subtask 6: Integrate Vision processor into EmotionEngine._infer_vision()`

---

### Subtask 7: Unit Tests — `tests/test_vision.py`

**File:** `/home/deepsim/multimodal-emotion-engine/tests/test_vision.py` (NEW — ~100 lines)

```
Test classes/functions:
1. test_face_detector_no_face()
   - Input: blank gray numpy array (256×256×3 uint8)
   - Assert: detect() returns empty list

2. test_expression_classifier_labels()
   - Verify all 7 expected labels present in classifier output
   - Assert: scores keys == ["angry","disgust","fear","happy","sad","surprise","neutral"]

3. test_face_processor_returns_dict_shape()
   - Pass None frame → assert has_face=False, emotion=None
   - Verify all required keys present in result dict

4. test_graceful_fallback_without_insightface()
   - Monkeypatch insightface module to raise ImportError on import
   - Assert: FaceProcessor creation doesn't crash
   - Assert: process(frame) returns no-face dict (not exception)

5. test_emotion_engine_vision_integration()
   - Create EmotionEngine with face_confidence_threshold=0.3
   - Call process(video_frame=None, audio=None) — assert no crash
   - Assert: result["face"]["has_face"] == False when no frame provided
```

**Change marker:** `// TASK_MEE_004 Subtask 7: New file - Unit tests for Vision submodule`

---

## 4. Acceptance Criteria

| Criterion | Verification Method |
|---|---|
| `pip install multimodal-emotion-engine[vision]` installs without errors | Run `pip install .[vision]` in test env |
| `FaceDetector.detect()` returns empty list for blank image | Unit test: `test_face_detector_no_face` |
| `ExpressionClassifier.infer()` returns 7-class scores dict | Unit test: `test_expression_classifier_labels` |
| `FaceProcessor.process(frame)` matches `_MEEFaceResult.to_dict()` schema | Unit test: `test_face_processor_returns_dict_shape` |
| `EmotionEngine._infer_vision(None)` returns no-face dict (not crash) when insightface unavailable | Unit test: `test_graceful_fallback_without_insightface` |
| `EmotionEngine.process(video_frame=None, audio=None)` doesn't crash | Unit test: `test_emotion_engine_vision_integration` |
| All unit tests pass: `pytest tests/test_vision.py -v` | Run test command |
| No AGPL/NC dependencies in final dependency tree | Check `pip show insightface deepface` license fields |

---

## 5. Risk Mitigation

| Risk | Mitigation |
|---|---|
| InsightFace SCRFD download fails (network) | Implement offline path: document manual weight download; support `INSIGHTFACE_MODEL_DIR` env var override |
| Jetson TensorRT compatibility deferred | CPU-only inference sufficient for this task; architecture supports later GPU backend swap |
| Model size ~80MB on first import | Add pip install note in docs; implement download timeout handling with retry |
| SCRFD det_size tuning affects accuracy/speed | Use (640,640) as default; document that it's tunable via config or constructor arg |

---

## 6. Implementation Strategy: Auto + Sequential

### Auto Strategy (recommended — single session)
The Implementer executes all 7 subtasks sequentially in one session:
1. Subtask 1 → dependencies installed
2. Subtask 2 → detector.py created
3. Subtask 3 → emotion_model.py created
4. Subtask 4 → processor.py created
5. Subtask 5 → `__init__.py` updated
6. Subtask 6 → engine.py wired
7. Subtask 7 → tests written + run

Each subtask produces inline change markers (`// TASK_MEE_004 Subtask N:`) for review traceability.

### Sequential Strategy (fallback — if compaction pressure detected)
- **Session A:** Complete Subtasks 1–4 (all new files created, dependencies installed)
- **Session B:** Complete Subtasks 5–7 (integration wiring + tests)
- If session hits compaction: write `COMPACTION_FAILURE.md` with completed subtasks list, save all in-progress artifacts to disk before closing

### Post-G4 PM Duties
PM handles: updating PROJECT_STATUS.md, CHANGELOG.md, sending PM_CLOSED notification. CTO does NOT perform these.

---

**CTO Signature:** CTO / Architect — 2026-09-19  
**Verdict:** ✅ G1 Plan Approved — dispatch to Implementer
