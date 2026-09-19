# TASK_REQUEST — TASK_MEE_007: Temporal User State

**Task ID:** TASK_MEE_007
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Track affective state over time and estimate a trend (increasing / stable / decreasing / unknown) so downstream consumers can respond to **sustained or changing** state, not just single frames.

## Detailed Requirements
- Implement `mee/state/history.py` (sliding-window history buffer of per-frame estimates + timestamps).
- Implement `mee/state/estimator.py` (trend estimation over the window: increasing/stable/decreasing/unknown, with configurable window + min samples).
- Wire into `process()` so `trend` reflects current state + history, **without changing the public signature**.
- Handle missing/None frames and missing data gracefully (no crash, no crash on short histories).
- Smooth/filter as reasonable; document the approach.

## Key Files (to create/modify)
- `mee/state/history.py`, `mee/state/estimator.py`
- `mee/api/engine.py` — update `_compute_trend()` / history usage only (mark `TASK_MEE_007`)

## Acceptance Criteria
- [ ] Given a sequence of same emotion estimates → trend "stable".
- [ ] Given rising emotion intensity over time → trend "increasing" (and analogous for decreasing).
- [ ] Short/empty history → trend "unknown" (no error).
- [ ] Window size and min samples configurable.
- [ ] Public API signature unchanged; existing tests pass.
- [ ] Unit tests added (`tests/test_state.py`).

## Dependencies
- TASK_MEE_006 (fusion → `overall` emotion is the input to trend estimation).

## Notes / Constraints
- Trend estimation is probabilistic; document limitations. "Affective-state estimation"; never "reads true emotion."
- MEE stays independent of the AI Companion book.
