# TASK_REQUEST — TASK_MEE_003: Voice Emotion Model Evaluation

**Task ID:** TASK_MEE_003
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Research and evaluate candidate **voice/acoustic emotion** models for local, commercial-safe, Jetson-friendly inference. Document a documented recommendation. This is **evaluation/planning output**, not implementation.

## Detailed Requirements
- Evaluate **≥3** candidate voice emotion models. Consider e.g. SpeechBrain RavNet, Wav2Vec 2.0 + emotion head, OpenSMILE + SVM, OpenL3.
- For each candidate, document: **benchmark accuracy** (RAVDESS, IEMOCAP, EMODB, etc.), **model size**, **license**, **local inference** feasibility, and **ONNX/TensorRT-Jetson potential**.
- Fill a comparison table (see below) and issue a single named recommendation with justification + fallback.
- Distinguish **acoustic emotion** from speech content: transcript (ASR) is **not** the voice-emotion signal.
- Record NEEDS-VERIFY items (e.g., specific SpeechBrain checkpoint license declarations).

## Key Files (to create/modify)
- `docs/MODEL_EVALUATION.md` (add/update the voice section; do not overwrite the vision section).
- `docs/development/reports/TASK_MEE_003/MODEL_EVALUATION.md` (copy per convention).

## Acceptance Criteria
- [ ] Comparison table includes all columns: benchmark accuracy, size, license, ONNX/Jetson potential, per model.
- [ ] ≥3 voice candidates evaluated.
- [ ] License analysis explicit (AGPL/NC flagged as commercial blockers; MIT/Apache-2.0 safe).
- [ ] Exactly one voice recommendation named with justification + fallback.
- [ ] NEEDS-VERIFY items listed.

## Dependencies
- TASK_MEE_001 (repo structure + public API stub).
- TASK_MEE_002 (parallelizable; both build on the repo foundation).

## Notes / Constraints
- MEE must remain independent of the AI Companion book.
- Model selection is a **CTO decision**.
- "Voice (acoustic) emotion estimation"; never "reads true emotion."
