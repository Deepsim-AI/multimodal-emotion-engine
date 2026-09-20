"""TASK_MEE_004 Task 3: Emotion model — DeepFace FER+ with graceful degradation.

Strategy:
  1. Primary: DeepFace with FER backend (7 classes)
     - Most accurate open source facial expression model
     - Returns probability distribution over 7 emotions
  2. Graceful degradation: if no backend, return neutral/0.0
"""

from __future__ import annotations

from typing import Optional

import numpy as np

# Canonical 7-class FER label set (matches DeepFace FER backend)
EMOTION_LABELS = [
    "anger", "disgust", "fear", "happy", "sad", "surprised", "neutral"
]


class EmotionModel:
    """7-class facial emotion estimator.

    Lazy-loads DeepFace on first predict() call.

    Usage:
        if EmotionModel.is_available():
            model = EmotionModel()
            result = model.predict(frame_bgr, face_crop=None)
    """

    def __init__(self, model_path: Optional[str] = None):
        self._model_path = model_path
        self._backend = None
        self._ready = False
        self._deepface = None

    @staticmethod
    def is_available() -> bool:
        """True if deepface is importable."""
        try:
            import deepface  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure_loaded(self) -> None:
        """Lazy-load DeepFace on first use."""
        if self._ready:
            return
        try:
            from deepface import DeepFace as _DF  # type: ignore
            self._deepface = _DF
            self._backend = "deepface"
            self._ready = True
        except Exception:
            pass  # _ready stays False — predict() will return degraded result

    def predict(self, frame_bgr: np.ndarray, face_crop: Optional[np.ndarray] = None) -> dict:
        """Predict emotion from a full frame or pre-cropped face region.

        Args:
            frame_bgr: (H, W, 3) uint8 BGR frame.
            face_crop: Optional pre-cropped face (H, W, 3) uint8 BGR.

        Returns:
            {
                "emotion": str,       # argmax label
                "confidence": float,  # argmax probability
                "scores": dict[str, float],
            }
        """
        self._ensure_loaded()

        if not self._ready:
            return self._degraded_result()

        return self._predict_deepface(frame_bgr, face_crop)

    def _predict_deepface(self, frame_bgr: np.ndarray, face_crop: Optional[np.ndarray] = None) -> dict:
        input_img = face_crop if face_crop is not None else frame_bgr
        try:
            results = self._deepface.extract_faces(
                img=input_img,
                backend="fer",
                enforce_face_checking=True,
            )
        except Exception:
            return self._degraded_result()

        if not results:
            return self._degraded_result()

        best = max(results, key=lambda r: r.get("confidence", 0))
        prob = best.get("probability", {})

        scores: dict[str, float] = {label: 0.0 for label in EMOTION_LABELS}
        for k, v in prob.items():
            norm_key = self._normalise_label(k)
            if norm_key in scores:
                scores[norm_key] = float(v)

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        emotion = max(scores, key=scores.get)
        confidence = scores[emotion]
        return {"emotion": emotion, "confidence": round(confidence, 4), "scores": scores}

    @staticmethod
    def _normalise_label(label: str) -> str:
        """Map DeepFace FER labels to our canonical set."""
        mapping = {
            "angry": "anger",
            "disgusted": "disgust",
            "fearful": "fear",
            "happy": "happy",
            "sad": "sad",
            "surprised": "surprised",
            "neutral": "neutral",
        }
        return mapping.get(label.lower().strip(), label.lower().strip())

    @staticmethod
    def _degraded_result(emotion: str = "neutral", confidence: float = 0.0) -> dict:
        """Safe fallback when no backend or no face found."""
        scores = {label: 0.0 for label in EMOTION_LABELS}
        scores[emotion] = confidence
        return {"emotion": emotion, "confidence": confidence, "scores": scores}
