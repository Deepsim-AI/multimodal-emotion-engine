# Implementation Instructions — TASK_MEE_009

**Task ID:** TASK_MEE_009  
**Phase:** Phase 5 (End-to-End Validation)  
**Assignee:** Implementer 💻 (ollama/qwen3.8:27b)  
**Status:** Ready for Build  

---

## What to Build

Implement end-to-end validation of the full MEE pipeline using **synthetic channel inputs**. The harness exercises all five test scenarios against `EmotionEngine.process()`, validating fusion logic, conflict detection, and trend analysis — without requiring any live hardware or model downloads.

## How to Use the Plan

Read: `docs/development/reports/TASK_MEE_009/CTO_PLAN.md` (the full CTO plan with rationale, subtask breakdown, code references, and constraints).

**Key decision:** Patch `_infer_vision()` and `_infer_voice()` via monkey-patch so `EmotionEngine.process()` takes the full code path including history recording and trend computation. This is true integration testing — not calling internal methods directly.

## Files to Create

| # | File | Action | Notes |
|---|------|--------|-------|
| 1 | `tools/evaluate_scenarios.py` | CREATE | Runnable harness; prints results table + JSON |
| 2 | `tests/scenario_data.py` | CREATE | Scenario definitions as dataclasses |
| 3 | `tests/test_scenarios.py` | CREATE | Pytest suite (5 test classes, ~1 test per scenario) |
| 4 | `docs/TEST_PROTOCOL.md` | CREATE | Evaluation methodology + expected results |

**Do NOT modify any existing files.** No changes to engine.py, fusion, state, or any other existing code.

## Key Code References (for the Implementer)

When you need to understand what `EmotionEngine.process()` produces or what channel dicts look like, read these EXACT locations:

| What to understand | File | Lines |
|---|---|---|
| `process()` return dict shape | `mee/api/engine.py` | L130–L155 |
| `_MEEFaceResult.to_dict()` output | `mee/api/engine.py` | L43–L56 |
| `_fuse()` returns `{emotion, confidence, conflict}` | `mee/api/engine.py` | L178–L192 |
| Channel dict format (what _infer_vision/_infer_voice produce) | `mee/api/engine.py` | L108–L126 (vision) and L134–L148 (voice) |
| `EmotionFusion.compute_fusion()` signature | `mee/fusion/emotion_fusion.py` | L82–L113 |

## Implementation Steps

### Step 1: Scenario Data (`tests/scenario_data.py`)

Create the data module first. This is pure data — no logic, just dataclasses and a list of scenarios. Follow CTO_PLAN.md Subtask 2 exactly for scenario definitions. Each scenario contains a list of `ScenarioStep` objects where each step has optional face and voice emotion/confidence fields.

### Step 2: Test File (`tests/test_scenarios.py`)

For each scenario, create a test class. Inside each test method:
1. Create `EmotionEngine()`
2. Monkey-patch `_infer_vision` to return `_MEEFaceResult(emotion=..., confidence=..., scores=..., has_face=...)` from the step's data
3. Monkey-patch `_infer_voice` to return the voice dict from the step's data
4. Call `engine.process(video_frame=synthetic_frame, audio=synthetic_audio)` — you CAN create tiny synthetic ndarrays (e.g., 10×10×3 uint8 for frame, [0.0]*640 for audio) or patch to return early. The key is that `_infer_vision`/`_infer_voice` return predetermined values.
5. Assert against expected values (emotion, conflict, trend)

### Step 3: Evaluation Harness (`tools/evaluate_scenarios.py`)

Create a standalone script (not pytest). It should:
1. Import `SCENARIOS` from `tests.scenario_data`
2. For each scenario, create engine, run all steps via patched process calls
3. Collect results
4. At end, print a markdown table with columns: Scenario | Emotion | Confidence | Conflict | Trend | Latency_ms (avg)
5. Print JSON dump of all results

### Step 4: Test Protocol (`docs/TEST_PROTOCOL.md`)

Document the evaluation methodology, expected results per scenario, pass/fail criteria, and known limitations. This is documentation — no code.

## Test Results Target

All tests must pass: `python3 -m pytest tests/test_scenarios.py -v`  
Full suite must still pass: `python3 -m pytest tests/ -q` (should still show 68+5 passed)

## Deliverables Report

Produce a lightweight report in the task directory (≤200 lines):
```
TASK_MEE_009 Implementation Status
=====================================
Subtask 1: `tools/evaluate_scenarios.py` — [APPLIED | FAILED]
- File: tools/evaluate_scenarios.py, ~N lines
- Change: Runnable harness with synthetic data
...
Subtask 2: `tests/scenario_data.py` — [APPLIED | FAILED]
...
Subtask 3: `tests/test_scenarios.py` — [APPLIED | FAILED]
...
Subtask 4: `docs/TEST_PROTOCOL.md` — [APPLIED | FAILED]
...
Test Results: X passed, Y failed in Zs

Key decisions made during implementation:
- (document any deviations from the plan)

Known issues / notes for Reviewer:
- (any observations that may be relevant for review)
```

## Important Constraints

