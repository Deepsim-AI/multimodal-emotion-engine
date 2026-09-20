# Changelog — Multimodal Emotion Engine (MEE)

All notable changes to this project will be documented in this file.

## [Unreleased]

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
