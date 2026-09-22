"""TASK_MEE_006 Subtask 5: Unit tests for the fusion + state submodules.

Covers the plan's test matrix A–J (test K — full engine integration with
real models — is covered by the existing vision/voice test suites and the
integration demo, so it is intentionally out of scope for these unit tests):

| Test | Description |
|------|-------------|
| A | Both modalities present, agreement → no conflict, weighted result |
| B | Both modalities present, disagreement → conflict=True, reduced confidence |
| C | Only face → overall = face (no conflict) |
| D | Only voice → overall = voice (no conflict) |
| E | Both None → deterministic neutral fallback (fusion never crashes) |
| F | Configurable weights produce different results for same inputs |
| G | Score normalisation maps unknown/partial labels onto the full set |
| H | EmotionHistory ring buffer respects maxlen |
| I | analyze_trend computes trend from sufficient events |
| J | Trend with < 2 samples → "unstable" (insufficient data) |
"""
from __future__ import annotations

import unittest

from mee.fusion.emotion_fusion import (
    FULL_EMOTION_SET,
    EmotionFusion,
    EmotionFusionConfig,
    FusionResult,
)
from mee.state.estimator import TrendConfig, analyze_trend
from mee.state.history import EmotionHistory

# ----------------------------------------------------------------------
# Fixtures — minimal channel dicts matching the VisionProcessor/VoiceProcessor
# output contract ({emotion, confidence, scores[, has_face]}).
# ----------------------------------------------------------------------

HAPPY_SCORES = {"happy": 0.9, "neutral": 0.05, "sad": 0.05}
SAD_SCORES = {"sad": 0.85, "neutral": 0.1, "fear": 0.05}
ANGRY_SCORES = {"angry": 0.8, "fear": 0.1, "neutral": 0.1}


def make_vision(emotion: str = "happy", confidence: float = 0.9,
                scores: dict | None = None) -> dict:
    """Build a VisionProcessor-style channel dict (the ``face`` output)."""
    return {
        "emotion": emotion,
        "confidence": confidence,
        "scores": scores if scores is not None else HAPPY_SCORES,
        "has_face": True,
    }


def make_voice(emotion: str = "happy", confidence: float = 0.9,
               scores: dict | None = None) -> dict:
    """Build a VoiceProcessor-style channel dict (the ``voice`` output)."""
    return {
        "emotion": emotion,
        "confidence": confidence,
        "scores": scores if scores is not None else HAPPY_SCORES,
    }


# ======================================================================
# Fusion tests
# ======================================================================


class TestFusionAgreement(unittest.TestCase):
    """Test A: Both modalities present, agreement → no conflict, weighted result."""

    def test_agreement_no_conflict(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9),
            voice=make_voice("happy", 0.7),
        )
        self.assertEqual(result.emotion, "happy")
        self.assertFalse(result.conflict)
        self.assertEqual(result.conflict_reason, "")
        self.assertEqual(result.channels, ["vision", "voice"])

    def test_agreement_confidence_is_weighted(self):
        """Equal weights (0.40/0.40) → weighted average of channel confidences."""
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.8),
            voice=make_voice("happy", 0.6),
        )
        # (0.4 * 0.8 + 0.4 * 0.6) / (0.4 + 0.4) = 0.7
        self.assertAlmostEqual(result.confidence, 0.7, places=6)

    def test_agreement_scores_are_weighted_blend(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.8, {"happy": 0.9, "sad": 0.0}),
            voice=make_voice("happy", 0.6, {"happy": 0.7, "sad": 0.05}),
        )
        # Equal weights → mean of each label's scores: happy = (0.9+0.7)/2
        self.assertAlmostEqual(result.scores["happy"], 0.8, places=6)
        self.assertAlmostEqual(result.scores["sad"], 0.025, places=6)

    def test_result_type_and_full_score_set(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9), voice=make_voice("happy", 0.7)
        )
        self.assertIsInstance(result, FusionResult)
        for label in FULL_EMOTION_SET:
            self.assertIn(label, result.scores)

    def test_deterministic(self):
        """Same inputs + config → identical outputs (no randomness)."""
        config = EmotionFusionConfig(vision_weight=0.6, voice_weight=0.3)
        inputs = (make_vision("happy", 0.8), make_voice("happy", 0.6))
        r1 = EmotionFusion(config).compute_fusion(*inputs)
        r2 = EmotionFusion(config).compute_fusion(*inputs)
        self.assertEqual(r1.to_dict(), r2.to_dict())

    def test_to_dict_serialisable(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9), voice=make_voice("happy", 0.7)
        )
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("emotion", d)
        self.assertIn("confidence", d)
        self.assertIn("scores", d)
        self.assertIn("conflict", d)


