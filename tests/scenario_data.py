"""TASK_MEE_009: Standardized end-to-end test scenarios.

Pure data module — no logic. Defines the five standardized scenarios
(Test A–E from the project plan §14) as importable dataclasses so both
the evaluation harness (``tools/evaluate_scenarios.py``) and the pytest
suite (``tests/test_scenarios.py``) consume identical input sequences.

Each scenario is a sequence of steps. A step specifies what the vision
channel and the voice channel report at that point in the sequence:

- ``face_emotion`` / ``face_confidence``: what ``_infer_vision()``
  returns (a face is present when ``face_emotion is not None``).
- ``voice_emotion`` / ``voice_confidence``: what ``_infer_voice()``
  returns (the voice channel is absent when ``voice_emotion is None``).

The engine under test is exercised through its full public path —
``EmotionEngine.process()`` — with ``_infer_vision``/``_infer_voice``
monkey-patched to emit these predetermined channel results. See
``docs/TEST_PROTOCOL.md`` for methodology and expected results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScenarioStep:
    """One step of a scenario: the channel outputs at this point.

    A step with ``face_emotion is None`` simulates "no face detected".
    A step with ``voice_emotion is None`` simulates "no voice channel".
    """

    face_emotion: Optional[str] = None
    face_confidence: float = 0.0
    voice_emotion: Optional[str] = None
    voice_confidence: float = 0.0


@dataclass
class Scenario:
    """A full end-to-end scenario: input sequence + expected outcomes."""

    name: str  # "A", "B", "C", "D", "E"
    label: str  # human-readable: "Neutral", "Happy", ...
    steps: List[ScenarioStep] = field(default_factory=list)
    expected_conflict: bool = False  # overall.conflict at the final step
    expected_emotion: str = "neutral"  # overall.emotion at the final step
    expected_trend: str = "stable"  # trend at the final step


def _repeat(face: Optional[str], fconf: float,
            voice: Optional[str], vconf: float, n: int) -> List[ScenarioStep]:
    """Build ``n`` identical steps (uniform scenarios)."""
    return [ScenarioStep(face, fconf, voice, vconf) for _ in range(n)]


# ----------------------------------------------------------------------
# Scenario A — Neutral (vision only)
# ----------------------------------------------------------------------
# 10 steps, face=neutral, no voice. Exercises the single-modality
# (vision-only) path through the full pipeline.
SCENARIO_A = Scenario(
    name="A",
    label="Neutral (vision-only)",
    steps=_repeat("neutral", 0.85, None, 0.0, 10),
    expected_conflict=False,
    expected_emotion="neutral",
    expected_trend="stable",
)

# ----------------------------------------------------------------------
# Scenario B — Happy (both modalities agree)
# ----------------------------------------------------------------------
# 10 steps, face=happy + voice=happy. Exercises the dual-channel
# agreement path.
SCENARIO_B = Scenario(
    name="B",
    label="Happy (both agree)",
    steps=_repeat("happy", 0.9, "happy", 0.85, 10),
    expected_conflict=False,
    expected_emotion="happy",
    expected_trend="stable",
)

# ----------------------------------------------------------------------
# Scenario C — Sad (vision only)
# ----------------------------------------------------------------------
# 10 steps, face=sad, no voice. Single-modality path, negative emotion.
SCENARIO_C = Scenario(
    name="C",
    label="Sad (vision-only)",
    steps=_repeat("sad", 0.8, None, 0.0, 10),
    expected_conflict=False,
    expected_emotion="sad",
    expected_trend="stable",
)

# ----------------------------------------------------------------------
# Scenario D — Frustrated (conflicting modalities)
# ----------------------------------------------------------------------
# Core conflict test: face reports happy, voice reports a different
# dominant emotion. Fusion must report conflict=True and let the
# higher-confidence label win.
#   Steps 0-4: face=happy (0.85) vs voice=angry (0.75)  → happy wins
#   Steps 5-9: face=happy (0.70) vs voice=sad  (0.65)  → happy wins
SCENARIO_D = Scenario(
    name="D",
    label="Frustrated (conflicting)",
    steps=(
        _repeat("happy", 0.85, "angry", 0.75, 5)
        + _repeat("happy", 0.70, "sad", 0.65, 5)
    ),
    expected_conflict=True,
    expected_emotion="happy",
    expected_trend="stable",
)

# ----------------------------------------------------------------------
# Scenario E — Cross-over (emotion shift over time)
# ----------------------------------------------------------------------
# Both modalities transition happy → neutral → sad. Exercises trend
# analysis: the dominant emotion changes within the window and
# confidence dips at the crossover, so the trend is no longer stable.
#   Steps 0-3: happy/happy (0.80 / 0.75)   → fused 0.775
#   Steps 4-6: neutral/neutral (0.40 / 0.40) → fused 0.40
#   Steps 7-9: sad/sad (0.80 / 0.75)        → fused 0.775
SCENARIO_E = Scenario(
    name="E",
    label="Cross-over (shift)",
    steps=(
        _repeat("happy", 0.8, "happy", 0.75, 4)
        + _repeat("neutral", 0.4, "neutral", 0.4, 3)
        + _repeat("sad", 0.8, "sad", 0.75, 3)
    ),
    expected_conflict=False,
    expected_emotion="sad",
    expected_trend="unstable",
)

# ----------------------------------------------------------------------
# Ordered list — the canonical scenario sequence (A, B, C, D, E).
# ----------------------------------------------------------------------
SCENARIOS: List[Scenario] = [
    SCENARIO_A,
    SCENARIO_B,
    SCENARIO_C,
    SCENARIO_D,
    SCENARIO_E,
]


def get_scenario(name: str) -> Scenario:
    """Look up a scenario by its one-letter name (case-insensitive)."""
    for s in SCENARIOS:
        if s.name.lower() == name.lower():
            return s
    raise KeyError(f"Unknown scenario {name!r}; expected one of "
                   f"{[s.name for s in SCENARIOS]}")
