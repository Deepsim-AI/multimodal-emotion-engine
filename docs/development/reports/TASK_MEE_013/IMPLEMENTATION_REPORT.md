# TASK_MEE_013 — Implementation Report

**Author:** Implementer 💻 (ollama/qwen3.8:27b)
**Date:** 2026-09-23
**Plan:** `docs/development/reports/TASK_MEE_013/CTO_PLAN.md` (G4 APPROVED, revisions R1–R3 incorporated)
**Predecessor:** TASK_MEE_012 (benchmark findings, committed `5b51bb6`)

---

## 1. Objective

Decouple face-detection frequency from the emotion-pass frequency in the vision pipeline. Detection is the dominant bottleneck on this Jetson host (~1 s/face CPU-only retina-face) while emotion inference is ~50 ms/face. The deliverable is a single additive config knob `detect_every_n_frames` that allows operators to reduce effective detection frequency without changing detection, alignment, or emotion algorithms.

---

## 2. Changes

### File A — `mee/vision/processor.py`

**`VisionProcessor.__init__`** (lines ~71–107):
- New parameter `detect_every_n_frames: int = 1` (final positional slot).
- `ValueError` raised if value < 1 (no silent clamping).
- Cache state fields per G4 revision R1:
  - `_detect_every_n_frames: int` — the validated knob value.
  - `_last_faces: Optional[list[Face]]` — `None` = uninitialized, `[]` = "no face" (R3).
  - `_last_frame_id: int | None` — `id(frame_bgr)` at detection time.
  - `_last_frame_shape: tuple[int, ...] | None` — frame shape at detection time.
  - `_call_counter: int` — mod-n counter.

**`VisionProcessor.process()`** (lines ~109–141):
- New keyword arg `force_detection: bool = False`.
- Fast path: `if self._detect_every_n_frames <= 1: return self._run_once(frame_bgr)` — delegates to the original code path verbatim (no cache consulted).
- Slow path (`n > 1`): increments `_call_counter`; on non-due calls (counter mod n ≠ 1) checks frame identity (`id()`) and shape; if both match the cached detection and `force_detection` is `False`, calls `_build_result(frame_bgr, self._last_faces)` directly. Otherwise re-detects, updates all cache fields, and calls `_build_result()`.
- Cache update on detection: `self._last_faces = faces if faces else []` (R3 — empty list, not `None`).

**`VisionProcessor._run_once()`** (lines ~143–218):
- Contains the original `process()` body unchanged: detect → no-face early return → per-face align/crop → emotion predict → best-face selection → `VisionResult` construction.

**`VisionProcessor._build_result()`** (lines ~222–272):
- Shared helper that performs Stage 2 (align/crop) + Stage 3 (emotion predict) for a given `faces` list, returning a fully-populated `VisionResult`.
- Used by both the `n > 1` slow path (for fresh and cached detections) and implicitly available for the `n == 1` path (though `_run_once` duplicates this for byte-parity).
- Ensures cached results feed downstream stages exactly as fresh detections would.

**`process_frame()`** — unchanged alias, calls `process()`.

### File B — `mee/api/engine.py`

**`MEEConfig`** (line ~34):
- New field: `detect_every_n_frames: Optional[int] = None` — `None` means "use processor default of 1" (backward compatible).

**`EmotionEngine._ensure_vision()`** (line ~103):
- Forwards `detect_every_n_frames=self.config.detect_every_n_frames or 1` to the `VisionProcessor` constructor.

### File C — `tests/test_vision.py`

8 new tests in a dedicated "TASK_MEE_013" section (lines ~245–430):

| Test | Verifies |
|---|---|
| `test_mee013_default_detection_every_call` | `n == 1` (default): 5 process() calls → 5 detect() calls; outputs correct. |
| `test_mee013_decoupling_n3` | `n == 3`: 6 calls on same frame → 2 detect() calls, 6 predict() calls; all outputs identical. |
| `test_mee013_staleness_frame_identity` | Different array object → cache invalidated, re-detection occurs; no-face state on frame B not masked by frame A's cached face. |
| `test_mee013_staleness_shape_change` | Same buffer, different shape (view) → re-detection forced. |
| `test_mee013_noface_state_cached` | `n == 2`: no-face result cached; second call reuses it (detect_calls stays at 1); third call re-detects. |
| `test_mee013_force_detection` | `force_detection=True` bypasses cache → extra detect() call. |
| `test_mee013_validation` | `detect_every_n_frames=0` and `-1` raise `ValueError`. |
| `test_mee013_engine_config_field` | `MEEConfig` exposes the field; default `None`; explicit value `4` accepted. |

Supporting stubs added: `CountingFaceDetector`, `CountingNoFaceDetector`, `CountingEmotionModel`, `SwitchingDetector`.

### File D — `README.md`

Added "Detection frequency (TASK_MEE_013)" subsection under Usage Examples with:
- Use case explanation (CPU-only detection bottleneck).
- Code example with `detect_every_n_frames=4`.
- Backward-compat note (`1` is default).
- Staleness / `force_detection` semantics.
- Thread-safety warning.

---

## 3. Acceptance Criteria Verification

| Criterion | Status | Evidence |
|---|---|---|
| New config field `detect_every_n_frames` exists, defaults to `1` | ✅ | `processor.py` `__init__`; `test_mee013_engine_config_field` |
| Default (`1`): detection runs every call, behavior unchanged | ✅ | `test_mee013_default_detection_every_call`; `_run_once()` = original body |
| `n > 1`: detection runs once, reused for next `n-1` calls, re-runs | ✅ | `test_mee013_decoupling_n3` (6 calls, 2 detections) |
| Reused result feeds alignment + emotion as fresh detection | ✅ | `_build_result()` shared path; `test_mee013_decoupling_n3` output equality |
| Existing tests pass; focused detection-frequency test added | ✅ | Full suite: 94 passed, 2 skipped |
| README/docs describe the knob | ✅ | `README.md` new subsection |

---

## 4. Test Results

**Host:** deepsim (Jetson Orin), Python 3.10.12, numpy 1.26.4

```
tests/test_vision.py:          20 passed, 2 skipped (Jetson-only)
tests/test_fusion.py:          included in combined run
tests/test_scenarios.py:       included in combined run
tests/test_voice.py:           included in combined run
Combined (fusion+scenarios+voice): 94 passed, 2 skipped, 2 warnings
```

No regressions. All 8 new TASK_MEE_013 tests pass.

---

## 5. Files Modified

```
 README.md               |  19 ++++
 mee/api/engine.py       |   3 +
 mee/vision/processor.py | 105 +++++++++++++++++++++-
 tests/test_vision.py    | 228 ++++++++++++++++++++++++++++++++++++++++++++++++
 docs/development/reports/TASK_MEE_013/implementation/COMPLETION_EVIDENCE.md | new
```

No changes to: `deepefflib`, `deepefflib_model`, `alignment.py`, `emotion_model.py`, detector backends — all G1-frozen.

---

## 6. Risks & Notes

- **Stale bbox:** mitigated by frame-identity + shape invalidation and `force_detection=True`.
- **Thread safety:** per-instance cache is not thread-safe; documented in docstring and README.
- **`n == 1` parity:** `_run_once()` is a verbatim copy of the original `process()` body; no new state is read on the default path.
