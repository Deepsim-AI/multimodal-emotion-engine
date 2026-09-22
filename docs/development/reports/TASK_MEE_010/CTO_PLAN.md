# CTO Plan — TASK_MEE_010: Jetson AGX Orin Deployment

**Task ID:** TASK_MEE_010  
**Phase:** Phase 5b (Edge Validation)  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)  
**Date:** 2026-09-22  

---

## Objective

Validate and optimize MEE on **Jetson AGX Orin (64GB unified memory)** after PC prototype is proven by TASK_MEE_009. Measure resource use and latency; produce `docs/JETSON_DEPLOYMENT.md`.

**Decision:** Plan has user approval to proceed (2026-09-22). Implementation starts immediately after this document.

---

## Architecture Decisions

### A. Voice Model: SpeechBrain IEMOCAP → ONNX Export (Primary Path)

**Recommendation:** Export the existing SpeechBrain `emotion-recognition-wav2vec2-IEMOCAP` to ONNX, then convert to INT8 TensorRT for Jetson GPU. This avoids introducing new dependencies and leverages the already-vetted model from MEE_003.

**Rationale (per MODEL_EVALUATION.md §3 VO1 evaluation):**
- SpeechBrain has **explicit ONNX export and TensorRT support built-in** (★ Best Jetson compatibility)
- Existing IEMOCAP weights are already in `~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP/` (~400MB with wav2vec2 backbone)
- INT8 quantization brings it down to ~200MB (vs. 350MB baseline + Vision model ~80MB = 280MB total — well within Jetson memory constraints when models are not loaded simultaneously)

**Risk:** IEMOCAP hyperparams.yaml is authored for SpeechBrain 0.x and incompatible with 1.1.x `classify_batch` (verified in current code at `mee/voice/emotion_model.py` lines 70-75). The workaround (direct submodule call: wav2vec2 → avg_pool → output_mlp) must be preserved or mapped to ONNX export path.

### B. Voice Model Alternative: Wav2Vec 2.0-base (Secondary Path)

**Fallback:** `facebook/wav2vec2-base-960h` with HF `optimum` → ONNX export → TensorRT INT8. This is a clean, well-documented path per MODEL_EVALUATION.md VO2 evaluation. Size: ~350MB baseline → ~175MB INT8.

### C. Vision Model: InsightFace Buffalo_L (No Change)

**Decision:** No optimization needed for V1 — DeepFace/InsightFace Buffalo_L is already ONNX-native and runs directly under ONNX Runtime on Jetson GPU via ORT-TensorRT. The weights (~50-80MB) are small enough that INT8 quantization provides marginal latency improvement but not memory necessity.

### D. Memory Budget (64GB Unified — Effective ~61GB usable)

| Component | FP32 Size | INT8 Size | Jetson Strategy |
|-----------|-----------|-----------|-----------------|
| SpeechBrain IEMOCAP (wav2vec2+classifier) | ~400MB | ~200MB | Load only during voice inference; unload after |
| Wav2Vec 2.0-base fallback | ~350MB | ~175MB | Alternative if export fails |
| InsightFace Buffalo_L (vision) | ~80MB | ~40MB | ONNX RT, no change needed |
| Python runtime + dependencies | ~200-300MB | — | Constant |
| OS + background processes | ~4GB | — | Not controllable |
| **Peak during voice inference** | **~5-6GB** | **~3-4GB** | Well within 61GB constraint |

**Rule:** Per AGENTS.md compaction rule (MEE_010 extends the same hardware principle): never load more than ~3 large models simultaneously. The deploy script must manage model lifecycle (load → infer → unload).

---

## Task Breakdown (with Exact File/Guidance)

### Task 1: Model Export Utilities

**Create:** `tools/export_models.py` (~200 lines)
- **Line 1-30:** Imports and CLI argument parser (argparse with `--model {speechbrain_iemocap|wav2vec2} --format onnx|onnx-int8 --output-dir`)
- **Line 31-80:** SpeechBrain IEMOCAP export function — uses `speechbrain.utils.export` or direct PyTorch ONNX export: `torch.onnx.export(model, dummy_input, f, opset_version=17, input_names=['audio'], output_names=['logits'])`
  - **Critical:** Must handle the hyperparams.yaml SpeechBrain 0.x/1.1.x incompatibility by building a wrapper module that exposes a single-callable forward method compatible with `torch.onnx.export` (see line ~92-102 of emotion_model.py for the submodule call pattern to replicate)
