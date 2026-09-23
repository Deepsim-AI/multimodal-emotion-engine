# TASK_MEE_013 — Gate G4 Approval (CTO)

**Date:** 2026-09-23
**Approvers:** CTO 🏗️
**Status:** ✅ APPROVED

## Review Summary

I reviewed this plan against the actual source code (`mee/vision/processor.py`, `mee/api/engine.py`). The plan is technically sound, correctly bounded, and my implementation guidance has been verified against the real line numbers.

### Confirmed against source

1. **Processor.py accuracy:** `VisionProcessor.__init__` spans lines 85-98 (plan approximates "71–99"); `process()` at line 96–174 (plan approximates "101–167"). Plan's guidance is correct within approximation tolerance.

2. **Engine.py accuracy:** `MEEConfig` at line 25 has no `detect_every_n_frames` — plan correctly identifies this needs adding. `_ensure_vision()` at ~line 93 constructs `VisionProcessor(...)` with two kwargs — this is the correct insertion point.

3. **G1 freeze respected:** No changes to `deepefflib`, `emotion_model.py`, detector backends, or alignment logic.

### Plan revisions (clarifications only — no scope change)

**R1 — Cache field names (make explicit):**
```python
self._last_faces: Optional[list[Face]] = None  # None=uninitialized; []="no face"
self._last_frame_id: int | None = None         # id(frame_bgr) at detection time
self._last_frame_shape: tuple[int, ...] | None = None  # frame.shape before flattening
self._call_counter: int = 0                    # mod-n counter
```

**R2 — Config threading (explicit):** Add `detect_every_n_frames: Optional[int] = None` to the `MEEConfig` dataclass in engine.py. Engine reads via `self.config.detect_every_n_frames or 1`, forwards through `_ensure_vision()` → `VisionProcessor(detect_every_n_frames=...)`.

**R3 — Empty-face cache rule:** When detection finds no face, cache `[]` (not `None`). Future calls with valid frame identity reuse this empty-state, returning cheap `VisionResult(has_face=False)` until a changed frame triggers re-detection.

## G4 Decision: ✅ APPROVED

The plan is bounded, uses exact file/symbol/line guidance per R-SI-2, has clear acceptance criteria with verification steps, and all clarifications above are non-scoping. **Go ahead Implementer.**