1. **No model loading or inference** — this is pipeline integration testing, not model validation
2. **No live hardware** — synthetic inputs only
3. **Monkey-patch approach**: You may monkey-patch `engine._infer_vision` and `engine._infer_voice` to return predetermined results. This exercises the full `process()` path (including history recording and trend computation) while avoiding actual model inference.
4. **Synthetic frame/audio inputs**: Create trivial arrays — `np.zeros((10,10,3), dtype=np.uint8)` for video_frame and `np.zeros(640, dtype=np.float32)` for audio are sufficient since the patched methods return early anyway.
5. **Follow the CTO plan exactly** — do not invent new scenarios or change existing ones without asking the CTO first.

## Gate Entry Verification (AGENTS.md Rule 7)

Before starting work, verify all artifacts from prior gates exist:
- ✅ TASK_REQUEST.md exists in this directory
- ✅ CTO_PLAN.md exists in this directory
If either is missing, halt and report to the CTO — do not proceed.

## Delivery

When complete, write your implementation status report to `IMPLEMENTATION_REPORT.md` in this task directory (overwrite any placeholder). The Reviewer will read that file for their assessment.

---

## GATE ENTRY CHECK — VERIFY BEFORE STARTING

Per AGENTS.md Rule 7, verify all prior gate artifacts exist:

- [ ] TASK_REQUEST.md exists ✅ (verified)
- [ ] CTO_PLAN.md exists ✅ (verified)

If either is missing, STOP and return to the CTO — do not proceed.

## IMPLEMENTATION PLAN SUMMARY

### What You're Building

End-to-end validation of the full MEE pipeline using synthetic inputs that mimic what `VisionProcessor.process_frame()` and `VoiceProcessor.process()` would return. This validates:
- Fusion logic with all channel combinations (vision-only, voice-only, both, neither)
- Conflict detection when modalities disagree
- Trend analysis over temporal sequences
- Public API contract preservation

### Five Test Scenarios

| Scenario | Description | Key Assertions |
|----------|-------------|---------------|
| A: Neutral | Vision-only neutral face | emotion=neutral, conflict=False, trend=stable |
| B: Happy | Both agree on happy | emotion=happy, conflict=False, trend=stable |
| C: Sad | Vision-only sad face | emotion=sad, conflict=False, trend=stable |
| D: Frustrated | Conflicting (happy face + angry voice) | **conflict=True**, higher-confidence label wins |
| E: Cross-over | Transitioning happy→neutral→sad | Trend shifts through stable→unstable→declining |

### Four Deliverable Files

1. **`tools/evaluate_scenarios.py`** — Runnable harness (not pytest): executes all 5 scenarios, prints markdown table + JSON results
2. **`tests/scenario_data.py`** — Pure data: `ScenarioStep` and `Scenario` dataclasses + `SCENARIOS` list
3. **`tests/test_scenarios.py`** — Pytest suite: one test class per scenario (~5 tests total)
4. **`docs/TEST_PROTOCOL.md`** — Documentation: methodology, expected results, pass/fail criteria, limitations

### How to Exercise the Engine (Key Technical Note)

The engine's `process(video_frame, audio)` calls `_infer_vision()` and `_infer_voice()` internally. For synthetic testing:

```python
engine = EmotionEngine()

# Monkey-patch before calling process():
engine._infer_vision = lambda frame=None: _MEEFaceResult(
    emotion="happy", confidence=0.9, scores={"happy": 0.9}, has_face=True
)
engine._infer_voice = lambda audio=None: {
    "emotion": "happy", "confidence": 0.85, "scores": {"happy": 0.85}
}

# Now call process with trivial inputs — patched methods short-circuit:
import numpy as np
result = engine.process(
    video_frame=np.zeros((10, 10, 3), dtype=np.uint8),
    audio=np.zeros(640, dtype=np.float32)
)
# result["overall"] and result["trend"] are populated via the real code path
```

This exercises **the full `process()` code path** including history recording and trend computation — not just calling `_fuse()` directly.

### Source References (Exact File/Symbol/Lines)

When you need to understand shapes or contracts, read these EXACT locations:

| What | File | Lines |
|------|------|-------|
| `process()` return dict shape | `mee/api/engine.py` | L130–L155 |
| `_MEEFaceResult.to_dict()` | `mee/api/engine.py` | L43–L56 |
| `_fuse()` return structure | `mee/api/engine.py` | L178–L192 |
| Vision inference contract | `mee/api/engine.py` | L108–L126 |
| Voice inference contract | `mee/api/engine.py` | L134–L148 |

## CONSTRAINTS (MANDATORY)

1. **No existing file modifications** — only create new files
2. **All 5 scenarios must be implemented** — no shortcuts
3. **Test dataclasses go in `tests/scenario_data.py`** — importable from both harness and tests
4. **Monkey-patch approach** — exercises real engine code path, not just unit-level components
5. **Verify full test suite passes** after changes: `python3 -m pytest tests/ -q` must show 73+ passed

## DELIVERY REQUIREMENT

When complete, write an implementation status report to `IMPLEMENTATION_REPORT.md` in this task directory (overwrite any placeholder). The Reviewer will use this for their assessment. Keep it under 200 lines with:
- Per-file deliverable status (APPLIED/FAILED per file)
- Test results summary
- Key decisions made during implementation
- Known issues or observations for the reviewer

## IMPORTANT — Read the Full CTO Plan Before Starting

The `CTO_PLAN.md` file in this directory contains additional rationale, design context, and constraints. Read it fully before beginning implementation. The instructions above are a condensed summary; the full plan has details you'll need.
