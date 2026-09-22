# CTO Plan — TASK_MEE_006: Multimodal Emotion Fusion

**Task ID:** TASK_MEE_006  
**Phase:** Phase 4  
**Date:** 2026-09-20  
**Preceding Tasks:** MEE_004 (Vision Engine), MEE_005 (Voice Engine) — both ✅ G4 Approved  
**Dependencies Met:** Vision + Voice processors exist and are wired into EmotionEngine

---

## 1. Problem Statement

Current `EmotionEngine._fuse()` is a rough stub:
- Uses a simple higher-confidence vote, not weighted fusion
- Does not implement the configurable weights from MEEConfig
- Conflict detection is basic (just label inequality)
- Trend computation is always `"unknown"` — no state tracking

TASK_MEE_006 delivers:
1. `mee/fusion/emotion_fusion.py` — real weighted fusion + conflict detection module
2. `mee/state/history.py` — ring buffer of emotion events
3. `mee/state/estimator.py` — trend analysis over history
4. Wire fusion and state into `EmotionEngine.process()` replacing the stubs
5. Unit tests (`tests/test_fusion.py`)

**Public API signature is NOT changed.** The contract for `process()` return type remains as locked in ARCHITECTURE.md §2.

---

## 2. Implementation Plan

### Subtask 1: Fusion Module — `mee/fusion/emotion_fusion.py`

Create a module with two core components:

**a) `EmotionFusionConfig(dataclass)`** — lightweight fusion config derived from MEEConfig
```python
@dataclass
class EmotionFusionConfig:
    vision_weight: float = 0.5
    voice_weight: float = 0.5
    conflict_threshold: float = 0.5
    
    # Derived properties (computed, not stored)
    @property
    def total_weight(self) -> float:
        return self.vision_weight + self.voice_weight
    
    @property
    def has_conflict(self) -> bool:
        # Only meaningful when vision and voice disagree
        return False  # set by compute_fusion()
```

**b) `EmotionFusion.compute_fusion(face_result, voice_result, config)` → dict**

The fusion algorithm (V1 deterministic weighted approach):

```python
def compute_fusion(face: _MEEFaceResult, voice: dict | None, config: EmotionFusionConfig) -> dict:
    """Return overall emotion dict per MEE API contract."""
    
    # --- Determine available modalities ---
    has_face = face is not None and face.has_face and face.emotion is not None
    has_voice = voice is not None and voice.get("emotion") is not None
    
    if not has_face and not has_voice:
        raise ValueError("Both modalities are None — must supply at least one input")
    
    # --- Build per-modality evidence ---
    face_evidence = {"emotion": face.emotion, "confidence": face.confidence} if has_face else None
    voice_evidence = {"emotion": voice["emotion"], "confidence": voice["confidence"]} if has_voice else None
    
    # --- Single-modality shortcut ---
    if has_face and not has_voice:
        return {
            "emotion": face.emotion,
            "confidence": face.confidence,
            "conflict": False,
        }
    if has_voice and not has_face:
        return {
            "emotion": voice["emotion"],
            "confidence": voice["confidence"],
            "conflict": False,
        }
    
    # --- Both present — weighted fusion ---
    total_w = config.vision_weight + config.voice_weight
    
    # Normalize weights if they don't sum to 1.0
    norm_v = config.vision_weight / total_w if total_w > 0 else 0.5
    norm_vc = config.voice_weight / total_w if total_w > 0 else 0.5
    
    # Weighted confidence for each modality's prediction
    face_conf = face.confidence * norm_v
    voice_conf = voice["confidence"] * norm_vc
    
    # Conflict detection: different labels + both above threshold
    conflict = (face.emotion != voice["emotion"]) and \
               face.confidence >= config.conflict_threshold and \
               voice["confidence"] >= config.conflict_threshold
    
    if conflict:
        # When modalities disagree: reduce overall confidence as a penalty
        # Weighted average of confidences, dampened by conflict factor
        combined_conf = 0.5 * (face_conf + voice_conf)  # reduce to mean under conflict
        # Pick the higher-confidence modality as the label source
        best_emotion = face.emotion if face_conf >= voice_conf else voice["emotion"]
    else:
        # Agreement or low confidence — weighted vote by confidence*weight
        combined_conf = max(face_conf, voice_conf)  # conservative: take the stronger signal
        best_emotion = face.emotion if face_conf >= voice_conf else voice["emotion"]
    
    return {
        "emotion": best_emotion,
        "confidence": round(combined_conf, 4),
        "conflict": conflict,
    }
```

