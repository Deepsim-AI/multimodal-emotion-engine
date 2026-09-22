# Implementation Instructions — TASK_MEE_010: Jetson AGX Orin Deployment

**Task ID:** TASK_MEE_010  
**Gate:** G2 (CTO Plan Approved)  
**Author:** CTO 🏗️  
**Date:** 2026-09-22  

---

## Implementation Plan — Step by Step

Follow these steps in order. Each step modifies/creates specific files — do not skip steps.

---

### STEP 1: Create `tools/export_models.py` (~200 lines)

**File:** `tools/export_models.py` (NEW)  
**Purpose:** Export MEE voice models to ONNX and optionally quantize to INT8 for TensorRT.

#### Structure:

```
Section 1 (lines 1-35): Imports and argparse CLI
    - argparse with choices=['speechbrain_iemocap', 'wav2vec2'], default='speechbrain_iemocap'
    - --format onnx|int8, default='onnx'
    - --output-dir <path>, default='./models/exported/'
    - --model-path override model_path flag

Section 2 (lines 36-90): export_speechbrain_iemocap(model_path, output_dir, format)
    - Load the IEMOCAP model using SpeechBrain EncoderClassifier.from_hparams()
      path: os.path.expanduser("~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP")
    - BUILD a wrapper module that implements __call__(x) → logits, matching the submodule
      call pattern from mee/voice/emotion_model.py lines 246-252:
          wav2vec2(raw) -> last_hidden_state -> avg_pool -> output_mlp -> logits
    - Use torch.onnx.export(wrapper, dummy_input, f, opset_version=17,
      input_names=['audio'], output_names=['logits'])
    - dummy_input: torch.randn(1, 16000) at 16kHz sample rate (1-second audio)

Section 3 (lines 91-145): export_wav2vec2(output_dir, format)
    - Load 'facebook/wav2vec2-base-960h' via transformers.AutoModelForAudioClassification
    - Use optimum-cli CLI: subprocess.run(['optimum-cli', 'export', 'onnx', ...])
      OR torch.onnx.export with AutoProcessor inputs
    - Handle label mapping (Wav2Vec default: ang, dis, fear, hap, neu, sad, sur)

Section 4 (lines 146-175): quantize_to_int8(input_path, output_path)
    - Use onnxruntime.quantization.post_quantization(model, 'QDSM') for data-free quantization
      OR use MEE_009 test scenarios as calibration data via representative_dataset_generator
    - Validate INT8 model loads and runs with same input/output shapes

Section 5 (lines 176-200): CLI dispatch
    - if args.model == 'speechbrain_iemocap': call export_speechbrain_iemocap
    - elif args.model == 'wav2vec2': call export_wav2vec2
    - Handle errors gracefully; print summary of exported files and sizes
```

#### Key Implementation Notes:
- SpeechBrain IEMOCAP uses a **direct submodule call** pattern (not the standard 1.1.x API). You MUST replicate this wrapper pattern for ONNX export. See existing code at `mee/voice/emotion_model.py` lines 246-252 for the exact forward pass to wrap.
- If SpeechBrain IEMOCAP is not downloaded, provide clear error message with download instructions.
- INT8 quantization uses data-free method first (QDSM — Quantize-Then-Dither-Scale-Magnitude), which works well for audio classification models that are already trained with dropout/BN.

---

### STEP 2: Create `tools/build_trt_engine.py` (~150 lines)

**File:** `tools/build_trt_engine.py` (NEW)  
**Purpose:** Build TensorRT INT8 engines from ONNX models for Jetson GPU acceleration.

#### Structure:

```
Section 1 (lines 1-25): Imports and argparse CLI
    - argparse with --onnx <path>, --output <path>, --int8/--fp16 flag, default int8
    - --calibration-dir for INT8 calibration data path

Section 2 (lines 26-75): build_engine(onnx_path, output_path, precision='int8', calib_dir=None)
    - Parse ONNX model with onnx.load()
    - Use tensorrt.Builder(logger) → tensorrt.Network(logger, trt.NetworkDefinitionCreationMode.EXPLICIT)
    - For INT8: create IInt8Calibrator with calibration data (MEE_009 scenarios)
    - Build engine with IBuilderConfig(flags)
    - Serialize to .trt file
    - If onnx2trt tool is available, use subprocess as alternative path

Section 3 (lines 76-115): build_engine_using_onnxruntime_trt(onnx_path, output_path)
    - Use ONNX Runtime TensorRT provider: InferenceSession(onnx, {'TensorrtExecutionProvider', ...})
    - Export the TRT engine via session.export_epic() or direct TensorRT API
    - This is the simpler fallback path that works without full TRT C++ builder

Section 4 (lines 116-150): CLI dispatch and logging
    - Print: input model, precision, output path, expected runtime behavior
    - Log all steps for auditability
```

