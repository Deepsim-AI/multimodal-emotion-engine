# CTO Plan — TASK_MEE_012: Jetson Performance Benchmarking for Replaced Vision Models

**Task ID:** TASK_MEE_012  
**Gate:** G1 — Plan Approval  
**Phase:** Phase 6 / Post-MEE_011 Model Replacement Validation  
**Date:** 2026-09-22  
**Planned By:** CTO / Architect  

---

## 1. Objective

Measure and compare the **real-world performance** of the new commercially-safe vision pipeline on the actual Jetson AGX Orin platform. This validates that the EmotiEffLib-based stack meets accuracy, latency, and resource requirements for commercial robotics deployment.

---

## 2. What Changed (MEE_011 Context)

| Stage | Before MEE_011 | After MEE_011 |
|-------|---------------|---------------|
| **Detection** | InsightFace SCRFD/buffalo_l (~80MB, MIT code + non-comm weights) | retina-face (MIT, no pre-loaded weights) |
| **Alignment** | From buffalo_l landmarks directly | face-alignment (68-point landmarks, ~5MB download) |
| **Expression** | DeepFace FER+ backend (mixed weight licenses) | EmotiEffLib (Apache-2.0 code + weights) |

---

## 3. Benchmark Plan

### Phase A: Latency Measurements

For each stage (detection, alignment, expression), measure:
- **Mean latency** over 100 frames (ms)
- **P95/P99 latencies** (outlier detection)
- **Memory footprint** of each model at rest and active
- **CPU usage** (cores utilized)

### Phase B: End-to-End Pipeline Test

Run full `EmotionEngine.process(frame, audio)` for:
- 10 minutes continuous stream at 30 FPS
- Memory stability (no leaks over time)
- Frame throughput (frames/sec sustained)

### Phase C: Accuracy Baseline Comparison

Compare EmotiEffLib accuracy vs. what the old pipeline achieved:
- Use existing test scenarios (`tests/test_scenarios.py`) on known face/voice inputs
- Record per-class accuracy, confidence distribution

---

## 4. Deliverables

| Artifact | Location | Description |
|----------|----------|-------------|
| Benchmark harness | `tools/bench_vision_models.py` (NEW) | Runs latency tests across model stages |
| Benchmark results | `docs/development/reports/TASK_MEE_012/BENCHMARK_RESULTS.md` | Tabulated results |
| MEE_012 plan | `docs/development/reports/TASK_MEE_012/CTO_PLAN.md` | This file |

---

## 5. Acceptance Criteria

| Criterion | Target | Verification |
|-----------|--------|--------------|
| Detection latency < 50ms/frame (mean) | ≤50ms | bench_results table |
| Expression inference latency < 30ms/frame (mean) | ≤30ms | bench_results table |
| Full pipeline sustained throughput ≥ 20 FPS | ≥20fps | Continuous test |
| Memory stays stable over 10-min run | No drift >5% | Memory graph |
| Accuracy ≥ old baseline within ±5% | Within range | Accuracy comparison |

---

## 6. Gate Alignment

| Gate | Requirement | Status |
|------|-------------|--------|
| G1 | CTO plan with acceptance criteria | ✅ This doc |
| G2 | User approval | ⏳ Pending |
| G3 | Benchmarks run and results verified | ⏸️ Pending |
| G4 | CTO final review of results | ⏸️ Pending |
| G5 | PM closure | ⏸️ Pending |

---
*CTO Plan — TASK_MEE_012 | 2026-09-22*
