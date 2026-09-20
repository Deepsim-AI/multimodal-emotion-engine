"""TASK_MEE_004 Task 4: Vision processor — orchestrates detection + emotion per frame.

Pipeline:
  1. FaceDetector.detect(frame) → list[Face]
  2. For each face: crop, EmotionModel.predict(crop) → emotion scores
  3. Return VisionResult with per-face scores, best-face label, and has_face

Public entry point:
  process(frame) → VisionResult
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .detector import FaceDetector, Face
from .emotion_model import EmotionModel


@dataclass
class FaceEmotion:
    """Emotion prediction for a single detected face."""
    label: str = "neutral"
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)
    bbox: tuple = (0.0, 0.0, 0.0, 0.0)  # (x, y, w, h)


@dataclass
class VisionResult:
    """Result of processing one video frame.

    Fields used by EmotionEngine._infer_vision:
      has_face, emotion, confidence, scores

    Additional fields for richer reporting:
      face_count, faces, best_emotion, best_confidence, channel_scores
    """
    has_face: bool = False
    # TASK_MEE_004: fields expected by EmotionEngine
    emotion: str = ""
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)
    face_count: int = 0
    faces: list = field(default_factory=list)
    # Best-face (highest confidence) summary
    best_emotion: str = ""
    best_confidence: float = 0.0
    # Per-channel (here just "vision") result
    channel_scores: dict = field(default_factory=dict)


class VisionProcessor:
    """Combines FaceDetector + EmotionModel into a single call per frame.

    Usage:
        vp = VisionProcessor()
        result = vp.process(frame_bgr)
        if result.has_face:
            print(result.best_emotion, result.best_confidence)
    """

    def __init__(self, detector=None, emotion_model=None):
        # Lazy init: allows injection for testing
        self._detector = detector or FaceDetector()
        self._emotion = emotion_model or EmotionModel()

    def process(self, frame_bgr: np.ndarray) -> VisionResult:
        """Process one BGR frame.

        Args:
            frame_bgr: (H, W, 3) uint8 BGR array.

        Returns:
            VisionResult — always returns (never raises on no-face).
        """
        faces = self._detector.detect(frame_bgr)

        if not faces:
            return VisionResult(
                has_face=False,
                emotion="",
                confidence=0.0,
                scores={},
                face_count=0,
                faces=[],
                best_emotion="",
                best_confidence=0.0,
                channel_scores={},
            )

        face_results: list[FaceEmotion] = []
        for face in faces:
            # TASK_MEE_004: use crop_face and Face.bbox
            crop = self._detector.crop_face(frame_bgr, face)
            pred = self._emotion.predict(frame_bgr, face_crop=crop)
            bbox = face.bbox
            x1, y1, x2, y2 = (float(v) for v in bbox)
            face_results.append(FaceEmotion(
                label=pred["emotion"],
                confidence=pred["confidence"],
                scores=pred["scores"],
                bbox=(x1, y1, x2 - x1, y2 - y1),
            ))

        # Best face = highest confidence
        best = max(face_results, key=lambda f: f.confidence)

        return VisionResult(
            has_face=True,
            emotion=best.label,
            confidence=best.confidence,
            scores=best.scores,
            face_count=len(face_results),
            faces=face_results,
            best_emotion=best.label,
            best_confidence=best.confidence,
            channel_scores={"vision": best.scores},
        )

    def process_frame(self, frame_bgr: np.ndarray) -> VisionResult:
        """Alias for process() — used by EmotionEngine._infer_vision."""
        return self.process(frame_bgr)
