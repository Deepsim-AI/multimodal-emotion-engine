"""TASK_MEE_006: Deterministic trend analysis over emotion history.

``analyze_trend`` inspects the last ``n`` samples in an ``EmotionHistory``
and classifies the emotional trajectory as one of:

- ``"stable"``     — the dominant emotion has not changed and confidence
                     variation is within ``conf_threshold``
- ``"improving"``  — confidence for the *current* dominant emotion is
                     rising across the window (or the dominant emotion
                     itself is the same and recent samples are more
                     confident than older ones)
- ``"declining"``  — the mirror image of improving
- ``"unstable"``   — the dominant emotion changed within the window, or
                     no single emotion dominates

The function is fully deterministic: same history + config → same output.
No clock, no randomness.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

from .history import EmotionHistory


@dataclass
class TrendConfig:
    """Thresholds governing trend classification."""
    window: int = 5
    conf_threshold: float = 0.1


@dataclass
class TrendResult:
    """Outcome of a single trend analysis pass."""
    trend: str
    dominant_emotion: Optional[str]
    dominant_confidence: Optional[float]
    samples_analyzed: int


def analyze_trend(
    history: EmotionHistory,
    config: Optional[TrendConfig] = None,
) -> TrendResult:
    """Classify the emotional trajectory over the last ``config.window``
    samples in ``history``.

    Parameters
    ----------
    history:
        The emotion history buffer.
    config:
        Classification thresholds. Defaults to ``TrendConfig()``.

    Returns
    -------
    TrendResult
        One of ``stable`` / ``improving`` / ``declining`` / ``unstable``.
    """
    cfg = config or TrendConfig()

    # Take the most recent `window` samples (or fewer if history is short).
    n = min(cfg.window, history.size)
    if n < 2:
        # Not enough data to classify a trend — report the current sample
        # as stable if present, else unstable.
        if history.size == 1:
            emotion, conf = history.items[0]
            return TrendResult("stable", emotion, conf, 1)
        return TrendResult("unstable", None, None, 0)

    recent = history.items[-n:]
    emotions = [e for e, _ in recent]
    confidences = [c for _, c in recent]

    # Determine the dominant emotion (most frequent; tie → most recent).
    counts = Counter(emotions)
    max_count = max(counts.values())
    tied = [e for e, c in counts.items() if c == max_count]
    if len(tied) > 1:
        dominant = tied[-1]  # most recent wins ties
    else:
        dominant = tied[0]

    # If the dominant emotion never appears in every sample, the stream is
    # shifting — classify as unstable.
    if max_count < n:
        # Not strictly every sample, but a single dominant label still holds.
        # If less than 50% of samples are the dominant emotion → unstable.
        if max_count < n / 2:
            dominant_conf = _mean_confidence(recent, dominant)
            return TrendResult("unstable", dominant, dominant_conf, n)

    dominant_conf = _mean_confidence(recent, dominant)

    # Compare early vs late confidence for the dominant emotion only.
    dom_confidences = [c for e, c in recent if e == dominant]
    if len(dom_confidences) < 2:
        return TrendResult("unstable", dominant, dominant_conf, n)

    half = len(dom_confidences) // 2
    early_mean = sum(dom_confidences[:half]) / half
    late_mean = sum(dom_confidences[half:]) / (len(dom_confidences) - half)
    delta = late_mean - early_mean

    if delta > cfg.conf_threshold:
        trend = "improving"
    elif delta < -cfg.conf_threshold:
        trend = "declining"
    else:
        trend = "stable"

    return TrendResult(trend, dominant, dominant_conf, n)


def _mean_confidence(samples, emotion: str) -> Optional[float]:
    vals = [c for e, c in samples if e == emotion]
    if not vals:
        return None
    return sum(vals) / len(vals)
