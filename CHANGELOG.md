# Changelog — Multimodal Emotion Engine (MEE)

All notable changes to this project will be documented in this file.

## [Unreleased]

## [v0.1.0] — 2026-09-22

### Added

**Temporal State Tracking (TASK_MEE_007):**
- `mee/state/history.py` — EmotionHistory fixed-window ring buffer
- `mee/state/estimator.py` — analyze_trend() deterministic classifier
- Engine integration via _compute_trend() in process() output under "trend" key

**Packaging & Documentation (TASK_MEE_011):**
- LICENSE file (Apache-2.0)
- requirements.txt generation from pyproject.toml deps
- README.md with install, usage, architecture overview, limitations, disclaimer
- docs/THIRD_PARTY_LICENSES.md — complete third-party component inventory
- EmotiEffLib-based vision pipeline (replaces InsightFace buffalo_l)

**End-to-End Validation (TASK_MEE_009):**
- `tools/evaluate_scenarios.py` — Runnable end-to-end evaluation harness
- `tests/scenario_data.py` — Scenario definitions (5 standardized scenarios: Neutral, Happy, Sad, Frustrated/Conflict, Cross-over)
- `tests/test_scenarios.py` — 38 tests validating full pipeline integration via monkey-patched process()
- `docs/TEST_PROTOCOL.md` — Evaluation methodology, expected results, pass/fail criteria
- Full suite: 106 tests (was 68 → +38 new, zero regressions)

**Jetson AGX Orin Deployment (TASK_MEE_010):**
- `tools/export_models.py` — SpeechBrain IEMOCAP + Wav2Vec 2.0-base export utilities
- `tools/build_trt_engine.py` — TensorRT engine builder with 3 fallback paths
- `tools/bench_jetson.py` — Performance benchmark harness (5-component timing)
- `tools/run_stability_test.py` — Extended stability runner with crash + drift detection
- `docs/JETSON_DEPLOYMENT.md` — Complete deployment guide (8 sections, hardware/software/perf/limitations)
- `mee/voice/emotion_model.py` — INT8 TensorRT auto-detection and graceful fallback
- `tests/helpers.py` — Jetson environment detection helper (`is_jetson()`)
- Test updates with `@pytest.mark.skipif` markers for non-Jetson hosts

**Emotion Demonstration UI (TASK_MEE_008):**
- `demo/emotion_demo.py` — Single-file Streamlit demo driving the public EmotionEngine API (589 lines)
- Live camera + mic input, real-time face/voice/overall emotion bars, trend indicator, conflict banner, debug JSON panel
- Headless/JSON-output mode for scripted evaluation (`--headless`)
- Graceful degradation when camera/microphone/hardware unavailable (synthetic-input fallback)
- `pyproject.toml` — demo extras: `streamlit>=1.28`, `sounddevice>=0.4`, `opencv-python>=4.8`
- `docs/DEMO.md` — one-page install/run guide (GUI + headless, hardware fallbacks)

**Voice Subsystem (TASK_MEE_005):**
- `mee/voice/recorder.py` — AudioRecorder + MicRecorder for audio capture
- `mee/voice/features.py` — FeatureExtractor (9 acoustic features via librosa)
- `mee/voice/emotion_model.py` — EmotionModel with SpeechBrain RavNet primary + Wav2Vec 2.0 fallback
- `mee/voice/processor.py` — VoiceProcessor pipeline
- Engine integration via `_infer_voice()` in EmotionEngine
- Graceful degradation when speechbrain unavailable
- 13 unit tests (`tests/test_voice.py`)

**Vision Subsystem (TASK_MEE_004):**
- `mee/vision/detector.py` — FaceDetector + Face dataclass (SCRFD via InsightFace)
- `mee/vision/emotion_model.py` — EmotionModel with 7-class prediction
- `mee/vision/processor.py` — VisionProcessor pipeline
- Engine integration via `_infer_vision()` in EmotionEngine
- Graceful degradation when insightface unavailable
- 12 unit tests (`tests/test_vision.py`)

### Changes

**License & Packaging (TASK_MEE_011):**
- MEE application code license changed to Apache-2.0 (from Proprietary)
- EmotiEffLib replaces InsightFace buffalo_l for production facial expression estimation
- Third-party license inventory added to docs/THIRD_PARTY_LICENSES.md

### Documentation
- `docs/MODEL_EVALUATION.md` — Vision and voice model comparison tables
- `docs/ARCHITECTURE.md` — Final architecture documentation (260 lines)
- `docs/TEST_PROTOCOL.md` — Testing methodology and pass/fail criteria

---
*All gates G1→G5 complete for tasks MEE_001 through MEE_011.*
*MEE remains an independent capability, not tied to the AI Companion book or any specific robot.*
