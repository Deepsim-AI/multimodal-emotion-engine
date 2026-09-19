# TASK_REQUEST — TASK_MEE_006: Multimodal Emotion Fusion

**Task ID:** TASK_MEE_006
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Combine vision + voice estimates into a unified affective-state estimate with a transparent, deterministic fusion strategy and explicit conflict reporting.

## Detailed Requirements
- Implement `mee/fusion/emotion_fusion.py` with the V1 strategy: configurable weighted combination (default vision 40% / voice 40% / context 20%; context absent → use vision+voice only). Weights are **engineering parameters**, not scientific truth.
- Wire fusion into `process()` so `overall` reflects it, **without changing the public signature**.
- Detect and **preserve disagreement**: when vision and voice strongly disagree, set `overall.conflict=true` and reduce/reflect lower overall confidence (see Test E in the plan). Do not silently hide conflict.
- Support single-modality input (only face, or only voice) returning a sensible overall.
- Design for a future learned-fusion model behind the same interface.

## Key Files (to create/modify)
- `mee/fusion/emotion_fusion.py`
- `mee/api/engine.py` — update fusion usage in `process()` only (mark `TASK_MEE_006`)

## Acceptance Criteria
- [ ] Vision + voice both present → `overall` emotion + confidence computed from weighted fusion.
- [ ] Conflicting modalities → `overall.conflict=true` with reduced confidence (per the plan's Test E example shape).
- [ ] Single-modality input handled (no crash; overall from the available source).
- [ ] Fusion weights configurable; easy to swap for a learned model later.
- [ ] Public API signature unchanged; existing tests pass.
- [ ] Unit tests added (`tests/test_fusion.py`).

## Dependencies
- TASK_MEE_004 (vision engine), TASK_MEE_005 (voice engine).

## Notes / Constraints
- Fusion weights are tuning parameters. Use "affective-state estimation"; never "reads true emotion."
- MEE stays independent of the AI Companion book.