- **Line 81-130:** Wav2Vec 2.0-base export via `optimum-cli export onnx --model facebook/wav2vec2-base-960h` — uses HF optimum library
- **Line 131-170:** INT8 quantization step using `onnxruntime.quantization.post_process_quantization` or `torch.ao.quantization.convert_to_int8` depending on source model
- **Line 171-200:** CLI dispatch and error handling

### Task 2: TensorRT Builder Utility

**Create:** `tools/build_trt_engine.py` (~150 lines)
- **Line 1-20:** Imports (tensorrt, tensorrt.tensorrt, onnx_graphsurgeon for IR adjustment)
- **Line 21-60:** Build function — creates ONNX Builder → TensorRT Builder → INT8 calibration cache. Uses `torch_tensorrt` JIT compilation path where available, falls back to `trtexec --onnx=model.onnx --saveEngine=model.trt --int8` command-line invocation
- **Line 61-100:** Calibrator for INT8 — uses MEE_009 test suite's 38 synthetic scenarios as calibration data (deterministic, reproducible)
- **Line 101-150:** CLI interface and logging

### Task 3: Performance Benchmark Harness

**Create:** `tools/bench_jetson.py` (~250 lines) + **Modify:** existing test infrastructure
- **Line 1-40:** Imports and benchmark config (MEEConfig-compatible)
- **Line 41-100:** `measure_latency_ms()` function — wraps `engine.process()` in timed loops (10 iterations, warmup excluded), returns mean/std/dev of latency_ms
- **Line 101-160:** `benchmark_component()` for each subsystem: `_infer_vision`, `_infer_voice`, `_fuse`, `_compute_trend` — measures isolated component latencies via monkey-patch or timing hooks in the EmotionEngine class
  - **Hook point:** Insert timing markers in `mee/api/engine.py` process() at line ~148-157 (the vision inference block through trend computation block)
