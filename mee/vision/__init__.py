"""TASK_MEE_011: Vision emotion submodule — commercially-safe pipeline.

Three-stage architecture:
  Stage 1 (Detection):    FaceDetector  (retina-face MIT / dlib / OpenCV HOG)
  Stage 2 (Alignment):    FaceAligner   (face-alignment, Apache-2.0)
  Stage 3 (Expression):   EmotionModel  (EmotiEffLib, Apache-2.0 code + weights)

⚠️ InsightFace buffalo_l is NOT part of the production pipeline (non-commercial
   research-only weights). A research-only wrapper is provided behind the
   INSIGHTFACE_RESEARCH_ONLY=true env var guard (see detector.py).

See docs/THIRD_PARTY_LICENSES.md for full license inventory.
"""

from .detector import FaceDetector, Face
from .alignment import FaceAligner
from .emotion_model import (
    EmotionModel,
    MEE_LABELS,
    EMOTION_LABELS,
)

__all__ = [
    "FaceDetector",
    "Face",
    "FaceAligner",
    "EmotionModel",
    "MEE_LABELS",
    "EMOTION_LABELS",
]
