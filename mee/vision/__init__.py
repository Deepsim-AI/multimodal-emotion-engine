"""TASK_MEE_004: Vision emotion module — detection, emotion model, processor."""

from .detector import FaceDetector, Face
from .emotion_model import EmotionModel, EMOTION_LABELS
from .processor import VisionProcessor, VisionResult, FaceEmotion

__all__ = [
    "FaceDetector",
    "Face",
    "EmotionModel",
    "EMOTION_LABELS",
    "VisionProcessor",
    "VisionResult",
    "FaceEmotion",
]
