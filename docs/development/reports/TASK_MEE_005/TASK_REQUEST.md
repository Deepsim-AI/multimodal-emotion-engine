# TASK_REQUEST — TASK_MEE_005: Voice Emotion Engine

**Task ID:** TASK_MEE_005
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Implement the voice module so `EmotionEngine.process(audio=...)` performs **acoustic emotion estimation** (not transcription). Extract acoustic features (pitch, energy, speaking rate, pauses, MFCC, spectral) and classify voice emotion via the approved voice model.

## Detailed Requirements
- Implement `mee/voice/recorder.py` (audio capture, optional), `mee/voice/features.py` (acoustic feature extraction), `mee/voice/emotion_model.py` (acoustic classification), `mee/voice/processor.py` (pipeline).
- Wire into `mee/api/engine.py` `_infer_voice()` **without changing `process()` or `MEEConfig`**.
- Return per call: `emotion`, `confidence`, optional `scores`. Handle **no-audio** gracefully (return None / no voice result, not an error).
- Distinguish **acoustic emotion from speech content**: the transcript is **not** the voice-emotion signal. ASR may exist as a side-channel but must not drive the voice-emotion branch.
- Use the CTO-recommended voice model (TASK_MEE_003). Graceful fallback when the package is missing.
- Support a small initial label set (neutral, happy, sad, angry, frustrated, excited); final labels follow the chosen model (documented).

## Key Files (to create/modify)
- `mee/voice/recorder.py`, `mee/voice/features.py`, `mee/voice/emotion_model.py`, `mee/voice/processor.py`
- `mee/api/engine.py` — update `_infer_voice()` only (mark `TASK_MEE_005`)

## Acceptance Criteria
- [ ] Given audio, returns voice emotion + confidence (+ scores); works with at least one backend.
- [ ] Given None audio, returns no voice result without error.
- [ ] Acoustic features are extracted and used; transcript not used as the emotion signal.
- [ ] Graceful degradation when backend missing.
- [ ] Public API signature unchanged; existing tests pass.
- [ ] Unit tests added (`tests/test_voice.py`).

## Dependencies
- TASK_MEE_001 (repo + API stub), TASK_MEE_003 (approved voice model). Parallelizable with TASK_MEE_004.

## Notes / Constraints
- "Voice (acoustic) emotion estimation"; never "reads true emotion."
- MEE stays independent of the AI Companion book.