- **Line 161-200:** Memory measurement via `psutil.Process().memory_info()` and Jetson-specific queries (`/sys/class/nvmap/`, or Python's `nvml` library if available)
- **Line 201-250:** CSV/JSON output with all metrics; runs against ALL models (SpeechBrain, Wav2Vec, on-device TensorRT)

### Task 4: Extended Stability Runner

**Create:** `tools/run_stability_test.py` (~100 lines)
- **Line 1-30:** Imports and config
- **Line 31-70:** Continuous processing loop — feeds MEE_009 synthetic scenarios (from `tests/scenario_data.py`) at configurable intervals, monitors memory drift and crashes over N hours
- **Line 71-100:** Results summary: total runs, crash count, max memory delta, model unload/load cycle count

### Task 5: docs/JETSON_DEPLOYMENT.md

**Create:** `docs/JETSON_DEPLOYMENT.md` (~300 lines)
- **Section 1 (lines 1-20):** Hardware overview — Jetson AGX Orin 64GB, unified memory architecture, GPU/CPU memory sharing constraints
- **Section 2 (lines 21-50):** Software requirements — Python version, PyTorch build for JetPack, ONNX Runtime TensorRT, SpeechBrain, insightface, calibration dependencies
- **Section 3 (lines 51-90):** Installation steps — step-by-step pip install, model download/export commands, TensorRT engine build process
- **Section 4 (lines 91-160):** Performance measurements table — all latency benchmarks from benchmark harness (each modality at FP32 and INT8; fused pipeline; memory usage)
- **Section 5 (lines 161-220):** Memory budget table — model sizes, runtime overhead, peak utilization during different inference configurations
- **Section 6 (lines 221-260):** Known limitations — model loading latency (cold start), TensorRT compilation time (one-time cost), SpeechBrain IEMOCAP label set limitation (4 labels → 7 canonical via mapping)
- **Section 7 (lines 261-300):** Model lifecycle management script recommendation

### Task 6: Test Updates for Jetson Compatibility

**Modify:** `tests/test_vision.py` and `test_voice.py` to add environment-aware tests:
- Add `pytest.mark.skipif` for non-Jetson environments (check `/sys/class/nvmap/` or `nvidia-smi --query-gpu=name --format=csv,noheader`) — **File:** `tests/test_vision.py` line ~N (add skip marker to existing test classes)
- Add GPU availability check: insert in `mee/vision/emotion_model.py` `is_available()` method at line ~50-53 (current check imports deepface; add GPU device check alongside)

### Task 7: Graceful Degradation Update for Jetson

**Modify:** `mee/voice/emotion_model.py` — add explicit INT8 TensorRT inference path
- **Line ~82-130** (`_ensure_loaded()`): After SpeechBrain/Wav2Vec loading, check for `.trt` engine file alongside model weights
- If found: load via `onnxruntime.InferenceSession(engine_path, providers=['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider'])`
- The TensorRT provider is registered automatically by onnxruntime when TensorRT is installed — no extra import needed beyond checking for the `.trt` file

---

## Implementation Strategy

### Phase Order (for single-session execution):
1. **Task 1** — Model export utilities (prerequisite for Tasks 2, 4)
2. **Task 2** — TensorRT builder (depends on Task 1 output)
3. **Task 3** — Benchmark harness (needs models from Tasks 1-2)
4. **Task 4** — Stability runner (depends on Task 3 patterns)
5. **Task 6** — Test updates (can run in parallel with Task 5)
6. **Task 7** — Graceful degradation updates (can run in parallel with Tasks 3-4)
7. **Task 5** — Documentation (final step; uses results from Tasks 3, 4)

### Parallelization:
Tasks 6+7 can be implemented in the same session as Task 3 (Implementer writes both code changes + test additions). Tasks 1-2 should be one session (model export is the most complex, highest-risk component).

### Model Loading Order:
Per hardware constraints, the deploy script should:
1. Load vision model (lightweight, ONNX RT) — ~80MB
2. Load voice model on-demand — ~200-400MB depending on quantization
3. After voice inference completes → explicit model cleanup (`del self._model; torch.cuda.empty_cache()`)
4. Memory budget: peak ~500MB vs. 61GB available — no conflict

### Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| SpeechBrain IEMOCAP hyperparams.yaml incompatible with ONNX export path | High | Use direct PyTorch submodule export pattern (already proven in `emotion_model.py` lines 246-252); test on Jetson first before deploying to production hardware |
| TensorRT INT8 calibration accuracy degradation on limited dataset | Medium | Use all MEE_009 synthetic scenarios (38 samples) + real audio if available; verify INT8 vs FP32 results match within 0.05 confidence threshold |
| Jetson GPU driver compatibility (current host CUDA 13.0 but JetPack may use different version) | Medium | Pin PyTorch to JetPack-compatible version in deploy doc; test on actual Jetson hardware, not just PC simulation |
| Large model cold-start latency (>30s for first inference) | Low | Document as known limitation; add warmup option to benchmark harness |

---

## Acceptance Criteria

- [ ] `tools/export_models.py` exports both SpeechBrain IEMOCAP and Wav2Vec 2.0-base to ONNX/INT8
- [ ] `tools/build_trt_engine.py` produces valid TensorRT engines for export model(s)
- [ ] `tools/bench_jetson.py` measures all latency targets from ARCHITECTURE.md §8: face detection <30ms, expression inference <50ms (TensorRT), voice <60ms (TensorRT), fusion+trend <5ms, total pipeline <150ms
- [ ] `tools/run_stability_test.py` runs >1 hour with zero crashes and memory drift <10% of peak
- [ ] `docs/JETSON_DEPLOYMENT.md` is complete with all 7 sections
- [ ] Model lifecycle management documented (load/unload patterns)
- [ ] Memory budget ≤ ~5GB peak during voice inference (well within Jetson constraint)

---

## Gate Entry Checklist

- G1: This plan document (current file)
- Dependency: TASK_MEE_009 ✅ (all 5 gates passed, E2E validation complete)
- No existing code depends on this task (MEE_011 depends on MEE_010 — downstream constraint)

---

**Status:** AWAITING IMPLEMENTATION  
