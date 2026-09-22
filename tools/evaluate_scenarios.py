#!/usr/bin/env python3
"""TASK_MEE_009: End-to-end evaluation harness.

Runnable script that executes the five standardized test scenarios
(Test A–E) against the real ``EmotionEngine.process()`` public path and
prints structured results: a markdown table plus a JSON dump.

How it works (per CTO plan Risk #1 — monkey-patch approach):
    ``_infer_vision`` / ``_infer_voice`` are patched per engine instance to
    return the predetermined channel results defined in
    ``tests/scenario_data.py``. ``process()`` then runs its full real
    code path (fusion → history append → trend → latency) against those
    results. This exercises the true pipeline glue without requiring live
    camera/mic hardware or model inference.

Usage:
    python tools/evaluate_scenarios.py            # run all scenarios
    python tools/evaluate_scenarios.py --json out.json  # also write JSON file

Exit code:
    0  if every scenario matches its expected outcome
    1  if any scenario deviates (see the per-scenario PASS/FAIL column)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make the repo root importable regardless of where the script is run from.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np  # noqa: E402

from mee.api.engine import EmotionEngine, MEEConfig, _MEEFaceResult  # noqa: E402
from tests.scenario_data import SCENARIOS, Scenario, ScenarioStep  # noqa: E402

# Trivial synthetic inputs — patched _infer_* methods ignore their args and
# return predetermined results; the arrays only satisfy the process() contract.
_SYNTH_FRAME = np.zeros((10, 10, 3), dtype=np.uint8)
_SYNTH_AUDIO = np.zeros(640, dtype=np.float32)


def _face_result(step: ScenarioStep) -> _MEEFaceResult:
    if step.face_emotion is None:
        return _MEEFaceResult()
    return _MEEFaceResult(
        emotion=step.face_emotion,
        confidence=step.face_confidence,
        scores={step.face_emotion: step.face_confidence},
        has_face=True,
    )


def _voice_result(step: ScenarioStep) -> dict | None:
    if step.voice_emotion is None:
        return None
    return {
        "emotion": step.voice_emotion,
        "confidence": step.voice_confidence,
        "scores": {step.voice_emotion: step.voice_confidence},
    }


def _run_scenario(scenario: Scenario) -> list[dict]:
    """Run every step of the scenario through the real process() path."""
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
        return _voice_result(steps[state["i"] - 1])

    engine._infer_vision = _vision
    engine._infer_voice = _voice

    results = []
    for _ in steps:
        results.append(engine.process(video_frame=_SYNTH_FRAME, audio=_SYNTH_AUDIO))
    return results


def _summarize(scenario: Scenario, results: list[dict]) -> dict:
    """Collapse a scenario's step results into a flat summary record."""
    final = results[-1]
    avg_latency = round(sum(r["latency_ms"] for r in results) / len(results), 3)
    final_overall = final["overall"]

    emotion_ok = final_overall["emotion"] == scenario.expected_emotion
    conflict_ok = final_overall["conflict"] is scenario.expected_conflict
    trend_ok = final["trend"] == scenario.expected_trend

    return {
        "name": scenario.name,
        "label": scenario.label,
        "steps": len(results),
        "emotion": final_overall["emotion"],
        "confidence": round(final_overall["confidence"], 4),
        "conflict": final_overall["conflict"],
        "trend": final["trend"],
        "avg_latency_ms": avg_latency,
        "max_latency_ms": round(max(r["latency_ms"] for r in results), 3),
        "expected": {
            "emotion": scenario.expected_emotion,
            "conflict": scenario.expected_conflict,
            "trend": scenario.expected_trend,
        },
        "checks": {
            "emotion": emotion_ok,
            "conflict": conflict_ok,
            "trend": trend_ok,
        },
        "pass": emotion_ok and conflict_ok and trend_ok,
    }


def _print_markdown_table(summaries: list[dict]) -> None:
    print("\n# TASK_MEE_009 — End-to-End Scenario Results\n")
    print("| Scenario | Label | Emotion | Confidence | Conflict | Trend | Avg Latency (ms) | Max Latency (ms) | Result |")
    print("|----------|-------|---------|------------|----------|-------|------------------|------------------|--------|")
    for s in summaries:
        status = "✅ PASS" if s["pass"] else "❌ FAIL"
        print(
            f"| {s['name']} | {s['label']} | {s['emotion']} | {s['confidence']:.3f} "
            f"| {s['conflict']} | {s['trend']} | {s['avg_latency_ms']:.3f} "
            f"| {s['max_latency_ms']:.3f} | {status} |"
        )
    print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="MEE end-to-end scenario harness")
    parser.add_argument("--json", dest="json_path", default=None,
                        help="optional path to also write the full JSON dump")
    args = parser.parse_args()

    summaries = []
    full = []
    for scenario in SCENARIOS:
        results = _run_scenario(scenario)
        summary = _summarize(scenario, results)
        summaries.append(summary)
        full.append({"scenario": summary, "steps": results})

    _print_markdown_table(summaries)

    dump = {
        "task": "TASK_MEE_009",
        "scenarios": summaries,
        "details": full,
        "overall_pass": all(s["pass"] for s in summaries),
    }
    json_text = json.dumps(dump, indent=2)

    if args.json_path:
        with open(args.json_path, "w") as f:
            f.write(json_text + "\n")
        print(f"Wrote JSON dump → {args.json_path}\n")
    else:
        print("## JSON dump\n")
        print("```json")
        print(json_text)
        print("```\n")

    passed = sum(1 for s in summaries if s["pass"])
    print(f"Overall: {passed}/{len(summaries)} scenarios PASS — "
          f"{'ALL PASS ✅' if all(s['pass'] for s in summaries) else 'SOME FAILED ❌'}")
    return 0 if all(s["pass"] for s in summaries) else 1


if __name__ == "__main__":
    sys.exit(main())