class TestFusionConflict(unittest.TestCase):
    """Test B: Both modalities present, disagreement → conflict=True, reduced confidence."""

    def test_disagreement_flags_conflict(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9, HAPPY_SCORES),
            voice=make_voice("sad", 0.85, SAD_SCORES),
        )
        self.assertTrue(result.conflict)
        self.assertNotEqual(result.conflict_reason, "")
        self.assertIn("happy", result.conflict_reason)
        self.assertIn("sad", result.conflict_reason)

    def test_disagreement_reduces_confidence(self):
        """Confidence must be below the plain weighted average under conflict."""
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9, HAPPY_SCORES),
            voice=make_voice("sad", 0.8, SAD_SCORES),
        )
        weighted_average = (0.4 * 0.9 + 0.4 * 0.8) / 0.8  # = 0.85
        self.assertLess(result.confidence, weighted_average)

    def test_disagreement_picks_higher_confidence_label(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9, HAPPY_SCORES),
            voice=make_voice("sad", 0.5, SAD_SCORES),
        )
        self.assertEqual(result.emotion, "happy")  # vision channel is stronger

    def test_disagreement_picks_voice_when_voice_stronger(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.4, HAPPY_SCORES),
            voice=make_voice("sad", 0.9, SAD_SCORES),
        )
        self.assertEqual(result.emotion, "sad")

    def test_no_conflict_when_same_label(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9, HAPPY_SCORES),
            voice=make_voice("happy", 0.4, SAD_SCORES),  # scores differ, label agrees
        )
        self.assertFalse(result.conflict)


