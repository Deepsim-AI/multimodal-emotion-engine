"""TASK_MEE_005 Subtask 5: Voice processor — orchestrates feature extraction + emotion classification.

Pipeline:
  1. FeatureExtractor.extract(audio) → dict of acoustic features
  2. EmotionModel.predict(audio, features) → VoiceResult
  3. Return result (always returns, never raises)
"""
from __future__ import annotations

from typing import Dict, Optional

from .features import FeatureExtractor
from .emotion_model import EmotionModel


class VoiceProcessor:
    """Combines FeatureExtractor + EmotionModel into a single call per audio input.

    Usage:
        vp = VoiceProcessor()
        result = vp.process(audio_array, sample_rate=16000)
    """

    def __init__(
        self,
        feature_extractor=None,
        emotion_model=None,
    ):
        # Lazy init: allows injection for testing and graceful fallback
        self._feature_extractor = feature_extractor or FeatureExtractor()
        self._emotion = emotion_model or EmotionModel()

    @property
    def available(self) -> bool:
        return self._emotion.available

    def process(
        self,
        audio: 'np.ndarray',
        sample_rate: int = 16000,
    ) -> Dict[str, object]:
        """Process one audio input.

        Args:
            audio: (N,) float32 mono audio samples at ~sample_rate Hz.
            sample_rate: Audio sample rate (default 16000).

        Returns:
            Dict matching _MEEFaceResult.to_dict() schema:
                {"emotion": str, "confidence": float, "scores": {label: float}}
            Always returns a valid dict — never raises.
        """
        import numpy as np

        # Validate input
        if audio is None or len(audio) == 0:
            return self._degraded_result()

        if not isinstance(audio, (np.ndarray, list)):
            return self._degraded_result()

        if isinstance(audio, list):
            audio = np.array(audio, dtype=np.float32)

        # Step 1: Extract acoustic features
        features = self._feature_extractor.extract(audio, sample_rate)

        # Step 2: Predict emotion
        result = self._emotion.predict(audio, sample_rate, features)

        return result.to_dict()

    def process_audio_chunk(
        self,
        duration_seconds: float = 2.0,
    ) -> Optional[Dict[str, object]]:
        """Convenience: record + process one audio chunk from live mic.

        Requires sounddevice and a physical microphone.
        Returns None if mic is unavailable.
        """
        try:
            from .recorder import MicRecorder  # noqa: PLC0412
            mic = MicRecorder(sample_rate=16000)
            record = mic.record_chunk(seconds=duration_seconds)
            if record is None:
                return None
            return self.process(record.data, record.sample_rate)
        except Exception:
            return None

    def _degraded_result(self) -> Dict[str, object]:
        """Degraded output when no model or no audio available."""
        scores = {label: 0.0 for label in [
            "angry", "disgust", "fear", "happy", "sad", "surprised", "neutral",
        ]}
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "scores": scores,
        }
