"""TASK_MEE_005 Subtask 4: Emotion model — acoustic emotion classification.

Primary: SpeechBrain RavNet (Apache-2.0) via speechbrain.inference
Fallback: Wav2Vec 2.0-base + emotion head (MIT license)
Degraded: neutral/0.0/all-zeros when no backend available
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np


VOICE_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]


@dataclass
class VoiceResult:
    """Structured emotion prediction from voice."""
    emotion: str = "neutral"
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "emotion": self.emotion,
            "confidence": self.confidence,
            "scores": self.scores,
        }


class EmotionModel:
    """Acoustic emotion classification using SpeechBrain or Wav2Vec.

    Usage:
        model = EmotionModel()
        result = model.predict(audio_array, sample_rate=16000)
    """

    # Label mapping: SpeechBrain native → MEE canonical (identity for the supported set)
    LABEL_MAP: Dict[str, str] = {
        "angry": "angry",
        "disgust": "disgust",
        "fear": "fear",
        "happy": "happy",
        "sad": "sad",
        "surprised": "surprised",
        "neutral": "neutral",
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
    ):
        self.model_path = model_path or "speechbrain/mtl-mimic-rep-vanilla"
        self.device = device
        self._model = None
        self._initialized = False
        self._speechbrain_available = False
        self._wav2vec_available = False
        self._init_backends()

    def _init_backends(self):
        """Detect available backends."""
        try:
            import speechbrain  # noqa: F401
            self._speechbrain_available = True
        except ImportError:
            self._speechbrain_available = False

        try:
            import transformers  # noqa: F401
            self._wav2vec_available = True
        except ImportError:
            self._wav2vec_available = False

    @property
    def available(self) -> bool:
        return self._speechbrain_available or self._wav2vec_available

    @staticmethod
    def is_available() -> bool:
        try:
            import speechbrain  # noqa: F401
            return True
        except ImportError:
            try:
                import transformers  # noqa: F401
                return True
            except ImportError:
                return False

    def _ensure_loaded(self) -> None:
        """Load the emotion model on first call (lazy init)."""
        if self._initialized:
            return
        self._initialized = True

        # Try SpeechBrain first (primary per MEE_003 CTO_APPROVAL)
        if self._speechbrain_available and self._model is None:
            try:
                from speechbrain.inference.classifiers import Classifier  # noqa: PLC0412
                self._model = Classifier(hyperparams=self.model_path)
                self._backend = "speechbrain"
                return
            except Exception as e:
                print(f"[MEE-Voice] SpeechBrain load failed: {e}")

        # Try Wav2Vec fallback
        if self._wav2vec_available and self._model is None:
            try:
                from transformers import (  # noqa: PLC0412
                    AutoModelForAudioClassification,
                    AutoProcessor,
                )
                self._processor = AutoProcessor.from_pretrained("facebook/wav2vec2-base-960h")
                self._model = AutoModelForAudioClassification.from_pretrained(
                    "facebook/wav2vec2-base-960h"
                )
                self._backend = "wav2vec"
                return
            except Exception as e:
                print(f"[MEE-Voice] Wav2Vec fallback failed: {e}")

        # No backend available — model stays None (degraded mode)
        self._model = None
        self._backend = None

    def predict(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        features: Optional[Dict[str, float]] = None,
    ) -> VoiceResult:
        """Predict emotion from raw audio.

        Args:
            audio: (N,) float32 mono audio samples at ~16kHz.
            sample_rate: Audio sample rate (default 16000).
            features: Optional precomputed acoustic features (unused in V1, preserved for future).

        Returns:
            VoiceResult with emotion, confidence, and scores over VOICE_LABELS.
        """
        if audio is None or len(audio) == 0:
            return self._degraded_result()

        self._ensure_loaded()

        if self._model is None:
            return self._degraded_result()

        try:
            if self._backend == "speechbrain":
                return self._predict_speechbrain(audio, sample_rate)
            elif self._backend == "wav2vec":
                return self._predict_wav2vec(audio, sample_rate)
            else:
                return self._degraded_result()

        except Exception:
            # On inference error, degrade to neutral
            return self._degraded_result()

    def _predict_speechbrain(self, audio: np.ndarray, sample_rate: int) -> VoiceResult:
        """Run emotion prediction via SpeechBrain RavNet."""
        # SpeechBrain expects a list of utterances; wrap single utterance
        utterances = [audio.astype(np.float32)]

        # Use the Classifier's encode_batch + classify method
        from speechbrain.inference.classifiers import Classifier  # noqa: PLC0412

        features = self._model.encode_batch(utterances)
        logits = self._model.classify_batch(features, torchaudio_lens=None)

        probs = np.array(logits.probs[0])
        label_idx = int(np.argmax(probs))
        label_name = logits.labels[0][label_idx] if label_idx < len(logits.labels[0]) else "neutral"

        # Map SpeechBrain label → MEE canonical label
        canonical_label = self.LABEL_MAP.get(label_name, label_name)

        scores = {label: 0.0 for label in VOICE_LABELS}
        # Align scores: SpeechBrain label order may differ; map by index
        sb_labels = [s.lower() for s in logits.labels[0]]
        for i, (sb_label, prob) in enumerate(zip(sb_labels, probs.tolist())):
            canonical = next(
                (k for k, v in self.LABEL_MAP.items() if v == sb_label or k == sb_label),
                sb_label,
            )
            scores[canonical] = round(prob, 6)

        confidence = float(probs[label_idx])
        return VoiceResult(
            emotion=canonical_label,
            confidence=round(confidence, 4),
            scores=scores,
        )

    def _predict_wav2vec(self, audio: np.ndarray, sample_rate: int) -> VoiceResult:
        """Run emotion prediction via Wav2Vec 2.0."""
        from transformers import (  # noqa: PLC0412
            AutoProcessor,
            AutoModelForAudioClassification,
        )

        inputs = self._processor(
            audio.tolist(),
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True,
        )

        with np.nditer([], op_dtypes=[np.float64], flags=['external_loop']):
            import torch  # noqa: PLC0412
            if self.device == "cuda":
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits.detach().cpu().numpy()[0]

        probs = np.exp(logits - np.max(logits))  # numerical stability
        probs = probs / probs.sum()
        label_idx = int(np.argmax(probs))
        confidence = float(probs[label_idx])

        # Wav2Vec default emotion labels: ang, dis, fear, hap, neu, sad, sur
        wb_labels_map = {
            "ang": "angry",
            "dis": "disgust",
            "fear": "fear",
            "hap": "happy",
            "neu": "neutral",
            "sad": "sad",
            "sur": "surprised",
        }

        label_names = self._model.config.id2label if hasattr(self._model.config, 'id2label') else wb_labels_map
        canonical_label = wb_labels_map.get(label_names[label_idx], label_names[label_idx])

        scores = {label: 0.0 for label in VOICE_LABELS}
        model_labels = self._model.config.label2id if hasattr(self._model.config, 'label2id') else {}
        for label_name, idx in model_labels.items():
            if idx < len(probs):
                canonical = wb_labels_map.get(label_name, label_name)
                scores[canonical] = round(float(probs[idx]), 6)

        return VoiceResult(
            emotion=canonical_label,
            confidence=round(confidence, 4),
            scores=scores,
        )

    def _degraded_result(self) -> VoiceResult:
        """Safe fallback when no backend or error occurs."""
        scores = {label: 0.0 for label in VOICE_LABELS}
        return VoiceResult(
            emotion="neutral",
            confidence=0.0,
            scores=scores,
        )
