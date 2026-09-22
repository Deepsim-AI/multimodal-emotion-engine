"""TASK_MEE_009: End-to-end validation of the full MEE pipeline.

Integration tests that exercise ``EmotionEngine.process()`` — the real
public API path including fusion, history recording, trend computation,
and latency measurement — using synthetic channel inputs.

Method (monkey-patch, per CTO plan Risk #1):
    ``_infer_vision`` / ``_infer_voice`` are patched to return
    predetermined channel results from the scenario data. ``process()``
    then runs its full real code path (``_fuse`` → fusion history
    append → ``_compute_trend``) against those results. This is true
    E2E validation of the pipeline glue without requiring live hardware
    or model inference.

Scenario definitions live in ``tests/scenario_data.py`` (shared with
the ``tools/evaluate_scenarios.py`` harness).
"""

from __future__ import annotations

import numpy as np
import pytest

from mee.api.engine import EmotionEngine, MEEConfig, _MEEFaceResult
from tests.scenario_data import SCENARIOS, Scenario, ScenarioStep, get_scenario

# Trivial synthetic inputs — the patched _infer_* methods ignore their
# arguments and return predetermined results, so the actual array values
# are irrelevant. They exist only to satisfy the process() contract.
_SYNTH_FRAME = np.zeros((10, 10, 3), dtype=np.uint8)
_SYNTH_AUDIO = np.zeros(640, dtype=np.float32)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _face_result(step: ScenarioStep) -> _MEEFaceResult:
    """Build the _MEEFaceResult that _infer_vision returns for this step."""
    if step.face_emotion is None:
        return _MEEFaceResult()  # no face detected
    return _MEEFaceResult(
        emotion=step.face_emotion,
        confidence=step.face_confidence,
        scores={step.face_emotion: step.face_confidence},
        has_face=True,
    )


def _voice_result(step: ScenarioStep) -> dict | None:
    """Build the voice dict (or None) that _infer_voice returns."""
    if step.voice_emotion is None:
        return None  # no voice channel
    return {
        "emotion": step.voice_emotion,
        "confidence": step.voice_confidence,
        "scores": {step.voice_emotion: step.voice_confidence},
    }


def _engine_for_scenario(scenario: Scenario) -> EmotionEngine:
    """Create a fresh engine wired to emit this scenario's steps in order.

    Each step is advanced once (a shared ``current`` cell), and the vision
    and voice patches read their own fields of that same step — not two
    successive steps — so a step's face/voice pairing stays aligned.
    """
    engine = EmotionEngine(config=MEEConfig())
    steps = list(scenario.steps)
    state = {"i": 0}

    def _advance() -> ScenarioStep:
        step = steps[state["i"]]
        state["i"] += 1
        return step

    def _vision(frame=None) -> _MEEFaceResult:
        return _face_result(_advance())

    def _voice(audio=None) -> dict | None:
        # Reads the *same* step the vision path just advanced.
        return _voice_result(steps[state["i"] - 1])

    engine._infer_vision = _vision
    engine._infer_voice = _voice
    return engine


def _run_scenario(scenario: Scenario) -> list[dict]:
    """Run every step of the scenario; return the list of process() results."""
    engine = _engine_for_scenario(scenario)
    results = []
    for _ in scenario.steps:
        results.append(engine.process(video_frame=_SYNTH_FRAME, audio=_SYNTH_AUDIO))
    return results


def _final(results: list[dict]) -> dict:
    return results[-1]


# ----------------------------------------------------------------------
# Shared structural contract (all scenarios)
# ----------------------------------------------------------------------

class TestScenarioContract:
    """Every scenario's process() output must carry the full public contract."""

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
    def test_output_keys_present(self, scenario: Scenario):
        results = _run_scenario(scenario)
        assert len(results) == len(scenario.steps)
        for r in results:
            assert set(r.keys()) == {"face", "voice", "overall", "trend", "latency_ms"}
            assert set(r["overall"].keys()) == {"emotion", "confidence", "conflict"}
            assert r["face"] is not None
            assert isinstance(r["latency_ms"], (int, float))
            assert 0.0 <= r["overall"]["confidence"] <= 1.0

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
    def test_no_crash_on_any_step(self, scenario: Scenario):
        # process() must not raise on any synthetic input.
        results = _run_scenario(scenario)
        assert all("overall" in r for r in results)


# ======================================================================
# Scenario A — Neutral (vision-only)
# ======================================================================

class TestScenarioA_Neutral:
    @classmethod
    def setup_class(cls):
        cls.results = _run_scenario(get_scenario("A"))

    def test_overall_emotion_is_neutral(self):
        assert _final(self.results)["overall"]["emotion"] == "neutral"

    def test_no_conflict(self):
        assert _final(self.results)["overall"]["conflict"] is False

    def test_trend_is_stable(self):
        assert _final(self.results)["trend"] == "stable"

    def test_vision_only_channel(self):
        # Voice channel absent on every step.
        assert all(r["voice"] is None for r in self.results)
        # Face channel present on every step.
        assert all(r["face"]["has_face"] for r in self.results)

    def test_latency_under_100ms(self):
        assert all(r["latency_ms"] < 100.0 for r in self.results)


