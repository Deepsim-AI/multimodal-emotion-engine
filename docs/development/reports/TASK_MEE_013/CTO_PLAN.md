# TASK_MEE_013 — CTO Task Plan (G1 — Architecture & Task Approval)

**Author:** CTO / Architect 🏗️ (draft for genuine technical review — see "Gate note" below)
**Date:** 2026-09-23
**Predecessor:** TASK_MEE_012 (benchmark findings, committed 5b51bb6)
**Status:** DRAFT — awaiting real CTO review and G4 approval. This plan is precise and bounded; the CTO must verify it stands, not rubber-stamp it.

---

## 1. Problem (from MEE_012 benchmark)

Detection is ~1 s/face (0.85 fps, CPU-only retina-face) and runs on **every** vision forward pass. Emotion inference is ~50 ms/face (20 fps). End-to-end is gated at 0.9 fps by detection frequency. We must **decouple detection frequency from emotion-pass frequency** without touching the G1-approved model backends.

## 2. Gate boundary (G1 freeze)

- **Untouched (G1):** `deepefflib` model, `deepefflib_model`, `alignment` (68-point refine), `emotion_model` inference weights/logic, detector **backends** (retina-face / dlib / opencv_hog), `deepefflib` license posture.
- **In scope (this task):** the **detection frequency control** in the orchestration layer only — `mee/vision/processor.py::VisionProcessor` and, to expose the knob, the engine constructor at `mee/api/engine.py`.
- Detection, alignment, and inference **algorithms are unchanged**. We only change *how often* detection runs and reuse its result.

## 3. Deliverable — one config knob

Add a single new parameter **`detect_every_n_frames: int = 1`** to `VisionProcessor.__init__`, threaded from `EmotionEngine.__init__` config. Semantics:

- `n == 1` (default): detection runs on every `process()` call — **behavior byte-for-byte identical** to current.
- `n > 1`: detection runs on call #1; its result (bounding box + 5-point landmarks) is cached and reused for calls #2..#n; detection re-runs on call #(n+1). Reused result feeds Stage 2 (alignment) and Stage 3 (emotion) exactly as a freshly-detected result would.

### Cache contract (must be satisfied)
- Cache holds: last `list[Face]` (or `None`), the last raw frame reference used for detection, and a monotonic call counter (mod `n`).
- **Staleness rule (safety):** detection MUST re-run when the frame content changes materially, else the cached bbox is stale. Concretely, the cache is invalidated on any of:
  - frame `shape` change (resolution/ndim),
  - frame `id`/`flags` change if a frame tag is available,
  - the caller passes a **different array object** (identity) — this is the simplest correct invalidation and matches the engine's per-frame loop,
  - **OR** an explicit `force_detection=True` argument on `process()`.
- If **no face was detected** on the last detection, cache that "no face" state; reuse it (still a valid, cheap result) until invalidated by a changed frame, matching the `not faces` early-return path.

### Correctness constraints
- With `n == 1`, the code path and outputs must be **identical** to current (no early/late detection, no cache read). Recommend implementing the default path as a fast `if self._detect_every_n_frames <= 1: return self._detect_once(...)` branch so the common path adds negligible overhead and no new state is consulted.
- `n` must be **validated** in `__init__` (`n >= 1`, else raise `ValueError`) — do not silently clamp.
- The knob must be **documented** (docstring + README).

## 4. Exact implementation guidance (R-SI-2: file/symbol/line ranges)

**File A — `mee/vision/processor.py`** (orchestrator, NOT G1 model weights)
- `VisionProcessor.__init__` (approx. lines 71–99): add param `detect_every_n_frames: int = 1`; store `self._detect_every_n_frames` after validation; (optionally) add `force_detection: bool = False` param to `process`.
- `VisionProcessor.process` (approx. lines 101–167): wrap the existing detect/align/emit body in a small helper `_run_once(frame_bgr) -> VisionResult`; add, at the top of `process`, a frequency gate that reuses the cached result when a valid cache exists and neither forced nor due-for-detection.
- Add the cache fields to `__init__`: `self._last_faces`, `self._last_frame`, `self._frame_counter`.
- Inline markers: `// TASK_MEE_013 Task 1:` etc. (AGENTS.md R-SI-4).
- Do **not** modify `deepefflib`, `deepefflib_model`, `alignment`, or `emotion_model`.

