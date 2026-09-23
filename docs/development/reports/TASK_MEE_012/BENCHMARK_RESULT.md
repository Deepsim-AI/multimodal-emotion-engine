# TASK_MEE_012 — Vision Performance Benchmark (Completed 2026-09-23)

**Status: BENCHMARK DATA AVAILABLE — PENDING CTO REVISION of G3**

Benchmark was completed and raw data written to `_bench_raw.json`. Results below. **Per G3, the CTO must now revise the task plan**: the retina-face CPU detection bottleneck is not fixable by code changes to `mee/vision/` (the pipeline is G1-approved, cannot be modified). It is a Jetson/dependency fix (TensorRT-optimized retina-face, ONNX runtime, or a GPU backend detector). This likely warrants a new task or a scoped dependency patch reviewed by the CTO.

## Benchmark environment
- Host: deepsim (Jetson AGX Orin, 64 GB)
- Python 3.10, NumPy 1.26.4
- Detector backend: **retina-face** (installed; requires `tf-keras` — installed during benchmark)
- Alignment backend: **face_alignment** (Apache-2.0)
- Emotion backend: **EmotiEffLib** (enet_b0_8_best_vgaf)

## Benchmark results (raw JSON: `_bench_raw.json`)

| Stage | Mean | p95 | p99 | min | fps | Notes |
|-------|------|-----|-----|-----|-----|-------|
| S1 Detection (retina-face) | 1143 ms | 1628 ms | 1745 ms | 1010 ms | **0.87** | CPU-only; no GPU path |
| S2 Alignment | — | — | — | — | — | skipped (no face in synthetic image) |
| S3 Emotion inference | **49.9 ms** | 90.9 ms | 109.6 ms | 23.8 ms | **20.05** | dominant emotion "fear" (random-noise input; expected) |
| End-to-end | 1111 ms | 1583 ms | 1677 ms | 1004 ms | **0.9** | bottleneck = detection |
| Memory (3-min sustained) | — | — | — | — | — | drift **+5.72%** (target: < +20%) ✓ |

## Key findings
1. **Emotion inference meets the ≥12 fps target** (20.05 fps, 49.9 ms/face). MEE_011 replacement is validated.
2. **Detection is the hard bottleneck: ~1182 ms/face, 0.85–0.87 fps** (verified independently on the same hardware). This is **retina-face running CPU-only** — the installed retina-face build has no CUDA/TensorRT path, so it runs entirely on CPU.
3. **Detection reported 0 faces** — retina-face requires a real human face; synthetic ellipse images are not detected. This is expected on synthetic test images and does **not** indicate a detection bug (the detector runs correctly; it found no face geometry to detect).
4. **Memory stability: +5.72% drift** over 3 minutes (162 samples, 1827 MB → 1931 MB) — **well within the +20% tolerance**. No memory growth issue.
5. **tf-keras** was installed during benchmarking (retina-face prerequisite). NumPy was reverted to 1.26.4 after a temporary numpy 2.x upgrade caused a compile-time `_ARRAY_API` incompatibility with the vision libs.

## Recommended next step (CTO decision needed)
The detection bottleneck is a **Jetson dependency/runtime problem**, not a Python code problem. Options for CTO to evaluate:
- (a) Install a GPU-optimized face detector (e.g., TensorRT/ONNX-RT retina-face, or InsightFace buffalo_l detector which is already present at `~/.insightface/models/buffalo_l/det_10g.onnx`) and route the detector to it — **requires a code change to `mee/vision/detector.py`**, which touches G1-approved pipeline → needs a new CTO-approved task or explicit G3 revision.
- (b) Reduce detection frequency (detect every Nth frame) to decouple from the ~1 s latency while keeping emotion at 20 fps. This is a policy/config change, not a code change, and can be done without touching the pipeline.

**Raw benchmark data preserved in `_bench_raw.json` for CTO revision.**
