# Changelog — Multimodal Emotion Engine (MEE)

All notable changes to this project will be documented in this file.

## [Unreleased]

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