#### Key Implementation Notes:
- TensorRT must be installed on Jetson (version >= 8.6 for JetPack 6.x) — verify before building
- INT8 calibration uses representative dataset from `tests/scenario_data.py` scenarios A-E
- If GPU device detection fails, abort with clear error

---

### STEP 3: Create `tools/bench_jetson.py` (~250 lines)

**File:** `tools/bench_jetson.py` (NEW)  
**Purpose:** Measure latency and memory for MEE pipeline on Jetson hardware.

#### Structure:

```
Section 1 (lines 1-45): Imports, config classes, benchmark runner state
    - from dataclasses import dataclass, field
    - BenchmarkConfig with runs=10, warmup_runs=3, output_format='csv'
    - LatencyResult with per-run measurements

Section 2 (lines 46-110): measure_component_latency(engine, component_name, audio=None, frame=None)
    - Monkey-patch or time-wrap the specified component method in EmotionEngine
    - For _infer_vision: inject timing before/after vp.process_frame() at line ~170 of engine.py
    - For _infer_voice: inject timing before/after vp.process() at line ~183 of engine.py
    - For _fuse: time self._fusion.compute_fusion() call at line ~198 of engine.py
    - For _compute_trend: time analyze_trend() call at line ~207 of engine.py
    - Return list of latency_ms measurements with mean/std/dev

Section 3 (lines 111-175): measure_memory_usage(engine)
    - Use psutil.Process().memory_info().rss for total process memory
    - Read Jetson power/thermal: open('/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq')
      OR use nvml (nvidia-ml-py if available on JetPack)
    - Record before and after pipeline runs

Section 4 (lines 176-230): run_benchmarks(config, model_config_override=None)
    - Load/create MEE EmotionEngine with config
    - Use MEE_009 test scenarios from tests/scenario_data.py for consistent inputs
    - Run each component benchmark in sequence
    - Record all metrics to CSV and JSON

Section 5 (lines 231-250): CLI interface
    - argparse with --model speechbrain/wav2vec/tensorrt, --output-dir <path>
    - Print results table to stdout after completion
```

#### Key Implementation Notes:
- **CRITICAL HOOK POINTS in mee/api/engine.py:**
  - Line ~153 (vision inference block): `face_result = self._infer_vision(video_frame)` — wrap with timing
  - Line ~162 (voice inference block): `voice_result = self._infer_voice(audio)` — wrap with timing
  - Line ~167 (fusion call): `overall = self._fuse(face_result, voice_result)` — wrap with timing
  - Line ~171 (trend computation): `trend = self._compute_trend()` — wrap with timing

---

### STEP 4: Create `tools/run_stability_test.py` (~100 lines)

**File:** `tools/run_stability_test.py` (NEW)  
**Purpose:** Run MEE continuously for >1 hour to verify no crashes, memory leaks, or degradation.

#### Structure:

```
Section 1 (lines 1-30): Imports and config
    - argparse with --hours <float>, default=2, --interval <int> seconds, default=5

Section 2 (lines 31-75): StabilityRunner class
    - __init__(): create EmotionEngine(), load test scenarios from tests/scenario_data.py
    - run_cycle(index, scenario): process one MEE_009 synthetic scenario, capture result + latency + memory
    - detect_memory_drift(): compare current RSS to baseline RSS — flag if >10% increase
    - detect_crash(): catch exceptions in processing loop; log stack trace

Section 3 (lines 76-100): Main run_loop()
    - Loop for --hours with --interval between cycles
    - Cycle through all MEE_009 scenarios (A-E) repeating
    - Print progress every hour
    - At end: print summary table (total runs, crashes, memory drift%, avg latency, worst latency)
```

#### Key Implementation Notes:
- Reuse the 5 scenarios from `tests/scenario_data.py` — they already produce deterministic, validated MEE outputs
- No external inputs needed — pure synthetic data validation
- Memory check uses psutil; handle cases where psutil is not installed gracefully

---

