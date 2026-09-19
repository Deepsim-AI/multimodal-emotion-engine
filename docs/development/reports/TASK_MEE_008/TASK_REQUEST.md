# TASK_REQUEST — TASK_MEE_008: Emotion Demonstration UI

**Task ID:** TASK_MEE_008
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Build a lightweight **local demonstration UI** (not a production UI) that displays live vision, voice, fused state, trend, confidence, and (if enabled) transcript — for technical evaluation and demos.

## Detailed Requirements
- Implement `demo/emotion_demo.py` using the demo dependency group (e.g. streamlit per pyproject). It must drive `EmotionEngine.process()` with live camera + microphone input.
- Display: camera image, detected face (bounding box), facial emotion + confidence, voice emotion + confidence, fused overall state + confidence, trend indicator, and transcript if ASR is enabled.
- Respect the public API contract (call `EmotionEngine().process(video_frame=, audio=)`); the UI is a **consumer**, never touching model internals.
- Degrade gracefully when camera/microphone/hardware is unavailable (show a clear message, do not crash).
- Provide a headless/non-GUI mode or a JSON-output mode so it can be scripted for automated evaluation.

## Key Files (to create/modify)
- `demo/emotion_demo.py`
- `pyproject.toml` — ensure `demo` optional-dependencies include the UI framework (e.g. streamlit).

## Acceptance Criteria
- [ ] `python demo/emotion_demo.py` runs on a Linux PC with camera + mic (or shows a clear "no hardware" message).
- [ ] UI shows face, voice, overall, trend, confidence, and transcript (if ASR enabled).
- [ ] UI works headless/JSON-output mode for scripted evaluation.
- [ ] Graceful handling of missing camera/microphone.
- [ ] Uses only the public API; signature unchanged.

## Dependencies
- TASK_MEE_001 (repo/API), TASK_MEE_004 (vision), TASK_MEE_005 (voice), TASK_MEE_006 (fusion), TASK_MEE_007 (trend).

## Notes / Constraints
- Purpose is technical demonstration only; do not invest in production UI polish.
- "Affective-state estimation"; never "reads true emotion."
