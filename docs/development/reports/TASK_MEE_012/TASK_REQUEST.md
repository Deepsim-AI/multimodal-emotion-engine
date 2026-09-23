# TASK_REQUEST — TASK_MEE_012: Jetson Performance Benchmarking for Replaced Vision Models

**Task ID:** TASK_MEE_012
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Measure and compare the **real-world performance** of the new commercially-safe vision pipeline (post-MEE_011) on the Jetson AGX Orin platform. This validates that the EmotiEffLib-based vision stack meets accuracy, latency, and resource requirements for commercial robotics deployment.

This task was **deferred from TASK_MEE_011** (both by the CTO plan §4 and the implementation report §9): MEE_011 replaced the production vision pipeline but deferred the Jetson performance benchmark as explicitly out of scope for that task's correctness gate. MEE_012 picks up the benchmark as its primary deliverable.

## Detailed Requirements
- **Phase A — Stage-level latency:** For each vision stage (detection → alignment → expression), measure mean/P95/P99 latency over a frame batch, memory footprint at rest and active, and CPU utilization.
- **Phase B — End-to-end pipeline:** Run the full `EmotionEngine.process(frame, audio)` pipeline for a sustained continuous stream; measure frame throughput (fps) and confirm memory stability (no leaks) over an extended run.
- **Phase C — Accuracy baseline:** Record EmotiEffLib accuracy/confidence distribution on the existing known scenarios (`tests/test_scenarios.py`), and compare against the documented MEE_011 baseline (~63–67% AffectNet val from the EmotiEffLib paper).
- **Deliverables:**
  - A runnable benchmark harness (`tools/bench_vision_models.py` extension or `tools/bench_mee_012.py`).
  - `docs/development/reports/TASK_MEE_012/BENCHMARK_RESULTS.md` — tabulated latency/memory/accuracy results with pass/fail against acceptance criteria.
  - Update `docs/development/reports/TASK_MEE_012/CTO_PLAN.md` as needed.

## Acceptance Criteria
- [ ] Detection latency < 50ms/frame (mean)
- [ ] Expression inference latency < 30ms/frame (mean)
- [ ] Full pipeline sustained throughput ≥ 20 FPS
- [ ] Memory stable over the extended run (no drift > 5%)
- [ ] Accuracy within ±5% of the documented MEE_011 baseline

## Dependencies
- TASK_MEE_011 (vision pipeline replacement complete, G4 approved, closed 2026-09-23)
- All prior MEE tasks complete (see PROJECT_STATUS.md)

## Notes / Constraints
- MEE remains an independent capability, not tied to the AI Companion book or any specific robot.
- "Affective-state estimation"; never "reads true emotion."
- Benchmark on the Jetson AGX Orin (aarch64). On non-Jetson hosts, run what's possible and clearly mark Jetson-specific measurements as deferred/unverified.
- Do not modify the production vision pipeline to "improve" benchmark numbers — report what you measure. If results miss targets, that is a finding, not a failure.