### STEP 5: Create `docs/JETSON_DEPLOYMENT.md` (~300 lines)

**File:** `docs/JETSON_DEPLOYMENT.md` (NEW)  
**Purpose:** Complete Jetson deployment guide.

#### Sections:
1. **Hardware Overview** (lines 1-20): Jetson AGX Orin 64GB, unified memory architecture explanation
2. **Software Requirements** (lines 21-55): Python >=3.9, PyTorch for JetPack version, ONNX Runtime with TensorRT, SpeechBrain 1.1+, insightface, psutil, nvidia-ml-py (optional)
3. **Installation Steps** (lines 56-90): 
   - pip install requirements
   - Download/export models using `tools/export_models.py`
   - Build TensorRT engines using `tools/build_trt_engine.py`
   - Verify with `python tools/bench_jetson.py --output-dir ./benchmarks/`
4. **Performance Benchmarks** (lines 91-160): Table of all measured latencies from bench output — FP32 vs INT8, per-component and total pipeline
5. **Memory Budget** (lines 161-220): Model sizes, runtime overhead, peak utilization charts/tables
6. **Known Limitations** (lines 221-260): Cold-start latency, TensorRT compilation time, SpeechBrain IEMOCAP label mapping limits (4→7 canonical via mapping table), no ASR in V1
7. **Model Lifecycle Management** (lines 261-300): Code examples for load/infer/unload pattern to minimize memory pressure

---

### STEP 6: Update Tests for Jetson Awareness

**Files:** `tests/test_vision.py` and `tests/test_voice.py`

#### In `tests/test_vision.py`:
- Add helper function `def is_jetson() -> bool:` that checks `/sys/class/nvmap/` directory existence or `nvidia-smi --query-gpu=name --format=csv,noheader | grep -c "Jetson"`
- Add pytest marker to test classes: `@pytest.mark.skipif(not is_jetson(), reason="Jetson hardware required")` for any GPU-specific tests

#### In `tests/test_voice.py`:
- Add same `is_jetson()` helper if not already available (move to a shared `tests/conftest.py` or `tests/helpers.py`)

---

### STEP 7: Update Voice Model for TensorRT Engine Auto-Detection

**File:** `mee/voice/emotion_model.py`  
**Method to modify:** `_ensure_loaded()` (starting at line ~85)

#### Changes within `_ensure_loaded()`:
After existing SpeechBrain/Wav2Vec loading attempts, add:
```python
# Check for TensorRT engine alongside model weights
trt_engine_path = os.path.join(
    os.path.dirname(self.model_path), 
    os.path.basename(os.path.normpath(self.model_path)) + '.trt'
)
if os.path.exists(trt_engine_path):
    try:
        import onnxruntime as ort
        self._model = ort.InferenceSession(
            trt_engine_path,
            providers=['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        self._backend = 'tensorrt'  # New backend type
        return  # Success — TensorRT engine loaded
    except Exception as e:
        print(f"[MEE-Voice] TRT engine load failed, falling back: {e}")
```

Then add `_predict_tensorrt()` method (~30 lines) to handle inference via ONNX Runtime TensorRT provider.

---

## Acceptance Criteria Verification

Before marking G3 (review), verify:
- [ ] All 7 deliverables exist on disk
- [ ] `python tools/export_models.py --help` runs without error
- [ ] `python tools/bench_jetson.py --help` runs without error
- [ ] `tools/evaluate_scenarios.py` still passes (regression check: should still have all 106 tests passing)
- [ ] No existing production code modified except for `_ensure_loaded()` in voice model (STEP 7) and test markers (STEP 6)

---

## Deliverables Summary

| # | File | Lines | Type |
|---|------|-------|------|
| 1 | `tools/export_models.py` | ~200 | NEW — Model export utility |
| 2 | `tools/build_trt_engine.py` | ~150 | NEW — TensorRT builder |
| 3 | `tools/bench_jetson.py` | ~250 | NEW — Benchmark harness |
| 4 | `tools/run_stability_test.py` | ~100 | NEW — Stability runner |
| 5 | `docs/JETSON_DEPLOYMENT.md` | ~300 | NEW — Deploy guide |
| 6 | `tests/test_vision.py`, `tests/test_voice.py` | modify markers | EXISTING — GPU-aware skip |
| 7 | `mee/voice/emotion_model.py` `_ensure_loaded()` | modify method | EXISTING — TRT engine detection |