**File B — `mee/api/engine.py`** (approx. `EmotionEngine.__init__`, lines 60–110, the VisionProcessor construction at line 100)
- Add `detect_every_n_frames: Optional[int] = None` to the engine constructor (and, if it accepts a **config object**, to that config schema), and forward it: `VisionProcessor(..., detect_every_n_frames=<value>)`.
- If no config object exists yet, add the field to the engine's accepted constructor kwargs only (minimal surface). Do **not** redesign config plumbing.

## 5. Where the knob does NOT go (explicit exclusions)
- NOT in `deepefflib` / `deepefflib_model`.
- NOT in `alignment.py` (alignment runs as before on whatever face result we have).
- NOT in the detector backends.
- NOT a resolution change / downscale (that would alter accuracy and is out of scope).
- NOT a per-model per-frame policy (keep it a single global knob for this task).

## 6. Acceptance criteria (verbatim, from TASK_REQUEST)
- [ ] New config field `detect_every_n_frames` exists, defaults to `1`.
- [ ] With default (`1`), detection runs on every forward pass (behavior unchanged).
- [ ] With `n > 1`, detection runs once and result reused for the next `n-1` calls, then re-runs.
- [ ] Reused result feeds alignment + emotion exactly as a fresh detection would.
- [ ] Existing tests pass; focused detection-frequency test added.
- [ ] README/docs describe the knob.

## 7. Verification plan
1. **Unit — default parity:** with `n == 1`, assert `process(frame)` returns the same `VisionResult` as before the change (compare against the current unpatched behavior / a recorded fixture). Assert detector call count == number of `process` calls.
2. **Unit — decoupling:** with `n == 3`, call `process` 6× on the **same** frame; assert detector invoked 2× (6 / 3), aligner/emotion invoked 6×, and emotion outputs identical across the reused calls.
3. **Unit — staleness:** with `n == 3`, call `process` on frame A (face) then a **different array** frame B (no face); assert detection re-ran (detected B's no-face state), not that A's cached face was wrongly reused.
4. **Unit — validation:** `detect_every_n_frames=0` raises `ValueError`.
5. **Integration:** run the existing `tests/test_vision.py` and `tests/test_fusion.py`; assert no regressions.
6. **Manual (optional, G1 host):** drive `EmotionEngine(detect_every_n_frames=4)` and confirm effective detection frequency drops ~4× while emotion outputs remain stable on a static image.

## 8. Risks & mitigations
- **Stale bbox risk** → mitigated by frame-identity/shape invalidation + `force_detection` (Sec. 3).
- **Hidden-state surprises** → the cache is per-`VisionProcessor` instance, single-threaded per instance; note this is not thread-safe and callers using one processor across threads must set `n == 1` (document it).
- **G1 creep** → strictly a frequency knob in the orchestrator; backends untouched.

## 9. Post-G4 (do NOT perform by CTO)
After issuing G4, the CTO does **not** run the completion checklist, update `PROJECT_STATUS.md`/`CHANGELOG.md`, or send `PM_CLOSED.md`. Those are PM (G5) duties. The CTO may flag to the user that Post-G4 remains pending.

---

**Gate note (read before treating this as done):** I drafted this plan under a user directive to proceed. Per DS-EO Rule 9 (no cross-agent duty substitution) and the independent-review requirement, this plan **must be reviewed by the CTO for technical soundness and formally approved at G4** — it is not self-authorizing. If the CTO disagrees with any boundary above, that rejection itself is a valid G1 outcome and should be reported rather than papered over.
