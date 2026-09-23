"""★ PRIMARY PUBLIC API — the ONLY interface consumers use.

EmotionEngine.process(video_frame, audio) -> JSON-serializable dict with
face/voice/overall/trend/conflict keys as specified in docs/ARCHITECTURE.md.

TASK_MEE_004: Vision path wired. TASK_MEE_005: Voice path wired with SpeechBrain RavNet.
Voice path degrades gracefully when speechbrain unavailable.
TASK_MEE_006 Subtask 4: real weighted fusion (EmotionFusion) + trend analysis
(analyze_trend over EmotionHistory) wired into process(); public return
contract (face, voice, overall, trend, latency_ms) unchanged.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from ..fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig
from ..state.history import EmotionHistory
from ..state.estimator import TrendConfig, analyze_trend


@dataclass
class MEEConfig:
    """V1 configuration — all defaults work without user input."""
    fusion_weights: dict = field(default_factory=lambda: {"vision": 0.5, "voice": 0.5})
    conflict_threshold: float = 0.5
    trend_window: int = 30
    trend_min_samples: int = 5
    vision_model_path: Optional[str] = None
    face_confidence_threshold: float = 0.7
    detect_every_n_frames: Optional[int] = None  # TASK_MEE_013 Task 2: 1=every pass (default); n>1 reuses detection for n passes
    voice_model_path: Optional[str] = None
    audio_sample_rate: int = 16000
    output_format: str = "json"


@dataclass
class _MEEFaceResult:
    emotion: Optional[str] = None
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)
    has_face: bool = False

    def to_dict(self) -> dict | None:
        if not self.has_face:
            return {
                "emotion": None,
                "confidence": 0.0,
                "scores": {},
                "has_face": False,
            }
        return {
            "emotion": self.emotion,
            "confidence": self.confidence,
            "scores": self.scores,
            "has_face": True,
        }


class EmotionEngine:
    """Stable public API for MEE V1.

    Usage:
        engine = EmotionEngine()
        result = engine.process(video_frame=frame, audio=audio)
        # result is a dict with keys: face, voice, overall, trend, latency_ms
    """

    def __init__(self, config: Optional[MEEConfig] = None):
        self.config = config or MEEConfig()
        self._initialized = False
        self._vision_processor = None  # TASK_MEE_004: lazy-loaded VisionProcessor
        self._voice_processor = None   # TASK_MEE_005: lazy-loaded VoiceProcessor
        self._model_ready = False  # Stub: no backend installed yet
        # TASK_MEE_006 Subtask 4: fusion + temporal state wiring.
        # One EmotionFusion instance per engine — it owns the EmotionHistory
        # buffer (shipped EmotionFusion always creates/uses its OWN internal
        # buffer; passing one in via the `history=` kwarg is accepted but
        # ignored at runtime — verified 2026-09-21). The engine therefore
        # reads trend samples back from `self._fusion.history`.
        weights = getattr(self.config, "fusion_weights", None) or {"vision": 0.5, "voice": 0.5}
        self._fusion_config = EmotionFusionConfig(
            vision_weight=float(weights.get("vision", 0.5)),
            voice_weight=float(weights.get("voice", 0.5)),
            conflict_threshold=float(self.config.conflict_threshold),
            history_window=int(self.config.trend_window),
        )
        self._fusion = EmotionFusion(config=self._fusion_config)
        self._trend_config = TrendConfig(
            window=int(self.config.trend_window),
            conf_threshold=float(self.config.conflict_threshold),
        )

    def _ensure_vision(self):
        """TASK_MEE_004: Lazy-load the vision processor (one-time cost)."""
        if self._vision_processor is None:
            try:
                from ..vision.processor import VisionProcessor
                self._vision_processor = VisionProcessor(
                    model_path=self.config.vision_model_path,
                    confidence_threshold=self.config.face_confidence_threshold,
                    # TASK_MEE_013 Task 2: thread detection-frequency knob (G4 R2)
                    detect_every_n_frames=self.config.detect_every_n_frames or 1,
                )
            except Exception:
                self._vision_processor = None  # graceful degradation
                return None
        return self._vision_processor
    def _ensure_voice(self):
        """TASK_MEE_005: Lazy-load the voice processor (one-time cost)."""
        if not hasattr(self, '_voice_processor') or self._voice_processor is None:
            try:
                from ..voice.processor import VoiceProcessor
                self._voice_processor = VoiceProcessor()
            except Exception:
                self._voice_processor = None  # graceful degradation
        return self._voice_processor

    def process(
        self,
        video_frame=None,
        audio=None,
    ) -> dict:
        """Process one frame and one audio chunk; return MEE result dict.

        Args:
            video_frame: BGR numpy array (H×W×3 uint8) or None.
            audio: 1-D float32 numpy array at 16kHz or None.

        Returns:
            JSON-serializable dict with keys: face, voice, overall, trend, latency_ms.
        """
        t0 = time.perf_counter()

        # ---- Vision path ----
        face_result = self._infer_vision(video_frame)

        # ---- Voice path ----
        voice_result = self._infer_voice(audio)

        # ---- Fusion (TASK_MEE_006: real weighted fusion via EmotionFusion) ----
        overall = self._fuse(face_result, voice_result)

        # ---- Trend (TASK_MEE_006: analyze_trend over accumulated history) ----
        trend = self._compute_trend()

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "face": face_result.to_dict(),
            "voice": voice_result if voice_result else None,
            "overall": overall,
            "trend": trend,
            "latency_ms": latency_ms,
        }

    # ---- Internal stubs (G3+ replace with real inference) ----

    def _infer_vision(self, frame=None) -> _MEEFaceResult:
        """TASK_MEE_004: Real vision inference via VisionProcessor."""
        if frame is None:
            return _MEEFaceResult()
        vp = self._ensure_vision()
        if vp is None:
            return _MEEFaceResult()  # graceful: no face, not an error
        result = vp.process_frame(frame)
        return _MEEFaceResult(
            emotion=result.emotion,
            confidence=result.confidence,
            scores=result.scores,
            has_face=result.has_face,
        )

    def _infer_voice(self, audio=None) -> dict | None:
        """TASK_MEE_005: Real voice inference via VoiceProcessor."""
        if audio is None:
            return None
        vp = self._ensure_voice()
        if vp is None:
            # Graceful degradation — no voice model available
            scores = {label: 0.0 for label in ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]}
            return {"emotion": "neutral", "confidence": 0.0, "scores": scores}
        result = vp.process(audio, self.config.audio_sample_rate)
        return {
            "emotion": result.get("emotion", "neutral"),
            "confidence": result.get("confidence", 0.0),
            "scores": result.get("scores", {}),
        }

    def _fuse(self, face: _MEEFaceResult, voice: dict | None) -> dict:
        """TASK_MEE_006 Subtask 4: weighted multimodal fusion via EmotionFusion.

        Delegates to ``self._fusion.compute_fusion(vision, voice)`` — the
        shipped instance-based API (the wiring plan's static
        ``EmotionFusion.compute_fusion(face, voice, config)`` signature does
        not exist on the implemented class). Returns the MEE overall dict:
        ``{emotion, confidence, conflict}``. Missing/degraded channels are
        handled inside fusion (deterministic neutral fallback, never raises),
        so the previous ValueError on double-None is intentionally retired —
        no test in this repo asserts the old exception behaviour.
        """
        vision = face.to_dict() if face.has_face else None
        result = self._fusion.compute_fusion(vision=vision, voice=voice)
        return {
            "emotion": result.emotion,
            "confidence": result.confidence,
            "conflict": result.conflict,
        }

    def _compute_trend(self) -> str:
        """TASK_MEE_006 Subtask 4: trend from accumulated emotion history.

        The fusion component records each step into its internal
        ``EmotionHistory`` (see ``__init__``); this reads that buffer and
        classifies the trajectory via the shipped
        ``mee.state.estimator.analyze_trend`` (the wiring plan's
        ``EmotionHistory.analyze_trend`` method does not exist).
        """
        result = analyze_trend(self._fusion.history, self._trend_config)
        return result.trend

    @property
    def is_ready(self) -> bool:
        return self._model_ready


# Convenience import alias
EmotionEngine = EmotionEngine  # pylint: disable=invalid-name