# ======================================================================
# Scenario B — Happy (both agree)
# ======================================================================

class TestScenarioB_Happy:
    @classmethod
    def setup_class(cls):
        cls.results = _run_scenario(get_scenario("B"))

    def test_overall_emotion_is_happy(self):
        assert _final(self.results)["overall"]["emotion"] == "happy"

    def test_no_conflict(self):
        assert _final(self.results)["overall"]["conflict"] is False

    def test_trend_is_stable(self):
        assert _final(self.results)["trend"] == "stable"

    def test_both_channels_present(self):
        assert all(r["face"]["has_face"] for r in self.results)
        assert all(r["voice"] is not None for r in self.results)


# ======================================================================
# Scenario C — Sad (vision-only)
# ======================================================================

class TestScenarioC_Sad:
    @classmethod
    def setup_class(cls):
        cls.results = _run_scenario(get_scenario("C"))

    def test_overall_emotion_is_sad(self):
        assert _final(self.results)["overall"]["emotion"] == "sad"

    def test_no_conflict(self):
        assert _final(self.results)["overall"]["conflict"] is False

    def test_trend_is_stable(self):
        assert _final(self.results)["trend"] == "stable"

    def test_vision_only_channel(self):
        assert all(r["voice"] is None for r in self.results)
        assert all(r["face"]["has_face"] for r in self.results)


# ======================================================================
# Scenario D — Frustrated (conflicting modalities) — KEY conflict test
# ======================================================================

class TestScenarioD_Frustrated_Conflict:
    @classmethod
    def setup_class(cls):
        cls.results = _run_scenario(get_scenario("D"))

    def test_conflict_is_true_on_every_step(self):
        # Every step has opposing dominant labels → conflict must persist.
        assert all(r["overall"]["conflict"] is True for r in self.results)

    def test_higher_confidence_label_wins(self):
        # face (happy, higher confidence) must beat voice (angry/sad)
        # on every step.
        assert all(r["overall"]["emotion"] == "happy" for r in self.results)

    def test_final_overall_emotion_is_happy(self):
        assert _final(self.results)["overall"]["emotion"] == "happy"

    def test_confident_channels_both_present(self):
        assert all(r["face"]["has_face"] and r["voice"] is not None
                   for r in self.results)

    def test_trend_stable_despite_conflict(self):
        # The dominant label never changes (happy), confidence varies
        # mildly within threshold → trend stays stable even in conflict.
        assert _final(self.results)["trend"] == "stable"


# ======================================================================
# Scenario E — Cross-over (emotion shift over time)
# ======================================================================

class TestScenarioE_Crossover:
    @classmethod
    def setup_class(cls):
        cls.results = _run_scenario(get_scenario("E"))

    def test_emotion_shifts_to_sad(self):
        # Final steps report sad; the overall emotion ends on sad.
        assert _final(self.results)["overall"]["emotion"] == "sad"

    def test_early_steps_happy_late_steps_sad(self):
        # Verify the temporal shift actually happened.
        assert self.results[0]["overall"]["emotion"] == "happy"
        assert self.results[-1]["overall"]["emotion"] == "sad"

    def test_no_conflict(self):
        # Both modalities always agree with each other → no conflict.
        assert _final(self.results)["overall"]["conflict"] is False

    def test_trend_reflects_shift(self):
        # The dominant emotion changes across the window → trend must
        # reflect instability (not a calm "stable").
        final_trend = _final(self.results)["trend"]
        assert final_trend in {"unstable", "declining"}

    def test_intermediate_step_present(self):
        # The neutral crossover phase must appear in the sequence.
        assert any(r["face"]["emotion"] == "neutral" for r in self.results)


# ======================================================================
# Cross-scenario coverage guarantees
# ======================================================================

class TestCoverage:
    """Guarantee the standardized scenario set exercises every required path."""

    def test_five_scenarios_defined(self):
        assert [s.name for s in SCENARIOS] == ["A", "B", "C", "D", "E"]

    def test_vision_exercised(self):
        # A, C are vision-only; B, D, E have face present.
        assert all(
            any(r["face"]["has_face"] for r in _run_scenario(s))
            for s in SCENARIOS
        )

    def test_voice_exercised_in_bde(self):
        for name in ("B", "D", "E"):
            s = get_scenario(name)
            results = _run_scenario(s)
            assert any(r["voice"] is not None for r in results), f"{name} missing voice"

    def test_conflict_path_exercised_in_d(self):
        s = get_scenario("D")
        results = _run_scenario(s)
        assert any(r["overall"]["conflict"] for r in results)

    def test_trend_analyzed_over_time(self):
        # E transitions across 10 steps — trend must be computed (non-None).
        s = get_scenario("E")
        results = _run_scenario(s)
        assert all(isinstance(r["trend"], str) and r["trend"]
                   for r in results)
