"""TASK_MEE_011: Vision emotion submodule — commercially-safe pipeline.

Three-stage architecture:
  Stage 1 (Detection): FaceDetector (retina-face, MIT)
  Stage 2 (Alignment): FaceAligner (face-alignment, Apache-2.0)
  Stage 3 (Expression): ExpressionClassifier (EmotiEffLib, Apache-2.0 for code + weights)

⚠️ InsightFace buffalo_l detection has been removed from the production pipeline
   because its pretrained model weights are non-commercial research-only per
   InsightFace's official license policy.

See docs/THIRD_PARTY_LICENSES.md for full license inventory.
"""

from .detector import FaceDetector, FaceBox, FaceAligner
from .emotion_model import ExpressionClassifier, MEE_LABELS

__all__ = [
    "FaceDetector",     # Stage 1: face detection (retina-face)
    "FaceBox",          # Detection result dataclass
    "FaceAligner",      # Stage 2: face alignment/cropping (face-alignment)
    "ExpressionClassifier",  # Stage 3: emotion classification (EmotiEffLib)
    "MEE_LABELS",       # Canonical 7-class label set
]
