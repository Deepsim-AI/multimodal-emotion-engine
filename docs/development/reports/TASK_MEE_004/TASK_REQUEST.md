# TASK_REQUEST — TASK_MEE_004: Vision Emotion Engine

**Task ID:** TASK_MEE_004
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Implement the vision module so `EmotionEngine.process(video_frame=...)` performs real facial-expression estimation: detect faces, crop/preprocess, run the approved vision model, and return per-face emotion probabilities with confidence. Models remain behind the stable API.

## Detailed Requirements
- Implement `mee/vision/detector.py` (face detection, multi-face support where practical), `mee/vision/emotion_model.py` (expression inference over a label set), `mee/vision/processor.py` (crop/preprocess → model → probabilities).
- Wire the module into `mee/api/engine.py` `_infer_vision()` **without changing the `process()` signature or `MEEConfig` fields**.
- Return, per face: `emotion`, `confidence`, `scores` (softmax per label), `has_face`. Handle **no-face** input gracefully (return `has_face=False`).
- Use the CTO-recommended vision model (see TASK_MEE_002). If the model package is not installed, fall back gracefully (see TASK_MEE_001) — do not crash.
- Support configurable model backend per ARCHITECTURE (replaceable implementation detail).

## Key Files (to create/modify)
- `mee/vision/detector.py`, `mee/vision/emotion_model.py`, `mee/vision/processor.py`
- `mee/api/engine.py` — update `_infer_vision()` only (mark `TASK_MEE_004`)

## Acceptance Criteria
- [ ] Given a face image, returns emotion + confidence + `scores` dict; `has_face=True`.
- [ ] Given a no-face image / None frame, returns `has_face=False` without error.
- [ ] Works with at least one supported backend; degrades gracefully when none installed.
- [ ] Multiple faces handled if more than one present (best-effort in V1).
- [ ] Public API signature unchanged; existing tests still pass.
- [ ] Unit tests added (`tests/test_vision.py`).

## Dependencies
- TASK_MEE_001 (repo + API stub), TASK_MEE_002 (approved vision model).

## Notes / Constraints
- "Facial-expression / facial-emotion estimation"; never "reads true emotion."
- Keep model as an implementation detail; consumers never import model internals.
