"""Multimodal Emotion Engine (MEE) V1 — Facially Expression / Voice Affective State Estimation.

Public entry point: import EmotionEngine from here or directly from mee.api.engine.
"""

__version__ = "0.1.0"

from mee.api.engine import EmotionEngine, MEEConfig
from mee.fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig
from mee.state.history import EmotionHistory
from mee.state.estimator import TrendConfig, TrendResult, analyze_trend

__all__ = [
    "EmotionEngine",
    "MEEConfig",
    # TASK_MEE_006 Subtask 4: fusion + state exports
    "EmotionFusion",
    "EmotionFusionConfig",
    "EmotionHistory",
    "TrendConfig",
    "TrendResult",
    "analyze_trend",
]
