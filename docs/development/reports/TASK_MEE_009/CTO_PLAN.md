# CTO Plan — TASK_MEE_009: End-to-End Validation

**Task ID:** TASK_MEE_009  
**Status:** Awaiting user approval → awaiting Implementer build  
**Date:** 2026-09-21  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)

---

## Executive Summary

TASK_MEE_009 validates the full pipeline end-to-end using **synthetic input channels** (no live camera/mic required). The harness exercises all five standardized test scenarios against the complete stack — vision path, voice path, fusion, and trend analysis — with structured output.

**Why synthetic data (not live hardware):**  
This system has no insightface or librosa/sounddevice installed locally. Live inference is impossible without installing heavy dependencies. Synthesizing channel dicts that match the VisionProcessor/VoiceProcessor output contract lets us exercise every path in the stack with real `EmotionEngine.process()` calls, which is exactly what E2E validation needs: not "does hardware work" (that's MEE_010), but "does the pipeline logic connect correctly?"

---

## Subtask Breakdown

### Subtask 1 — Evaluation Harness Script (`evaluate_scenarios.py`)

**File:** `tools/evaluate_scenarios.py` (create)  
**Purpose:** Runnable script that executes all five test scenarios and prints structured results.

**Changes needed:**
- Import `EmotionEngine` from `mee`
- Import scenario definitions from `tests/scenario_data.py`
- For each scenario, call `engine.process(video_frame=..., audio=...)` with synthetic inputs
- Collect `face`, `voice`, `overall`, `trend`, `latency_ms` at each step
- After all steps, print a markdown results table + JSON dump

**Key implementation:**
```python
# Line ~5: import structure
from mee.api.engine import EmotionEngine, MEEConfig
from tests.scenario_data import SCENARIOS

# Line ~12: engine creation with default config
engine = EmotionEngine(config=MEEConfig())

# Line ~20: per-scenario loop calling engine.process()
# Each call uses synthetic dicts matching face/voice output format
```

### Subtask 2 — Scenario Data Module (`tests/scenario_data.py`)

**File:** `tests/scenario_data.py` (create)  
**Purpose:** Defines all five test scenarios as structured data, including step-by-step input sequences.

**Scenario definitions (synthetic inputs, not live capture):**

#### Test A: Neutral
- 10 steps, each with `face={"emotion": "neutral", "confidence": 0.85}` + `voice=None`
- Expected: `overall.conflict=False`, trend="stable", emotion="neutral"
- Rationale: Tests the single-modality (vision-only) path through full pipeline

#### Test B: Happy
- 10 steps, each with `face={"emotion": "happy", "confidence": 0.9}` + `voice={"emotion": "happy", "confidence": 0.85, "scores": {}}`
- Expected: `overall.conflict=False`, trend="stable", emotion="happy"
- Rationale: Tests agreement path with both channels

#### Test C: Sad
- 10 steps, each with `face={"emotion": "sad", "confidence": 0.8}` + `voice=None`
- Expected: `overall.conflict=False`, trend="stable", emotion="sad"
- Rationale: Tests single-modality (vision-only) for negative emotion

#### Test D: Frustrated (conflicting modalities)
- 10 steps with alternating/conflicting pairs:
  - Step 0–4: face=`happy` (confidence 0.85), voice=`angry` (confidence 0.75)
  - Step 5–9: face=`happy` (confidence 0.7), voice=`sad` (confidence 0.65)
- Expected: `overall.conflict=True` throughout, higher-confidence label wins
- Rationale: **Core conflict test** — verifies fusion preserves disagreement

#### Test E: Cross-over (emotion shift over time)
- 10 steps transitioning from happy → sad:
  - Steps 0–3: face=`happy` (confidence 0.8), voice=`happy` (confidence 0.75)
  - Steps 4–6: face=`neutral` (confidence 0.4), voice=`neutral` (confidence 0.4)  
  - Steps 7–9: face=`sad` (confidence 0.8), voice=`sad` (confidence 0.75)
- Expected: trend transitions from "stable" → "unstable" (at crossover) → "declining"

**Data structure per scenario step:**
```python
@dataclass
class ScenarioStep:
    face_emotion: Optional[str] = None
    face_confidence: float = 0.0
    voice_emotion: Optional[str] = None  
    voice_confidence: float = 0.0

@dataclass
class Scenario:
    name: str              # "A", "B", "C", "D", "E"
    label: str             # "Neutral", "Happy", "Sad", "Frustrated", "Cross-over"
    steps: List[ScenarioStep]
    expected_conflict: bool     # whether overall.conflict should be True
    expected_emotion: str       # dominant emotion across the sequence
    expected_trend: str         # final trend after all steps
```

### Subtask 3 — Test File (`tests/test_scenarios.py`)

**File:** `tests/test_scenarios.py` (create)  
**Purpose:** Pytest-compatible unit tests that validate each scenario's output structure and key assertions.

**Structure (mirror the existing test_fusion.py style):**
```python
class TestScenarioA_Neutral:
    def test_overall_emotion_is_neutral(self): ...
    def test_no_conflict(self): ...
    def test_trend_becomes_stable(self): ...
    def test_latency_under_100ms(self): ...  # sanity

class TestScenarioB_Happy:
    def test_overall_emotion_is_happy(self): ...
    def test_no_conflict(self): ...
    def test_trend_becomes_stable(self): ...

class TestScenarioC_Sad:
    def test_overall_emotion_is_sad(self): ...
    def test_no_conflict(self): ...
    def test_trend_becomes_stable(self): ...

class TestScenarioD_Frustrated_Conflict:
    def test_conflict_is_true(self): ...     # KEY assertion
    def test_higher_confidence_label_wins(self): ...
    def test_trend_becomes_unstable_or_declining(self): ...

class TestScenarioE_Crossover:
    def test_emotion_shifts_to_sad(self): ...
    def test_trend_transition_stable_unstable_declining(self): ...
```

**Each test creates a fresh `EmotionEngine()` and calls `process()` with the scenario's synthetic inputs.** No mocking — this is true integration testing against the real engine.

### Subtask 4 — Test Protocol Document (`docs/TEST_PROTOCOL.md`)

**File:** `docs/TEST_PROTOCOL.md` (create)  
**Purpose:** Documents the evaluation methodology, expected results for each scenario, and known limitations.

**Contents:**
1. **Methodology:** Synthetic channel data vs. live hardware; what this validates and doesn't validate
2. **Scenario descriptions** (full text for each of A–E)
3. **Expected results table** with exact emotion/conflict/trend per scenario
4. **Pass/fail criteria** — what constitutes a pass for each test
5. **Known limitations:**
   - No real inference testing (models not loaded on this system)
   - Latency measurements are meaningful only relative to local hardware, not production targets
   - Fusion logic is tested (via unit tests in MEE_006), this validates the glue/wiring

---

## Acceptance Criteria Mapping

| Requirement | How Validated | Test Location |
|---|---|---|
| All 5 scenarios produce structured output | `evaluate_scenarios.py` prints table + JSON | Subtask 1 |
| Vision exercised in A, C, E | Scenario input contains face dict with emotion/conidence/scores | Subtask 2 |
| Voice exercised in B, D, E | Scenario input contains voice dict | Subtask 2 |
| Fusion exercises conflict path | Test D steps with opposing face/voice labels | Subtask 3::TestScenarioD_Frustrated_Conflict.test_conflict_is_true |
| Trend analysis works over time | E scenario transitions tracked across 10 steps | Subtask 3::TestScenarioE_Crossover |
| No crashes on any input | All `process()` calls in try/except during harness execution | Subtask 1 |

---

## Key Code References (R-SI-2: Exact File/Symbol/Lines)

The Implementer needs to know where the engine currently lives and what its interface looks like:

| Symbol | File | Lines | Notes |
|---|---|---|---|
| `EmotionEngine` class | `mee/api/engine.py` | L84–L219 | All logic is here; no new methods needed |
| `process()` return dict | `mee/api/engine.py:L130-155` | Keys: face, voice, overall, trend, latency_ms | Contract — harness must assert all present |
| `overall` keys | `mee/api/engine.py:L150-152` | `{emotion, confidence, conflict}` (from `_fuse`) | Fusion output shape |
| `MEEConfig` defaults | `mee/api/engine.py:L16-24` | All defaults are fine for synthetic testing | No config changes needed |
| `EmotionFusion.compute_fusion()` | `mee/fusion/emotion_fusion.py:L82-113` | Takes `vision=None, voice=None`; never raises | What the engine calls internally |
| `_MEEFaceResult.to_dict()` | `mee/api/engine.py:L43-56` | Returns dict with has_face/emotion/confidence/scores | What gets passed to fusion via `_fuse` |

---

## Constraints

1. **No live hardware required** — all inputs are synthetic dicts matching the processor output contract
2. **No model loading** — harness exercises the engine's `process()` path which in real use would invoke VisionProcessor/VoiceProcessor; for validation, we bypass that by directly calling `_fuse`-equivalent logic through the process pipeline
3. **Do NOT modify any existing files** except: create new files listed above and add to `pyproject.toml` if a new optional dependency is needed (none expected)
4. **Keep the test file self-contained** — no external fixtures, no conftest.py changes
5. **All scenario data must be in `tests/scenario_data.py`** so it's importable from both `evaluate_scenarios.py` and `test_scenarios.py`

---

## Delivery Checklist

| Deliverable | Location | Status |
|---|---|---|
| `tools/evaluate_scenarios.py` | CREATE | Pending |
| `tests/scenario_data.py` | CREATE | Pending |
| `tests/test_scenarios.py` | CREATE | Pending |
| `docs/TEST_PROTOCOL.md` | CREATE | Pending |
| Tests pass (all 5 scenarios) | `pytest tests/test_scenarios.py` | Pending |
| Harness runnable: `python tools/evaluate_scenarios.py` | Shell | Pending |

---

## Risks & Notes

1. **Engine doesn't accept raw channel dicts directly** — it expects `video_frame=ndarray, audio=ndarray` and runs `_infer_vision()`/_infer_voice() internally. For synthetic testing, the harness should either:
   - A) Patch `_infer_vision`/`_infer_voice` to return predetermined results (cleanest), or
   - B) Call `EmotionEngine._fuse()` directly with channel dicts (shortcuts the full path)
   
   **CTO recommendation: Option A.** Patching `_infer_vision` and `_infer_voice` via monkey-patch exercises the full `process()` code path including history recording, trend computation, and latency measurement. This is true E2E validation.

2. **Conflict threshold tuning** — The shipped `EmotionFusionConfig.conflict_threshold` defaults to 0.3 (in `emotion_fusion.py` L64). Test D scenarios use high-confidence opposing labels which will exceed this threshold, ensuring `conflict=True`. This is verified by MEE_006's `TestFusionConflict` tests.

3. **Trend classification** — Uses `analyze_trend()` over the fusion history buffer (ring size from `EmotionFusionConfig.history_window`, default 10). The cross-over scenario (E) exercises this with exactly 10 steps, which matches the window boundary. The trend transition through "stable" → "unstable" → "declining" is expected and testable.
