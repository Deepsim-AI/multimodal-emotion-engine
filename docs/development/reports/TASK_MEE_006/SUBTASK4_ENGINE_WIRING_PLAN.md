# TASK_MEE_006 — Subtask 4: Engine Wiring Plan

**Scope**: Wire `EmotionFusion` + `EmotionHistory` + `EmotionEstimator` into `EmotionEngine.process()` — ONE file change.

## What to Change (exact file, exact methods)

### File: `mee/api/engine.py`

**Three stubs to replace:**

#### 1. `_fuse(self, face, voice)` → delegate to `EmotionFusion.compute_fusion(face, voice, config)`

- Import: `from ..fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig`
- Build `EmotionFusionConfig(vision_weight=vw, voice_weight=vw, ...)` from `self.config.fusion_weights`
- Call: `result = EmotionFusion.compute_fusion(face, voice, fusion_config)`
- Return result dict (keys already match: emotion, confidence, conflict)

#### 2. `_compute_trend(emotion)` → use EmotionHistory + EmotionEstimator

- Initialize `self._emotion_history` as `EmotionHistory(window=30)` in `__init__`
- In each `process()` call, append to history: `self._emotion_history.append({...})`
- Call: `trend = self._emotion_history.analyze_trend(self.config.trend_min_samples)`
- Return trend result

#### 3. `__init__` → add `_emotion_history` field

```python
self._emotion_history = EmotionHistory()
```

### File: `mee/__init__.py` (public API export)

Add exports so consumers can import:
```python
from .fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig
from .state.history import EmotionHistory
from .state.estimator import EmotionEstimator
```

### Key constraint for the Implementer

- **This is a focused single-file change** (engine.py) plus two minor additions (__init__.py exports)
- **Do NOT modify any other files** — fusion/state code is already written and tested
- **Tests to verify**: `python -m pytest tests/test_fusion.py -v` should still pass (68 tests, 0 failures)

## Implementation Steps

1. Add imports at top of engine.py:
   ```python
   from ..fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig
   from ..state.history import EmotionHistory
   from ..state.estimator import EmotionEstimator
   ```

2. In `EmotionEngine.__init__`, add:
   ```python
   self._emotion_history = EmotionHistory()
   ```

3. Replace `_fuse` body — delegate to `EmotionFusion.compute_fusion()`

4. Replace `_compute_trend` body — use `self._emotion_history.analyze_trend()`

5. In `process()`, after computing overall, append to history:
   ```python
   self._emotion_history.append({
       "emotion": overall["emotion"],
       "confidence": overall["confidence"],
   })
   ```

## Acceptance Criteria

- All 68 tests pass (42 fusion + existing vision/voice regression)
- `EmotionEngine.process()` returns realistic trend values (not always "unknown")
- No regressions to any existing functionality
