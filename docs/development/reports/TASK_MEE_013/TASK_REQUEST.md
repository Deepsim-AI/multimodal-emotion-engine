# TASK_MEE_013 — Task Request

**Requested by:** Project Manager 📋 (PM) 2026-09-23
**Requested model:** Option 2 via standard DS-EO task workflow (CTO Plan → Implementer → Reviewer → G4 → PM G5)
**Predecessor:** TASK_MEE_012 (benchmark findings, committed at 5b51bb6)

## Context / Why

TASK_MEE_011 replaced the vision emotion pipeline with an EmotiEffLib-native implementation. The MEE_012 benchmark (`docs/development/reports/TASK_MEE_012/BENCHMARK_RESULT.md`, `_bench_raw.json`) found:

- Emotion inference (Stage 3, EmotiEffLib): **20.05 fps** — comfortably above the ≥12 fps target.
- Face detection (Stage 1, retina-face, **CPU-only**): **~1182 ms/face, 0.85 fps** — the dominant bottleneck. Independently reproduced (`1182.3 ms` mean).
- End-to-end: **0.9 fps**, bottleneck = detection.
- Memory stability over 3 min: **+5.72% drift** — well within the +20% tolerance.

Detection runs on the full frame on **every** vision forward pass. Since detection (~1 s) is ~23× slower than emotion (~50 ms), the effective throughput is gated by the detection frequency, not the emotion throughput. We need to **decouple detection frequency from emotion-pass frequency** so that detection is done once and its result (bounding box + 5-point landmarks) is reused for multiple emotion passes.

## Scope (G1 boundary)

Implement a **`detect_every_n_frames`** configuration knob that decouples detection frequency from the emotion forward pass.

- **Single new config field**, documented in the code, defaulting to `1` (backward-compatible: behavior unchanged unless the operator opts in).
- `n == 1`: detection runs every call — **exact current behavior**, no regression.
- `n > 1`: detection runs on the first call; the last detected bounding box + 5-point landmarks are **cached and reused** for subsequent calls up to and including `n` calls, after which detection re-runs.
- The cached detection result must **feed Stage 2 (alignment) and Stage 3 (emotion)** exactly as a freshly-detected result would — i.e., the decoupling is transparent to downstream stages.
- The knob is **purely a performance lever**, not an accuracy change: it does not alter how detection/alignment/inference work, only *how often* detection executes.

## Hard Constraints

1. **G1 gate freeze:** `mee/vision/emotion_model.py` is G1-approved **production** code. Do **not** refactor the three-stage architecture, change the model, change the detection backend, or alter the alignment/emotion logic. The change must be **localized, additive, and backward-compatible**.
2. **No cross-task assumption:** this task owns only the decoupling knob. Any accuracy/compression/quantization work is out of scope.
3. **Backward compatibility:** default behavior (detection every pass) must be byte-for-byte identical to current behavior. If the knob is unset/1, the detector must run on every call.
4. **Minimal surface:** add the field + the cache-reuse logic only. No new files unless strictly required by the task. Any new file must be scoped to this task.
5. **No external actions.** No pip installs, no model downloads, no network.
6. **Evidence of change:** Implementer must add inline change markers (`// TASK_MEE_013 Task N:` per AGENTS.md R-SI-4).

## Acceptance Criteria

- [ ] New config field `detect_every_n_frames` exists and defaults to `1`.
- [ ] With the default (`1`), detection runs on every vision forward pass (behavior unchanged).
- [ ] With `n > 1`, detection runs once and its result is reused for the next `n-1` calls, then re-runs.
- [ ] Reused detection result feeds alignment + emotion exactly as a fresh detection would.
- [ ] Behavior verified against the existing test suite (no regressions) and a focused detection-frequency test.
- [ ] README / docs updated to describe the knob (task-authorized).

## Verification

- Existing unit/integration tests must pass.
- A focused test demonstrating `n > 1` reduces detection invocations by the expected factor while preserving emotion outputs.
- Report findings in `implementation/` and the final `IMPLEMENTATION_REPORT.md`.

## Notes for CTO

- Detection currently runs on CPU-only at ~1 s/face (retina-face has no GPU path on this Jetson). The knob's value is to allow lower *effective* detection frequency when the operator accepts minor staleness.
- Decide the exact cache shape and where it lives (in the EmotionModel pipeline instance? a small per-frame state object?). Keep it minimal and thread/usage-safe as much as reasonable; do not over-engineer.