**Label normalization:** The MEE fixed vocabulary (neutral/happy/sad/angry/frustrated/surprised/fearful/disgust) must be used. If a model returns native labels outside this set (e.g., SpeechBrain's `neu`/`hap`), they are mapped at the fusion layer before comparison. Mapping table:

```
neutral → neutral
neu → neutral
happy → happy
hap → happy  
sad → sad
angry → angry
frustrated → frustrated
surprised → surprised
fearful → fearful
disgust → disgust
disgusted → disgust
```

### Subtask 2: State History — `mee/state/history.py`

Create a ring buffer for tracking emotion events over time.

```python
from collections import deque

@dataclass
class EmotionEvent:
    """Single-frame emotion event."""
    timestamp: float          # perf_counter value at capture
    emotion: str
    confidence: float
    face_emotion: str | None = None  # source modality labels (if both available)
    voice_emotion: str | None = None
    conflict: bool = False

class EmotionHistory:
    """Ring buffer of emotion events. Thread-safe for single-writer."""
    
    def __init__(self, maxlen: int = 30):
        self._buffer: deque[EmotionEvent] = deque(maxlen=maxlen)
        self._maxlen = maxlen
    
    def append(self, event: EmotionEvent):
        self._buffer.append(event)
    
    def get_events(self) -> list[EmotionEvent]:
        return list(self._buffer)
    
    @property
    def size(self) -> int:
        return len(self._buffer)
    
    @property
    def is_sufficient(self) -> bool:
        """Return True if enough samples for trend analysis."""
        return self.size >= 5  # per MEEConfig.trend_min_samples default
    
    def clear(self):
        self._buffer.clear()
```

### Subtask 3: State Estimator — `mee/state/estimator.py`

Trend analysis over the emotion history buffer.

```python
class EmotionEstimator:
    """Compute trend from emotion history."""
    
    TREND_STATES = ("increasing", "stable", "decreasing", "unknown")
    
    def __init__(self, window: int = 30, min_samples: int = 5):
        self._window = window
        self._min_samples = min_samples
    
    def compute_trend(self, history: EmotionHistory) -> str:
        """Determine trend from recent emotion events."""
        if not history.is_sufficient:
            return "unknown"
        
        events = history.get_events()[-self._window:]
        
        # Count last-emotion dominance (simplified heuristic for V1)
        # V2+: use exponential weighted moving average of confidence deltas
        
        if len(events) < 2:
            return "stable"
        
        # Compare first half vs second half of window
        mid = len(events) // 2
        first_half_conf = sum(e.confidence for e in events[:mid]) / mid
        second_half_conf = sum(e.confidence for e in events[mid:]) / (len(events) - mid)
        
        # Use the dominant emotion label's confidence trajectory
        if abs(second_half_conf - first_half_conf) < 0.05:
            return "stable"
        elif second_half_conf > first_half_conf:
            return "increasing"
        else:
            return "decreasing"
```

### Subtask 4: Engine Integration — `mee/api/engine.py` (lines ~1–260)

**File:** `mee/api/engine.py`

Target locations and changes:

| Line Range | Change | Detail |
|---|---|---|
| ~8-9 | Add imports | `from ..fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig; from ..state.history import EmotionHistory, EmotionEvent; from ..state.estimator import EmotionEstimator` |
| ~53-54 | Add instance vars | `self._emotion_history = EmotionHistory(config.trend_window)` and `self._estimator = EmotionEstimator(...)` |
| ~90-98 | Replace `_fuse()` | Call `EmotionFusion.compute_fusion(face, voice, fusion_config)`; record event to history when both modalities present |
| ~106-107 | Replace `_compute_trend()` | Call `self._estimator.compute_trend(self._emotion_history)` |

The `process()` method signature is unchanged — only its internals change. The return dict keys remain: face, voice, overall, trend, latency_ms.

### Subtask 5: Unit Tests — `tests/test_fusion.py`

Test suite covering:

| Test ID | Description |
|---|---|
| A | Both modalities present, agreement → no conflict, weighted result |
| B | Both modalities present, disagreement → conflict=True, reduced confidence |
| C | Only face → overall = face (no conflict) |
| D | Only voice → overall = voice (no conflict) |
| E | Both None → ValueError raised |
| F | Configurable weights produce different results for same inputs |
| G | Label normalization maps SpeechBrain labels correctly |
| H | EmotionHistory ring buffer respects maxlen |
| I | EmotionEstimator computes trend from sufficient events |
| J | Trend = "unknown" with insufficient samples |
| K | Integration: engine.process() produces correct overall when both modalities available |

### Subtask 6: Public API Exports — `mee/fusion/__init__.py` + `mee/state/__init__.py`

- `mee/fusion/__init__.py`: export `EmotionFusion`, `EmotionFusionConfig`
- `mee/state/__init__.py`: export `EmotionHistory`, `EmotionEvent`, `EmotionEstimator`

### Subtask 7: Integration Test — update existing test suite

- Verify all MEE_004 + MEE_005 tests still pass (no regressions)
- New tests in `tests/test_fusion.py` as specified above

---

## 3. Acceptance Criteria

| # | Criterion | Verification |
|---|---|---|
| 1 | Weighted fusion produces correct result per weights | Test A, F |
| 2 | Conflict detected when modalities disagree + both high confidence | Test B |
| 3 | Single-modality input works (no crash) | Test C, D |
| 4 | Both-noise → ValueError | Test E |
| 5 | Weights configurable via MEEConfig.fusion_weights | Test F |
| 6 | Label normalization correct | Test G |
| 7 | Public API unchanged | Integration test K + existing tests |
| 8 | Trend analysis works with sufficient history | Test I |
| 9 | All existing tests still pass | Pre/post diff |

---

## 4. Design Decisions & Rationale

1. **Deterministic weighted fusion for V1.** Learned fusion (neural) is deferred to V2+. The V1 algorithm is transparent and debuggable. Weights are engineering parameters, not scientific constants.

2. **Confidence penalty on conflict.** When modalities disagree with high confidence, the overall confidence is reduced to `0.5 * mean(face_conf, voice_conf)` — reflecting uncertainty rather than hiding it.

3. **Ring buffer over deque.** EmotionHistory wraps deque internally; the dataclass interface makes the API explicit and extensible (can add timestamps, modality labels).

4. **Trend heuristic is conservative for V1.** Simple first-half vs second-half confidence comparison. V2 can add exponential smoothing, label-transition matrices, or a small state-classifier.

5. **No model download.** Fusion and state modules have zero external dependencies — pure Python + standard library. No new pip installs needed.

---

## 5. Files to Create/Modify

| File | Action | Lines (est) |
|---|---|---|
| `mee/fusion/emotion_fusion.py` | **CREATE** | ~80 |
| `mee/fusion/__init__.py` | **CREATE** | ~5 |
| `mee/state/history.py` | **CREATE** | ~40 |
| `mee/state/estimator.py` | **CREATE** | ~35 |
| `mee/state/__init__.py` | **CREATE** | ~10 |
| `mee/api/engine.py` | MODIFY (~line 8) | ~40 lines changed across 3 methods |
| `tests/test_fusion.py` | **CREATE** | ~200 |

---

## 6. Gate Entry Verification Checklist

- [x] MEE_004 (Vision Engine) — G4 Approved, artifacts in TASK_MEE_004/
- [x] MEE_005 (Voice Engine) — G4 Approved, artifacts in TASK_MEE_005/
- [x] Public API contract locked — no changes needed to `process()` signature
- [x] Fusion module directory exists (`mee/fusion/`)
- [x] State module directory exists (`mee/state/`)

---

## 7. Model Selection for Future V2

When adding learned fusion:
- Prefer ONNX-compatible models for Jetson deployment
- Look for multimodal fusion architectures that take face embedding + acoustic features as input
- Maintain the same output interface so `EmotionEngine.process()` doesn't need to change
