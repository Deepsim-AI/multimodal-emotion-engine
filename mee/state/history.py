"""TASK_MEE_006: Fixed-size emotion history buffer.

``EmotionHistory`` stores the most recent ``window`` (emotion, confidence)
pairs in chronological order. It is a pure data structure with no model
dependencies — the trend estimator and fusion component both consume it.

Determinism: ``append`` is the only mutation; ``items``, ``emotions``, and
``confidence`` are read-only views. No clock, no randomness.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, List, Tuple


class EmotionHistory:
    """Fixed-window ring buffer of (emotion, confidence) samples.

    Parameters
    ----------
    window:
        Maximum number of samples retained. Must be >= 1; larger values
        retain more history but cost a small fixed memory overhead.
    """

    def __init__(self, window: int = 10) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self._window = window
        self._samples: Deque[Tuple[str, float]] = deque(maxlen=window)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def append(self, emotion: str, confidence: float) -> None:
        """Record one sample. Oldest samples are evicted when full."""
        self._samples.append((str(emotion), float(confidence)))

    def clear(self) -> None:
        """Remove all samples."""
        self._samples.clear()

    # ------------------------------------------------------------------
    # Read-only views
    # ------------------------------------------------------------------

    @property
    def window(self) -> int:
        """Configured maximum number of samples."""
        return self._window

    @property
    def size(self) -> int:
        """Number of samples currently stored (may be < window)."""
        return len(self._samples)

    @property
    def items(self) -> List[Tuple[str, float]]:
        """All stored samples, oldest first."""
        return list(self._samples)

    @property
    def emotions(self) -> List[str]:
        """Emotion labels, oldest first."""
        return [emotion for emotion, _ in self._samples]

    @property
    def confidences(self) -> List[float]:
        """Confidence values, oldest first."""
        return [confidence for _, confidence in self._samples]

    def __len__(self) -> int:
        return self.size

    def __repr__(self) -> str:
        return (
            f"EmotionHistory(window={self._window}, "
            f"size={self.size}, emotions={self.emotions})"
        )
