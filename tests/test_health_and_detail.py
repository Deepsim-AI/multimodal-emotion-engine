# TASK_MEE_CONTRACT_ENHANCEMENT_001 — G2 implementation tests
"""
Tests for the two additive MEE contract enhancements:

  Gap A — MEEConfig.detail_level: "off" | "reason_only"
          When "reason_only" and overall.conflict is True, the output
          includes overall.conflict_reason (str). Under default "off",
          the key is absent (backward compatible).

  Gap B — EmotionEngine.health()
          Real readiness signal based on internal model-load state.
          Never calls process(). Returns:
            {"status": "ready"|"degraded"|"unavailable", "detail": str}

Note on env constraints:
  This test file exercises only the engine's _fuse() path and health()
  — it does NOT call engine.process() with real audio/frames, because
  the voice path imports the transformers/torch chain that has a
  documented segfault under pytest in this env (see MEE_ASSESSMENT.md
  Phase 0: "MEE run incomplete in Phase 0 (env/ABI limitation)").
  The fusion logic it drives is the same path used in production _fuse().
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is importable when running via `python -m pytest` from this dir.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from unittest import mock

from mee.api.engine import MEEConfig, EmotionEngine, _MEEFaceResult
from mee.fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _canonical_conflict_inputs():
    """Vision says 'happy' (high confidence); voice says 'angry' (high confidence).
    This is the canonical conflict case in the fusion implementation
    (see mee/fusion/emotion_fusion.py:215-303). Returns (vision, voice).
    """
    vision = {"emotion": "happy", "confidence": 0.95,
              "scores": {"happy": 0.95, "neutral": 0.05}}
    voice  = {"emotion": "angry", "confidence": 0.95,
              "scores": {"angry": 0.95, "neutral": 0.05}}
    return vision, voice


def _face_from(vision):
    return _MEEFaceResult(
        emotion=vision["emotion"],
        confidence=vision["confidence"],
        scores=vision["scores"],
        has_face=True,
    )


# ------------------------------------------------------------------ #
#  AC-1 — MEEConfig gains an additive detail_level field (default 'off')
# ------------------------------------------------------------------ #

def test_detail_level_default_is_off():
    """AC-1: MEEConfig gains an additive field detail_level with default 'off'."""
    cfg = MEEConfig()
    assert cfg.detail_level == "off"


# ------------------------------------------------------------------ #
#  Gap A — conflict_reason exposure via detail_level                   #
# ------------------------------------------------------------------ #

def test_conflict_reason_present_when_configured():
    """AC-2: with detail_level='reason_only' AND conflict=True,
    overall.conflict_reason is present (str)."""
    vision, voice = _canonical_conflict_inputs()

    # First verify the fusion layer actually reports a conflict for this input,
    # so the assertion below is not vacuous.
    fusion = EmotionFusion(config=EmotionFusionConfig(vision_weight=0.5, voice_weight=0.5))
    fused = fusion.compute_fusion(vision=vision, voice=voice)
    assert fused.conflict is True, "expected a conflict for happy vs angry"
    assert fused.conflict_reason, "expected non-empty conflict_reason from fusion"

    # Now exercise the engine's _fuse() with this same input under detail_level
    # "reason_only" and confirm conflict_reason is surfaced on the overall dict.
    engine = EmotionEngine(config=MEEConfig(detail_level="reason_only"))
    face = _face_from(vision)
    overall = engine._fuse(face, voice)
    assert overall["conflict"] is True
    assert "conflict_reason" in overall, (
        "engine._fuse must surface conflict_reason when detail_level='reason_only' and conflict=True"
    )
    assert isinstance(overall["conflict_reason"], str)
    assert overall["conflict_reason"] == fused.conflict_reason


def test_no_conflict_reason_by_default():
    """AC-3: default config (detail_level='off') — overall dict must NOT
    include 'conflict_reason' even when conflict=True."""
    vision, voice = _canonical_conflict_inputs()
    engine = EmotionEngine(config=MEEConfig())  # default: detail_level="off"
    assert engine.config.detail_level == "off"
    face = _face_from(vision)
    overall = engine._fuse(face, voice)
    assert overall["conflict"] is True
    # AC-3: key absent under default (backward compat)
    assert "conflict_reason" not in overall, (
        "detail_level='off' must NOT include conflict_reason (backward compat)"
    )


# ------------------------------------------------------------------ #
#  Gap B — health() method                                            #
# ------------------------------------------------------------------ #

def test_health_unavailable_when_no_models():
    """AC-4: engine.health() returns 'unavailable' when no models are loaded.
    Must NOT call process()."""
    engine = EmotionEngine(config=MEEConfig())
    assert engine._vision_processor is None
    assert engine._voice_processor is None
    h = engine.health()
    assert h["status"] == "unavailable", h
    assert isinstance(h["detail"], str) and h["detail"]


def test_health_ready_when_both_loaded():
    """AC-4: engine.health() returns 'ready' when both vision and voice are loaded."""
    engine = EmotionEngine(config=MEEConfig())
    engine._vision_processor = object()
    engine._voice_processor = object()
    h = engine.health()
    assert h["status"] == "ready", h
    assert isinstance(h["detail"], str) and h["detail"]


def test_health_degraded_when_one_loaded():
    """AC-4: engine.health() returns 'degraded' when exactly one model is loaded."""
    engine = EmotionEngine(config=MEEConfig())
    engine._vision_processor = object()   # vision OK
    engine._voice_processor = None        # voice missing
    h = engine.health()
    assert h["status"] == "degraded", h
    assert "Vision" in h["detail"] and "Voice" in h["detail"]
    assert "OK" in h["detail"] and "missing" in h["detail"]


def test_health_does_not_call_process():
    """AC-4: health() must NOT call process(). Verified by patching process
    to raise if invoked, then calling health() — must succeed cleanly."""
    engine = EmotionEngine(config=MEEConfig())
    with mock.patch.object(EmotionEngine, "process",
                           side_effect=AssertionError("health() must not call process()")):
        h = engine.health()
    assert "status" in h and "detail" in h


# ------------------------------------------------------------------ #
#  Regression guard — existing keys/defaults unchanged                 #
# ------------------------------------------------------------------ #

def test_existing_overall_keys_unchanged_by_default():
    """AC-5/AC-6: under default config, overall dict has exactly the prior
    keys: emotion, confidence, conflict (no new keys added)."""
    engine = EmotionEngine(config=MEEConfig())
    face = _MEEFaceResult(emotion="happy", confidence=0.8,
                          scores={"happy": 0.8}, has_face=True)
    overall = engine._fuse(face, voice=None)
    assert set(overall.keys()) == {"emotion", "confidence", "conflict"}, (
        f"overall keys under default config must be exactly "
        f"{{emotion, confidence, conflict}}; got {set(overall.keys())}"
    )
