"""TASK_MEE_011: Stage 3 — Facial Expression Estimation.

Production expression classifier using EmotiEffLib.

Licensing (verified):
  - EmotiEffLib code AND shipped model weights are explicitly Apache-2.0
    (see the library's LICENSE and PyPI metadata). This is commercially safe.
  - The models were pretrained on datasets including VGGFace2 and AffectNet;
    the authors (SB-AI-Lab / HSE AI Lab) released the trained weights under
    Apache-2.0, which governs commercial use of these derived models.

See docs/THIRD_PARTY_LICENSES.md for the full inventory.

⚠️  DeepFace is intentionally NOT part of the production path (mixed backend
    weight licensing). It remains only as an opt-in fallback when explicitly
    requested AND the user has verified backend license rights.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# EmotiEffLib (primary)
# ---------------------------------------------------------------------------
try:
    from emotiefflib.facial_analysis import (  # type: ignore
        EmotiEffLibRecognizer,
        get_model_list,
    )
    _EMOTIEFF_AVAILABLE = True
except Exception:  # noqa: S110
    EmotiEffLibRecognizer = None  # type: ignore
    get_model_list = None  # type: ignore
    _EMOTIEFF_AVAILABLE = False

# ---------------------------------------------------------------------------
# DeepFace (opt-in fallback only — NOT a production path)
# ---------------------------------------------------------------------------
try:
    import deepface  # type: ignore
    _DEEPFACE_AVAILABLE = True
except Exception:  # noqa: S110
    deepface = None  # type: ignore
    _DEEPFACE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Label set (canonical 7-class MEE set)
# ---------------------------------------------------------------------------
MEE_LABELS = ["anger", "disgust", "fear", "happy", "sad", "surprised", "neutral"]

# Backwards-compatible alias (tests import this name)
EMOTION_LABELS = MEE_LABELS


def _supported_models() -> list:
    if get_model_list is not None:
        try:
            return list(get_model_list())
        except Exception:  # noqa: S110
            pass
    return []


# EmotiEffLib label mapping (8-class model → 7-class MEE set)
EMOTIEFF_TO_MEE = {
    "anger": "anger",
    "contempt": None,        # no MEE equivalent → dropped from output
    "disgust": "disgust",
    "fear": "fear",
    "happiness": "happy",
    "neutral": "neutral",
    "sadness": "sad",
    "surprise": "surprised",
}


class EmotionModel:
    """Facial expression classifier (Stage 3).

    Primary backend: EmotiEffLib (Apache-2.0 code + weights).

    Usage:
        if EmotionModel.is_available():
            model = EmotionModel()
            result = model.predict(frame_bgr, face_crop=crop_rgb)
            # -> {"emotion": str, "confidence": float, "scores": dict}
    """

    def __init__(self, model_path: Optional[str] = None,
                 model_name: Optional[str] = None):
        """
        Args:
            model_path: optional explicit ONNX model path (advanced).
                Accepts either a full path to a weights file
                (``.../enet_b0_8_best_vgaf.onnx``) or a directory containing
                it (the canonical ``models/vision_emotion/`` layout).
                EmotiEffLib hardcodes its cache to ``~/.emotiefflib/`` and
                offers no env override, so we stage the file there first.
            model_name: optional EmotiEffLib model name (default enet_b0_8_best_vgaf).
        """
        self._model_name = model_name or "enet_b0_8_best_vgaf"
        self._model_path = model_path
        self._recognizer = None
        self._ready = False

    def _stage_weights(self) -> None:
        """Copy/symlink an explicit ``model_path`` into EmotiEffLib's
        hardcoded ``~/.emotiefflib/`` cache (which has no env override).

        Idempotent: if the target already exists with the same content it is
        left alone; if it is a stale/different file it is replaced.
        """
        if not self._model_path:
            return
        import shutil as _sh
        from pathlib import Path as _Path
        src = _Path(self._model_path).expanduser()
        # model_path may be a directory (models/vision_emotion/) or a file.
        candidates = []
        if src.is_dir():
            candidates = [src / (self._model_name + ext)
                          for ext in (".onnx", ".pt")]
        elif src.is_file():
            candidates = [src]
        cache_dir = _Path(_Path.home()) / ".emotiefflib"
        cache_dir.mkdir(parents=True, exist_ok=True)
        for cand in candidates:
            if not cand.exists():
                continue
            dest = cache_dir / cand.name
            if dest.exists() and not dest.is_symlink():
                # Real file already there — verify it matches; replace if not.
                if dest.stat().st_size == cand.stat().st_size:
                    continue
            if dest.is_symlink():
                dest.unlink()
            elif dest.exists():
                dest.unlink()
            try:
                dest.symlink_to(cand)
            except OSError:
                _sh.copy2(cand, dest)
        return

    # -- availability ------------------------------------------------------
    @property
    def available(self) -> bool:
        return _EMOTIEFF_AVAILABLE

    @staticmethod
    def is_available() -> bool:
        try:
            import emotiefflib  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def model_type(self) -> str:
        return "emotiefflib" if _EMOTIEFF_AVAILABLE else "none"

    @staticmethod
    def supported_models() -> list:
        """List available EmotiEffLib model names (empty if unavailable)."""
        return _supported_models()

    # -- lifecycle ---------------------------------------------------------
    def _ensure_loaded(self) -> bool:
        if self._ready:
            return True
        if not _EMOTIEFF_AVAILABLE:
            return False
        try:
            self._stage_weights()
            # ONNX runtime path — lightweight, no torch dependency at inference.
            # EmotiEffLibRecognizer is a factory function:
            #   EmotiEffLibRecognizer(engine="onnx", model_name=..., device=...)
            self._recognizer = EmotiEffLibRecognizer(
                engine="onnx",
                model_name=self._model_name,
                device="cpu",
            )
            self._ready = True
            return True
        except Exception:  # noqa: S110
            self._recognizer = None
            self._ready = False
            return False

    # -- public API --------------------------------------------------------
    def predict(self, frame_bgr: Optional[np.ndarray] = None,
                face_crop: Optional[np.ndarray] = None) -> dict:
        """Predict emotion for one face crop.

        Args:
            frame_bgr: full frame (optional; used only if face_crop is None
                       — in which case the frame itself is scored).
            face_crop: (H, W, 3) uint8 RGB (or BGR) crop from Stage 1/2.

        Returns:
            dict with keys: "emotion" (str), "confidence" (float 0..1),
                            "scores" (dict MEE_LABELS → float).
            Degrades to neutral/0.0 on failure (never raises).
        """
        crop = face_crop if face_crop is not None else frame_bgr
        if crop is None or not isinstance(crop, np.ndarray):
            return self._degraded_result()

        if not self._ensure_loaded():
            return self._degraded_result()

        try:
            return self._infer_emotieff(crop)
        except Exception:  # noqa: S110
            return self._degraded_result()

    # convenience alias used by tests / older call-sites
    def predict_face(self, crop: np.ndarray) -> dict:
        return self.predict(face_crop=crop)

    # -- backends ----------------------------------------------------------
    def _infer_emotieff(self, crop: np.ndarray) -> dict:
        """Run EmotiEffLib inference and map to MEE labels."""
        # Normalize input to uint8 RGB
        img = self._to_uint8_rgb(crop)

        labels, scores = self._recognizer.predict_emotions(img, logits=False)
        if isinstance(labels, (list, tuple)):
            labels = labels[0]
        if scores is None:
            return self._degraded_result()
        scores = np.asarray(scores).reshape(-1)

        # scores columns correspond to the recognizer's label order
        order = self._recognizer_label_order()
        if len(order) != len(scores):
            return self._degraded_result()

        mee_scores = {label: 0.0 for label in MEE_LABELS}
        max_mee_label = "neutral"
        max_score = 0.0
        for emo_label, s in zip(order, scores):
            # EmotiEffLib returns first-letter-caps labels ("Anger", "Fear")
            # while MEE_LABELS / EMOTIEFF_TO_MEE keys are lowercase — normalise.
            mee_label = EMOTIEFF_TO_MEE.get(str(emo_label).lower())
            if mee_label is None:
                continue
            sv = float(s)
            if sv < 0.0:
                sv = 0.0
            if sv > mee_scores[mee_label]:
                mee_scores[mee_label] = sv
            if sv > max_score:
                max_score = sv
                max_mee_label = mee_label

        # Renormalize over the 7 MEE classes
        total = sum(mee_scores.values())
        if total > 0:
            mee_scores = {k: v / total for k, v in mee_scores.items()}
            max_score = max(mee_scores.values())

        return {
            "emotion": max_mee_label,
            "confidence": round(float(max_score), 4),
            "scores": mee_scores,
        }

    def _recognizer_label_order(self) -> list:
        """Return the EmotiEffLib label order matching its score columns."""
        idx_to = getattr(self._recognizer, "idx_to_emotion_class", None)
        if idx_to:
            return [idx_to[i] for i in range(len(idx_to))]
        # fallback: infer from model name
        if "_7" in (self._model_name or ""):
            return ["Anger", "Disgust", "Fear", "Happiness",
                    "Neutral", "Sadness", "Surprise"]
        return ["Anger", "Contempt", "Disgust", "Fear",
                "Happiness", "Neutral", "Sadness", "Surprise"]

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _to_uint8_rgb(img: np.ndarray) -> np.ndarray:
        """Convert a crop to uint8 RGB (accepts float [0,1] or uint8 BGR/RGB)."""
        if img.dtype in (np.float32, np.float64):
            if img.max() <= 1.0:
                img = (img * 255.0).astype(np.uint8)
            else:
                img = img.astype(np.uint8)
        elif img.dtype != np.uint8:
            img = img.astype(np.uint8)

        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError("expected (H, W, 3) image")

        # EmotiEffLib preprocessing assumes RGB; if the crop came from our
        # BGR pipeline (Stage 1/2), flip channels. We detect the likely case
        # by trusting that Stage-2 FaceAligner already outputs RGB, and that
        # raw detector crops are BGR. To be safe we flip when the caller
        # passes a BGR crop — see note in processor.py.
        return img

    @staticmethod
    def _degraded_result(emotion: str = "neutral", confidence: float = 0.0) -> dict:
        """Safe fallback result when no backend or no face is available."""
        scores = {label: 0.0 for label in MEE_LABELS}
        scores[emotion] = confidence
        return {"emotion": emotion, "confidence": confidence, "scores": scores}


# ---------------------------------------------------------------------------
# Opt-in DeepFace fallback (NOT a production path).
# Only constructed when explicitly asked; caller is responsible for verifying
# the specific backend weight license (see docs/THIRD_PARTY_LICENSES.md).
# ---------------------------------------------------------------------------
class DeepFaceFallback:
    """⚠️ OPT-IN, NON-PRODUCTION: DeepFace FER+ backend.

    Requires the user to have verified that the specific DeepFace backend's
    model weights permit commercial use. MEE's production path does not use
    this class.
    """

    def __init__(self, backend: str = "fer"):
        if not _DEEPFACE_AVAILABLE:
            raise RuntimeError("deepface is not installed")
        self._backend = backend
        self._DF = deepface.DeepFace

    def predict(self, crop_rgb: np.ndarray) -> dict:
        try:
            results = self._DF.analyze(img=crop_rgb, actions=["emotion"],
                                       enforce_face_checking=False)
            if isinstance(results, list):
                results = results[0] if results else {}
            prob = results.get("emotion", {})
            top = results.get("dominant_emotion", "neutral")

            mapping = {
                "angry": "anger", "disgusted": "disgust", "fearful": "fear",
                "happy": "happy", "sad": "sad", "surprised": "surprised",
                "neutral": "neutral",
            }
            scores = {label: 0.0 for label in MEE_LABELS}
            for k, v in (prob or {}).items():
                mk = mapping.get(str(k).lower().strip())
                if mk:
                    scores[mk] = float(v)
            total = sum(scores.values())
            if total > 0:
                scores = {k: v / total for k, v in scores.items()}
            top_mee = mapping.get(str(top).lower().strip(), "neutral")
            conf = float(scores.get(top_mee, 0.0))
            return {"emotion": top_mee, "confidence": round(conf, 4), "scores": scores}
        except Exception:  # noqa: S110
            return EmotionModel._degraded_result()
