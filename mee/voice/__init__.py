"""TASK_MEE_005 Subtask 1a: Voice package exports.

Public API:
    from mee.voice import (
        AudioRecorder, MicRecorder,
        FeatureExtractor, AUDIO_FEATURES,
        EmotionModel, VOICE_LABELS, VoiceResult,
        VoiceProcessor,
    )
"""
from .recorder import AudioRecorder, MicRecorder
from .features import FeatureExtractor, AUDIO_FEATURES, FEATURE_DIM
from .emotion_model import EmotionModel, VOICE_LABELS, VoiceResult
from .processor import VoiceProcessor

__all__ = [
    "AudioRecorder",
    "MicRecorder",
    "FeatureExtractor",
    "AUDIO_FEATURES",
    "FEATURE_DIM",
    "EmotionModel",
    "VOICE_LABELS",
    "VoiceResult",
    "VoiceProcessor",
]