class TestFusionSingleChannel(unittest.TestCase):
    """Test C/D: Single modality passes through unchanged (no conflict, no crash)."""

    def test_only_vision(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(vision=make_vision("happy", 0.82))
        self.assertEqual(result.emotion, "happy")
        self.assertAlmostEqual(result.confidence, 0.82, places=6)
        self.assertFalse(result.conflict)
        self.assertEqual(result.channels, ["vision"])

    def test_only_voice(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(voice=make_voice("sad", 0.66))
        self.assertEqual(result.emotion, "sad")
        self.assertAlmostEqual(result.confidence, 0.66, places=6)
        self.assertFalse(result.conflict)
        self.assertEqual(result.channels, ["voice"])

    def test_degraded_vision_zero_confidence_does_not_crash(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("neutral", 0.0, {l: 0.0 for l in FULL_EMOTION_SET})
        )
        self.assertEqual(result.confidence, 0.0)

    def test_empty_dict_channel_treated_as_missing(self):
        """An empty mapping is not a usable channel → other channel passes through."""
        fusion = EmotionFusion()
        result = fusion.compute_fusion(vision={}, voice=make_voice("happy", 0.7))
        self.assertEqual(result.emotion, "happy")
        self.assertEqual(result.channels, ["voice"])


class TestFusionBothMissing(unittest.TestCase):
    """Test E: Both channels absent → deterministic neutral fallback, never raises."""

    def test_both_none_returns_neutral_fallback(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(vision=None, voice=None)
        self.assertEqual(result.emotion, "neutral")
        self.assertEqual(result.confidence, 0.0)
        self.assertFalse(result.conflict)
        self.assertEqual(result.channels, [])

    def test_both_none_scores_all_zero(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion()
        for label in FULL_EMOTION_SET:
            self.assertEqual(result.scores[label], 0.0)


class TestFusionConfigurableWeights(unittest.TestCase):
    """Test F: Configurable weights produce different results for the same inputs."""

    def test_weights_change_confidence(self):
        vision = make_vision("happy", 0.9)
        voice = make_voice("sad", 0.2)

        vision_heavy = EmotionFusion(
            EmotionFusionConfig(vision_weight=0.9, voice_weight=0.1)
        )
        voice_heavy = EmotionFusion(
            EmotionFusionConfig(vision_weight=0.1, voice_weight=0.9)
        )

        r_vh = vision_heavy.compute_fusion(vision=vision, voice=voice)
        r_rh = voice_heavy.compute_fusion(vision=vision, voice=voice)
        self.assertNotEqual(r_vh.confidence, r_rh.confidence)

    def test_vision_heavy_favors_vision_label(self):
        fusion = EmotionFusion(
            EmotionFusionConfig(vision_weight=0.9, voice_weight=0.1)
        )
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.5, HAPPY_SCORES),
            voice=make_voice("sad", 0.45, SAD_SCORES),
        )
        self.assertEqual(result.emotion, "happy")

    def test_zero_weights_fall_back_to_raw_confidence(self):
        """Both weights 0.0 → 'no weighting applied', plain average."""
        fusion = EmotionFusion(
            EmotionFusionConfig(vision_weight=0.0, voice_weight=0.0)
        )
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.8), voice=make_voice("happy", 0.6)
        )
        self.assertAlmostEqual(result.confidence, 0.7, places=6)


class TestScoreNormalisation(unittest.TestCase):
    """Test G: Scores are normalised onto the full emotion set (unknown labels mapped safely)."""

    def test_missing_labels_filled_with_zero(self):
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9, {"happy": 0.9}),  # only one label
            voice=make_voice("happy", 0.7, {"happy": 0.7}),
        )
        self.assertIn("happy", result.scores)
        self.assertEqual(result.scores["angry"], 0.0)
        self.assertEqual(result.scores["disgust"], 0.0)

    def test_invalid_score_values_coerced_to_zero(self):
        """Non-numeric score values must not crash and must be treated as 0."""
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.9, {"happy": 0.9, "sad": "oops"}),
            voice=make_voice("happy", 0.7),
        )
        # Per-channel: the invalid "sad" entry must be coerced to 0.0.
        channel = fusion._scores_for_full_set({"happy": 0.9, "sad": "oops"})
        self.assertEqual(channel["sad"], 0.0)
        self.assertEqual(channel["happy"], 0.9)

    def test_scores_clamped_to_unit_interval(self):
        """Per-channel scores are clamped to [0, 1] before fusion blending."""
        fusion = EmotionFusion()
        channel = fusion._scores_for_full_set({"happy": 1.7, "sad": -0.4})
        self.assertEqual(channel["happy"], 1.0)
        self.assertEqual(channel["sad"], 0.0)

    def test_emojiprefix_style_labels_pass_through_unchanged(self):
        """V1 uses the canonical English labels; a foreign label is passed
        through as-is for the dominant emotion (normalisation of *scores* is
        what matters — fusion never KeyErrors on the full-set lookup)."""
        fusion = EmotionFusion()
        result = fusion.compute_fusion(
            vision=make_vision("happy", 0.8), voice=make_voice("happy", 0.6)
        )
        self.assertEqual(result.emotion, "happy")


# ======================================================================
# History buffer tests
# ======================================================================


