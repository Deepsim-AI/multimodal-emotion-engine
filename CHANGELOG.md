# Changelog — Multimodal Emotion Engine (MEE)

All notable changes to this project will be documented in this file.

## [Unreleased]

## [v0.1.0] — 2026-09-19

### Added
- Vision submodule (`mee/vision/`) with face detection and emotion classification:
  - `FaceDetector` — SCRFD-based face detection via InsightFace buffalo_l
  - `EmotionModel` — 7-class emotion prediction (anger, disgust, fear, happy, sad, surprised, neutral)
  - `VisionProcessor` — detection→classification→aggregation pipeline
  - Engine integration via `_infer_vision()` in `EmotionEngine`
- Graceful degradation: vision gracefully degrades when insightface unavailable (returns no-face result)
- Lazy model loading on first use (~280 MB download on first invocation)
- 12 unit tests for vision module (`tests/test_vision.py`)

### Dependencies Added
- `insightface>=0.7` — optional [vision] dependency
- `deepface>=0.0.84` — optional [vision] dependency
