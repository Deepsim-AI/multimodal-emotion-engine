"""Multimodal Emotion Engine (MEE) V1 — Facially Expression / Voice Affective State Estimation.

Public entry point: import EmotionEngine from here or directly from mee.api.engine.
"""

__version__ = "0.1.0"

from mee.api.engine import EmotionEngine, MEEConfig

__all__ = ["EmotionEngine", "MEEConfig"]
