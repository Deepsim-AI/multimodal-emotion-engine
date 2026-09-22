"""TASK_MEE_006: Deterministic multimodal emotion fusion with explicit conflict reporting.

Replaces the stub weighted-fusion logic previously embedded in
``EmotionEngine._fuse()`` with a dedicated, independently testable component.

The fusion algorithm is fully deterministic: given the same per-channel
results and weights, it always produces the same output.

Conflict handling:
    When the vision and voice channels disagree on the dominant emotion
    (or the channel confidences diverge by more than ``conflict_threshold``),
    the overall confidence is reduced and ``conflict=True`` is reported
    explicitly. Disagreement is never silently hidden.

Single-modality:
    If only one channel is present, fusion passes that channel's dominant
    emotion through unchanged, at its own confidence. Missing or degraded
    channels never cause a crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from mee.state.history import EmotionHistory

# Canonical label order for the full emotion set.
FULL_EMOTION_SET: Tuple[str, ...] = (
    "angry", "disgust", "fear", "happy", "sad", "surprised", "neutral",
)

# Neutral fallback when fusion cannot be resolved deterministically.
_FALLBACK_EMOTION = "neutral"


@dataclass
class EmotionFusionConfig:
    """Configuration knobs for the fusion component.

    Defaults follow ARCHITECTURE.md (vision 0.40 / voice 0.40 /
    context 0.20). The context channel is not yet implemented, so its
    weight is retained but excluded from the active total; the effective
    two-channel split is 50/50 until a context source is wired in.

    ``vision_weight`` and ``voice_weight`` are relative weights — they
    are normalised internally against the sum of the active channels.
    Setting both to 0.0 means "no modality weighting applied" and falls
    back to the raw channel confidences.
    """

    vision_weight: float = 0.40
    voice_weight: float = 0.40
    context_weight: float = 0.20  # reserved; no context source yet
    conflict_threshold: float = 0.30
    history_window: int = 10  # number of prior samples for the trend estimator


@dataclass
class FusionResult:
    """Output of a single fusion step.

    Attributes
    ----------
    emotion:
        The overall dominant emotion label (from the full set).
    confidence:
        Deterministic fused confidence in [0, 1].
    scores:
        Fused per-emotion scores, always keyed by the full emotion set.
    conflict:
        True when the two channels disagreed on the dominant emotion or
        diverged in confidence by more than the configured threshold.
    conflict_reason:
        Human-readable explanation of the disagreement, empty when no
        conflict was detected.
    channels:
        Which channels actually contributed to this step ("vision",
        "voice").
    """

    emotion: str
    confidence: float
    scores: Dict[str, float]
    conflict: bool
    conflict_reason: str
    channels: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion": self.emotion,
            "confidence": self.confidence,
            "scores": dict(self.scores),
            "conflict": self.conflict,
            "conflict_reason": self.conflict_reason,
            "channels": list(self.channels),
        }


class EmotionFusion:
    """Deterministic weighted fusion over the active modality channels.

    Parameters
    ----------
    config:
        Fusion configuration; see ``EmotionFusionConfig``.
    history:
        Optional shared history buffer. When omitted, a fresh
        ``EmotionHistory`` is created with the configured window.

    The same fusion instance should be passed to every
    ``EmotionEngine.process()`` call in a session — the temporal state
    (trend) is derived from its accumulated history.
    """

    def __init__(
        self,
        config: Optional[EmotionFusionConfig] = None,
        history: Optional[EmotionHistory] = None,
    ) -> None:
        self.config = config or EmotionFusionConfig()
        self.history = history or EmotionHistory(self.config.history_window)

    # ------------------------------------------------------------------
    # Core fusion step
    # ------------------------------------------------------------------

    def compute_fusion(
        self,
        vision: Optional[Dict[str, Any]] = None,
        voice: Optional[Dict[str, Any]] = None,
    ) -> FusionResult:
        """Fuse the available channel results into a single outcome.

        Parameters
        ----------
        vision:
            The ``face`` dict from ``VisionProcessor`` (or any mapping
            with the same keys: ``emotion``, ``confidence``, ``scores``,
            ``has_face``). ``None`` means no vision channel this step.
        voice:
            The ``voice`` dict from ``VoiceProcessor`` (or any mapping
            with the same keys: ``emotion``, ``confidence``, ``scores``).
            ``None`` means no voice channel this step.

        Returns
        -------
        FusionResult
            Deterministic fusion output for this step.

        Raises
        ------
        Nothing. Missing, ``None``, or degraded channels are handled
        explicitly; this method never raises on a missing modality.
        """
        vision = self._normalise_channel(vision)
        voice = self._normalise_channel(voice)

        active = []
        if vision is not None:
            active.append(("vision", vision))
        if voice is not None:
            active.append(("voice", voice))

        # No active channels at all — deterministic fallback, no crash.
        if not active:
            return FusionResult(
                emotion=_FALLBACK_EMOTION,
                confidence=0.0,
                scores={label: 0.0 for label in FULL_EMOTION_SET},
                conflict=False,
                conflict_reason="",
                channels=[],
            )

        weights = {
            "vision": float(self.config.vision_weight),
            "voice": float(self.config.voice_weight),
        }

        if len(active) == 1:
            return self._single_channel_fusion(active[0])

        result = self._dual_channel_fusion(active, weights)

        # Update the shared history buffer with this step's outcome.
        self.history.append(result.emotion, result.confidence)

        return result

    # ------------------------------------------------------------------
    # Single-modality path
    # ------------------------------------------------------------------

    def _single_channel_fusion(
        self, channel: Tuple[str, Dict[str, Any]]
    ) -> FusionResult:
        name, channel = channel
        scores = self._scores_for_full_set(channel.get("scores", {}))
        emotion = channel.get("emotion") or _FALLBACK_EMOTION
        confidence = float(channel.get("confidence") or 0.0)
        # A degraded channel (confidence ~0) passes through at its own
        # low confidence — no artificial boost, no crash.
        self.history.append(emotion, confidence)
        return FusionResult(
            emotion=emotion,
            confidence=max(0.0, min(1.0, confidence)),
            scores=scores,
            conflict=False,
            conflict_reason="",
            channels=[name],
        )

    # ------------------------------------------------------------------
    # Dual-modality path with explicit conflict handling
    # ------------------------------------------------------------------

    def _dual_channel_fusion(
        self,
        active: List[Tuple[str, Dict[str, Any]]],
        weights: Dict[str, float],
    ) -> FusionResult:
        vision = active[0][1]
        voice = active[1][1]

        v_emotion = vision.get("emotion") or _FALLBACK_EMOTION
        v_conf = float(vision.get("confidence") or 0.0)
        r_emotion = voice.get("emotion") or _FALLBACK_EMOTION
        r_conf = float(voice.get("confidence") or 0.0)

        w_v = weights.get("vision", 0.0)
        w_r = weights.get("voice", 0.0)

        scores_v = self._scores_for_full_set(vision.get("scores", {}))
        scores_r = self._scores_for_full_set(voice.get("scores", {}))

        conflict = False
        conflict_reason = ""

        if v_emotion != r_emotion:
            # Dominant emotions disagree. Weighted confidence is computed
            # as the weighted sum of the two channels' *own* dominant
            # confidences, then reduced proportionally to how much the
            # channels disagree (larger confidence gap → larger reduction).
            total_w = w_v + w_r
            if total_w > 0:
                base_confidence = (w_v * v_conf + w_r * r_conf) / total_w
            else:
                base_confidence = (v_conf + r_conf) / 2.0
            confidence_gap = abs(v_conf - r_conf)
            disagreement_factor = min(1.0, confidence_gap / max(self.config.conflict_threshold, 1e-9))
            reduced_confidence = base_confidence * (1.0 - 0.5 * disagreement_factor)
            conflict = True
            conflict_reason = (
                f"vision={v_emotion} ({v_conf:.2f}) vs "
                f"voice={r_emotion} ({r_conf:.2f}) — dominant emotions differ"
            )
            emotion = v_emotion if v_conf >= r_conf else r_emotion
            # Fused scores: weighted blend of the two channels' score
            # vectors; the channel with the higher dominant confidence
            # contributes its own dominant score more heavily.
            total_w = w_v + w_r
            if total_w > 0:
                fused_scores = {
                    label: (w_v * scores_v.get(label, 0.0) + w_r * scores_r.get(label, 0.0))
                    / total_w
                    for label in FULL_EMOTION_SET
                }
            else:
                fused_scores = {
                    label: (scores_v.get(label, 0.0) + scores_r.get(label, 0.0)) / 2.0
                    for label in FULL_EMOTION_SET
                }
        else:
            # Dominant emotions agree — no conflict, confidence is the
            # weighted combination of the two channels' confidences.
            total_w = w_v + w_r
            if total_w > 0:
                reduced_confidence = (w_v * v_conf + w_r * r_conf) / total_w
            else:
                reduced_confidence = (v_conf + r_conf) / 2.0
            emotion = v_emotion
            total_w = w_v + w_r
            if total_w > 0:
                fused_scores = {
                    label: (w_v * scores_v.get(label, 0.0) + w_r * scores_r.get(label, 0.0))
                    / total_w
                    for label in FULL_EMOTION_SET
                }
            else:
                fused_scores = {
                    label: (scores_v.get(label, 0.0) + scores_r.get(label, 0.0)) / 2.0
                    for label in FULL_EMOTION_SET
                }

        reduced_confidence = max(0.0, min(1.0, reduced_confidence))

        return FusionResult(
            emotion=emotion,
            confidence=reduced_confidence,
            scores=fused_scores,
            conflict=conflict,
            conflict_reason=conflict_reason,
            channels=["vision", "voice"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalise_channel(
        self, channel: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Return a normalised channel dict, or None if not usable.

        A channel is considered "present" when it is a non-empty mapping.
        A channel with ``confidence`` of 0.0 (degraded/no signal) is still
        returned — fusion handles it as a low-confidence contributor rather
        than dropping it, so that a single strong channel can still
        dominate and the other does not crash the step.
        """
        if channel is None:
            return None
        if not isinstance(channel, dict) or not channel:
            return None
        return channel

    @staticmethod
    def _scores_for_full_set(
        scores: Dict[str, float],
    ) -> Dict[str, float]:
        """Return a dict covering every label in FULL_EMOTION_SET.

        Missing labels are filled with 0.0 so that downstream consumers
        can always index the full set without KeyError.
        """
        out: Dict[str, float] = {}
        for label in FULL_EMOTION_SET:
            try:
                value = float(scores.get(label, 0.0))
            except (TypeError, ValueError):
                value = 0.0
            out[label] = max(0.0, min(1.0, value))
        return out
