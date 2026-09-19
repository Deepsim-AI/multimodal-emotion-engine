# TASK_REQUEST — TASK_MEE_009: End-to-End Validation

**Task ID:** TASK_MEE_009
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Run the full pipeline end-to-end using the standardized test scenarios and validate that every stage works together, with measurable confidence/latency. This is the prototype gate before Jetson work.

## Detailed Requirements
- Implement the standardized test scenarios (plan §14): Test A Neutral, Test B Happy, Test C Sad, Test D Frustrated, Test E Conflicting Modalities. Each records vision, voice, fusion, confidence, and latency.
- Test E must exercise **opposing** modalities (positive face + angry/frustrated voice) and confirm the system preserves conflict (`overall.conflict=true`) rather than hiding it.
- Provide a runnable evaluation harness (script) that executes all scenarios and prints a structured results table / JSON.
- Validate every acceptance criterion from TASK_MEE_004–008 is met in the integrated flow.
- Document known limitations and environment requirements.

## Key Files (to create/modify)
- `tests/test_scenarios.py` (or `tests/test_end_to_end.py`)
- `docs/TEST_PROTOCOL.md` (evaluation protocol + expected results)
- Any small glue in `demo/` or a dedicated `evaluate` script.

## Acceptance Criteria
- [ ] All 5 test scenarios run and produce structured output.
- [ ] Vision, voice, fusion, and temporal state all exercised in one end-to-end pass.
- [ ] Test E produces a visible conflict signal.
- [ ] Confidence and latency measured/reported.
- [ ] All prior-task acceptance criteria pass in the integrated flow.
- [ ] Results reproducible from a single command.

## Dependencies
- TASK_MEE_004, 005, 006, 007 (all engine stages implemented and unit-tested).

## Notes / Constraints
- "Affective-state estimation"; never "reads true emotion." Document that outputs are probabilistic estimates.