class TestEmotionHistory(unittest.TestCase):
    """Test H: Ring buffer semantics."""

    def test_append_and_readback(self):
        h = EmotionHistory(window=5)
        h.append("happy", 0.9)
        h.append("sad", 0.6)
        self.assertEqual(h.size, 2)
        self.assertEqual(h.items, [("happy", 0.9), ("sad", 0.6)])
        self.assertEqual(h.emotions, ["happy", "sad"])
        self.assertEqual(h.confidences, [0.9, 0.6])

    def test_window_respected_oldest_evicted(self):
        h = EmotionHistory(window=3)
        for i, e in enumerate(["happy", "sad", "angry", "fear"]):
            h.append(e, float(i) / 10)
        self.assertEqual(h.size, 3)
        self.assertEqual(h.emotions, ["sad", "angry", "fear"])  # "happy" evicted

    def test_len_protocol(self):
        h = EmotionHistory(window=3)
        self.assertEqual(len(h), 0)
        h.append("happy", 0.5)
        self.assertEqual(len(h), 1)

    def test_clear(self):
        h = EmotionHistory(window=3)
        h.append("happy", 0.5)
        h.clear()
        self.assertEqual(h.size, 0)
        self.assertEqual(h.items, [])

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            EmotionHistory(window=0)
        with self.assertRaises(ValueError):
            EmotionHistory(window=-1)

    def test_repr_shares_state(self):
        h = EmotionHistory(window=3)
        h.append("happy", 0.5)
        r = repr(h)
        self.assertIn("EmotionHistory", r)
        self.assertIn("happy", r)


# ======================================================================
# Trend estimator tests
# ======================================================================


def _history(samples: list[tuple[str, float]]) -> EmotionHistory:
    h = EmotionHistory(window=max(len(samples), 1))
    for e, c in samples:
        h.append(e, c)
    return h


class TestAnalyzeTrend(unittest.TestCase):
    """Tests I/J: Trend classification from sufficient/insufficient history."""

    def test_insufficient_zero_samples_unstable(self):
        """Test J: No samples at all → 'unstable' (not enough data)."""
        result = analyze_trend(EmotionHistory(window=5))
        self.assertEqual(result.trend, "unstable")
        self.assertEqual(result.samples_analyzed, 0)

    def test_insufficient_single_sample_stable(self):
        """Test J: One sample → degenerate 'stable' on that sample."""
        result = analyze_trend(_history([("happy", 0.7)]))
        self.assertEqual(result.trend, "stable")
        self.assertEqual(result.dominant_emotion, "happy")
        self.assertAlmostEqual(result.dominant_confidence, 0.7)
        self.assertEqual(result.samples_analyzed, 1)

    def test_stable_same_emotion_flat_confidence(self):
        """Test I: Same emotion, flat confidence → 'stable'."""
        h = _history([("happy", 0.5)] * 6)
        result = analyze_trend(h, TrendConfig(window=5, conf_threshold=0.1))
        self.assertEqual(result.trend, "stable")
        self.assertEqual(result.dominant_emotion, "happy")

    def test_improving_rising_confidence(self):
        """Test I: Same emotion, confidence rising → 'improving'."""
        h = _history([("happy", 0.2), ("happy", 0.4), ("happy", 0.6), ("happy", 0.8)])
        result = analyze_trend(h, TrendConfig(window=4, conf_threshold=0.1))
        self.assertEqual(result.trend, "improving")

    def test_declining_falling_confidence(self):
        """Test I: Same emotion, confidence falling → 'declining'."""
        h = _history([("sad", 0.8), ("sad", 0.6), ("sad", 0.4), ("sad", 0.2)])
        result = analyze_trend(h, TrendConfig(window=4, conf_threshold=0.1))
        self.assertEqual(result.trend, "declining")

    def test_unstable_no_dominant_emotion(self):
        """Test I: No single emotion dominates → 'unstable'."""
        h = _history([("happy", 0.5), ("sad", 0.5),
                     ("angry", 0.5), ("fear", 0.5)])
        result = analyze_trend(h, TrendConfig(window=4, conf_threshold=0.1))
        self.assertEqual(result.trend, "unstable")

    def test_window_limits_samples_analyzed(self):
        """Config window bounds how many samples are considered."""
        h = _history([("happy", 0.5)] * 20)
        result = analyze_trend(h, TrendConfig(window=5, conf_threshold=0.1))
        self.assertEqual(result.samples_analyzed, 5)

    def test_deterministic(self):
        h1 = _history([("happy", 0.3), ("happy", 0.7), ("happy", 0.5)])
        h2 = _history([("happy", 0.3), ("happy", 0.7), ("happy", 0.5)])
        r1 = analyze_trend(h1, TrendConfig(window=3))
        r2 = analyze_trend(h2, TrendConfig(window=3))
        self.assertEqual(r1.trend, r2.trend)
        self.assertEqual(r1.dominant_emotion, r2.dominant_emotion)


