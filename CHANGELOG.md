# Changelog — Multimodal Emotion Engine (MEE)

All notable changes to this project will be documented in this file.

## [Unreleased]
**Emotion Demonstration UI (TASK_MEE_008):**
- `demo/emotion_demo.py` — Single-file Streamlit demo driving the public EmotionEngine API (589 lines)
- Live camera + mic input, real-time face/voice/overall emotion bars, trend indicator, conflict banner, debug JSON panel
- Headless/JSON-output mode for scripted evaluation (`--headless`)
- Graceful degradation when camera/microphone/hardware unavailable (synthetic-input fallback)
- `pyproject.toml` — demo extras: `streamlit>=1.28`, `sounddevice>=0.4`, `opencv-python>=4.8`
- `docs/DEMO.md` — one-page install/run guide (GUI + headless, hardware fallbacks)
**Jetson AGX Orin Deployment (TASK_MEE_010):**
- `tools/export_models.py` — SpeechBrain IEMOCAP + Wav2Vec 2.0-base export utilities
- `tools/build_trt_engine.py` — TensorRT engine builder with 3 fallback paths
- `tools/bench_jetson.py` — Performance benchmark harness (5-component timing)
- `tools/run_stability_test.py` — Extended stability runner with crash + drift detection
- `docs/JETSON_DEPLOYMENT.md` — Complete deployment guide (8 sections, hardware/software/perf/limitations)
- `mee/voice/emotion_model.py` — INT8 TensorRT auto-detection and graceful fallback
- `tests/helpers.py` — Jetson environment detection helper (`is_jetson()`)
- Test updates with `@pytest.mark.skipif` markers for non-Jetson hosts

**Jetson AGX Orin Deployment (TASK_MEE_010):**
- `tools/export_models.py` — SpeechBrain IEMOCAP + Wav2Vec 2.0-base export utilities
- `tools/build_trt_engine.py` — TensorRT engine builder with 3 fallback paths
- `tools/bench_jetson.py` — Performance benchmark harness (5-component timing)
- `tools/run_stability_test.py` — Extended stability runner with crash + drift detection
- `docs/JETSON_DEPLOYMENT.md` — Complete deployment guide (8 sections, hardware/software/perf/limitations)
- `mee/voice/emotion_model.py` — INT8 TensorRT auto-detection and graceful fallback
- `tests/helpers.py` — Jetson environment detection helper (`is_jetson()`)
- Test updates with `@pytest.mark.skipif` markers for non-Jetson hosts

**End-to-End Validation (TASK_MEE_009):**
- `tools/evaluate_scenarios.py` — Runnable end-to-end evaluation harness
- `tests/scenario_data.py` — Scenario definitions (5 standardized scenarios: Neutral, Happy, Sad, Frustrated/Conflict, Cross-over)
- `tests/test_scenarios.py` — 38 tests validating full pipeline integration via monkey-patched process() path
- `docs/TEST_PROTOCOL.md` — Evaluation methodology, expected results, pass/fail criteria
- Full suite: 106 tests (was 68 → +38 new, zero regressions)


## [v0.1.0] — 2026-09-20

### Added

**Vision Subsystem (TASK_MEE_004):**
- `mee/vision/detector.py` — FaceDetector + Face dataclass (SCRFD via InsightFace)
- `mee/vision/emotion_model.py` — EmotionModel with 7-class prediction
- `mee/vision/processor.py` — VisionProcessor pipeline
- Engine integration via `_infer_vision()` in EmotionEngine
- Graceful degradation when insightface unavailable
- 12 unit tests (`tests/test_vision.py`)

**Voice Subsystem (TASK_MEE_005):**
- `mee/voice/recorder.py` — AudioRecorder + MicRecorder for audio capture
- `mee/voice/features.py` — FeatureExtractor (9 acoustic features via librosa)
- `mee/voice/emotion_model.py` — EmotionModel with SpeechBrain RavNet primary + Wav2Vec 2.0 fallback
- `mee/voice/processor.py` — VoiceProcessor pipeline
- Engine integration via `_infer_voice()` in EmotionEngine
- Graceful degradation when speechbrain unavailable
- 13 unit tests (`tests/test_voice.py`)

**Documentation:**
- `docs/MODEL_EVALUATION.md` — Vision and voice model comparison tables
- Task lifecycle artifacts for MEE_001, MEE_003, MEE_004, MEE_005

### Dependencies Added
- `[vision]`: opencv-python, onnxruntime, insightface, deepface
- `[voice]`: speechbrain, sounddevice, librosa, onnxruntime
