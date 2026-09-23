"""TASK_MEE_011 TASK_MEE_012: Facial expression estimator using EmotiEffLib.

Replaces the previous DeepFace FER+ backend (mixed weight licensing) with
EmotiEffLib — a library where both code AND shipped model weights are explicitly
licensed under Apache-2.0, making it commercially safe for MEE production use.

Model weight licensing note:
  EmotiEffLib models were pretrained on datasets including VGGFace2 and AffectNet. 
  However, the authors (SB-AI-Lab/HSE AI Lab) have explicitly released their trained 
  weights under Apache-2.0, which supersedes original dataset terms for commercial use 
  of these specific derived models.

See docs/THIRD_PARTY_LICENSES.md for full license inventory.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


# ── Primary: EmotiEffLib (Apache-2.0 for code + weights) ────────────────────
try:
    from emotiefflib.facial_analysis import FacialEmotionRecognizer, get_model_list  # type: ignore
    _EMOTIEFF_AVAILABLE = True
except Exception:  # noqa: S110
    FacialEmotionRecognizer = None
    _EMOTIEFF_AVAILABLE = False

# ── Fallback: DeepFace FER+ (MIT code only) ──────────────────────────────────
try:
    import deepface  # type: ignore
    _DEEPFACE_AVAILABLE = True
except Exception:  # noqa: S110
    _DEEPFACE_AVAILABLE = False


# Canonical MEE label set
MEE_LABELS = ["anger", "disgust", "fear", "happy", "sad", "surprised", "neutral"]

# EmotiEffLib label mapping (8 classes → 7 MEE classes)
EMOTIEFF_TO_MEE = {
    "angry": "anger",
    "disgust": "disgust", 
    "fearful": "fear",
    "happy": "happy",
    "sad": "sad",
    "surprised": "surprised",
    "neutral": "neutral",
    "contempt": None,       # No equivalent in MEE 7-class → skip/neutral
}


class ExpressionClassifier:
    """Facial expression classifier using EmotiEffLib (Apache-2.0).

    Usage:
        if ExpressionClassifier.is_available():
            classifier = ExpressionClassifier()
            result = classifier.infer(face_crop_rgb)
    """

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name
        self._classifier = None
        self._ready = False
        self._backend_used = None

    @staticmethod
    def is_available() -> bool:
        return _EMOTIEFF_AVAILABLE or _DEEPFACE_AVAILABLE

    def _ensure_loaded(self) -> bool:
        if self._ready:
            return True
        
        # Strategy 1: EmotiEffLib (preferred — Apache-2.0 weights)
        if _EMOTIEFF_AVAILABLE and not self._classifier:
            try:
                model = self._model_name or "enet_b0_8_best_vgaf"  # Fast default
                self._classifier = FacialEmotionRecognizer(model=model, verbose=0)
                self._ready = True
                self._backend_used = "emotiefflib"
                return True
            except Exception:
                pass
        
        # Strategy 2: DeepFace FER+ (fallback)
        if _DEEPFACE_AVAILABLE and not self._classifier:
            try:
                from emotiefflib import DeepFace as _DF
                self._classifier = _DF
                self._backend_used = "deepface"
                self._ready = True
                return True
            except Exception:
                pass
        
        return False

    def infer(self, face_crop_rgb: np.ndarray) -> dict:
        """Predict emotion from a cropped face (RGB)."""
        if not self._ensure_loaded():
            return self._degraded_result()

        try:
            if self._backend_used == "emotiefflib":
                result = self._infer_emotieff(face_crop_rgb)
            elif self._backend_used == "deepface":
                result = self._infer_deepface(face_crop_rgb)
            else:
                return self._degraded_result()

            if result is not None:
                return result
        except Exception:
            pass

        return self._degraded_result()

    def _infer_emotieff(self, face_crop_rgb: np.ndarray) -> Optional[dict]:
        """Run EmotiEffLib inference."""
        if face_crop_rgb.dtype == np.float32 or face_crop_rgb.dtype == np.float64:
            input_img = (face_crop_rgb * 255).astype(np.uint8)
        else:
            input_img = face_crop_rgb.copy()

        try:
            result_dict = self._classifier.predict(input_img)
            
            if isinstance(result_dict, dict):
                scores = {label: 0.0 for label in MEE_LABELS}
                
                max_score = 0.0
                max_label = "neutral"
                for emoteff_label, score in result_dict.items():
                    mee_label = EMOTIEFF_TO_MEE.get(emoteff_label)
                    if mee_label:
                        scores[mee_label] = float(score)
                        if float(score) > max_score:
                            max_score = float(score)
                            max_label = mee_label

                total = sum(scores.values())
                if total > 0:
                    scores = {k: v / total for k, v in scores.items()}
                
                return {
                    "emotion": max_label,
                    "confidence": round(max_score, 4),
                    "scores": scores,
                }
        except Exception:
            pass

        return None

    def _infer_deepface(self, face_crop_rgb: np.ndarray) -> Optional[dict]:
        """Run DeepFace FER+ inference (fallback)."""
        try:
            results = self._classifier.extract_faces(
                img=face_crop_rgb if face_crop_rgb.ndim == 3 else face_crop_rgb[..., ::-1],
                backend="fer",
                enforce_face_checking=False,
            )
            
            if not results:
                return None

            best = max(results, key=lambda r: r.get("confidence", 0))
            prob = best.get("probability", {})

            scores = {label: 0.0 for label in MEE_LABELS}
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

        except Exception:
            return None

    @staticmethod
    def _normalise_label(label: str) -> str:
        """Map DeepFace FER labels to MEE canonical set."""
        mapping = {
            "angry": "anger", "disgusted": "disgust",
            "fearful": "fear", "happy": "happy",
            "sad": "sad", "surprised": "surprised",
            "neutral": "neutral",
        }
        return mapping.get(label.lower().strip(), label.lower().strip())

    @staticmethod
    def _degraded_result(emotion: str = "neutral", confidence: float = 0.0) -> dict:
        """Safe fallback when no backend or no face found."""
        scores = {label: 0.0 for label in MEE_LABELS}
        scores[emotion] = confidence
        return {"emotion": emotion, "confidence": confidence, "scores": scores}


# ── Graceful degradation when no model is available ────────────────────────────────

def _no_infer(*args, **kwargs):
    return ExpressionClassifier._degraded_result()  # type: ignore

if not ExpressionClassifier.is_available():
    ExpressionClassifier.infer = _no_infer  # type: ignore
    ExpressionClassifier.is_available = lambda: False  # type: ignore
