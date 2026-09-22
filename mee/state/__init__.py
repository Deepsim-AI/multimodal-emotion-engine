# State submodule — temporal state tracking
# TASK_MEE_006: history buffer + deterministic trend estimator

from .history import EmotionHistory
from .estimator import TrendConfig, TrendResult, analyze_trend

__all__ = [
    "EmotionHistory",
    "TrendConfig",
    "TrendResult",
    "analyze_trend",
]