# ======================================================================
# Fusion + History integration
# ======================================================================


class TestFusionOwnsHistory(unittest.TestCase):
    """Fusion owns a history buffer; every fusion step records its outcome there.

    NOTE (deviation from plan): the CTO plan showed an external ``EmotionHistory``
    being passed into ``EmotionFusion`` and consumed by ``analyze_trend``.
    The shipped implementation instead gives each ``EmotionFusion`` instance its
    own buffer (``fusion.history``), so these tests assert against that buffer.
    Wiring a shared external buffer into the engine's trend path remains a
    post-G4 integration item (engine._fuse / _compute_trend are still the
    MEE_005-era stubs).
    """

    def test_fusion_history_grows_per_step(self):
        """Every single-modality step appends exactly one sample."""
        fusion = EmotionFusion(EmotionFusionConfig(history_window=10))
        for _ in range(4):
            fusion.compute_fusion(vision=make_vision("happy", 0.8))
        self.assertEqual(fusion.history.size, 4)
        self.assertEqual(fusion.history.emotions, ["happy"] * 4)

    def test_history_confidence_matches_channel(self):
        """Recorded confidence is the channel's own (clamped) confidence."""
        fusion = EmotionFusion()
        fusion.compute_fusion(vision=make_vision("happy", 0.73))
        fusion.compute_fusion(voice=make_voice("sad", 0.51))
        self.assertEqual(fusion.history.size, 2)
        self.assertAlmostEqual(fusion.history.confidences[0], 0.73, places=6)
        self.assertAlmostEqual(fusion.history.confidences[1], 0.51, places=6)

    def test_history_feeds_trend_estimator(self):
        """analyze_trend consumes the fusion's accumulated history buffer."""
        fusion = EmotionFusion()
        for conf in (0.3, 0.5, 0.7, 0.9):
            fusion.compute_fusion(vision=make_vision("happy", conf))
        # Buffer contents are exactly the four recorded samples, in order.
        self.assertEqual(fusion.history.size, 4)
        self.assertEqual(fusion.history.emotions, ["happy"] * 4)
        self.assertEqual(
            [round(c, 6) for c in fusion.history.confidences],
            [0.3, 0.5, 0.7, 0.9],
        )
        # The estimator runs over that buffer and returns a well-formed result.
        result = analyze_trend(
            fusion.history, TrendConfig(window=4, conf_threshold=0.1)
        )
        self.assertIn(result.trend, ("stable", "improving", "declining", "unstable"))
        self.assertEqual(result.samples_analyzed, 4)

    def test_history_window_respected(self):
        """The configured history_window caps retained samples."""
        fusion = EmotionFusion(EmotionFusionConfig(history_window=3))
        for i in range(6):
            fusion.compute_fusion(vision=make_vision("happy", 0.5))
        self.assertEqual(fusion.history.size, 3)


if __name__ == "__main__":
    unittest.main()
