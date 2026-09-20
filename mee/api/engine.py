"""★ PRIMARY PUBLIC API — the ONLY interface consumers use.

EmotionEngine.process(video_frame, audio) -> JSON-serializable dict with
face/voice/overall/trend/conflict keys as specified in docs/ARCHITECTURE.md.

TASK_MEE_004: Vision path wired to mee.vision.processor (InsightFace/SCRFD +
emotion head). Voice path remains stubbed (TASK_MEE_003).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MEEConfig:
    """V1 configuration — all defaults work without user input."""
    fusion_weights: dict = field(default_factory=lambda: {"vision": 0.5, "voice": 0.5})
    conflict_threshold: float = 0.5
    trend_window: int = 30
    trend_min_samples: int = 5
    vision_model_path: Optional[str] = None
    face_confidence_threshold: float = 0.7
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
        self._model_ready = False  # Stub: no backend installed yet

    def _ensure_vision(self):
        """TASK_MEE_004: Lazy-load the vision processor (one-time cost)."""
        if self._vision_processor is None:
            try:
                from ..vision.processor import VisionProcessor
                self._vision_processor = VisionProcessor(
                    model_path=self.config.vision_model_path,
                    confidence_threshold=self.config.face_confidence_threshold,
                )
            except Exception:
                self._vision_processor = None  # graceful degradation
                return None
        return self._vision_processor

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

        # ---- Vision path (stub) ----
        face_result = self._infer_vision(video_frame)

        # ---- Voice path (stub) ----
        voice_result = self._infer_voice(audio)

        # ---- Fusion (stub: equal-weight vote when both available) ----
        overall = self._fuse(face_result, voice_result)

        # ---- Trend (stub: always "unknown" until history populated) ----
        trend = self._compute_trend(overall["emotion"])

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
        if not self._model_ready or audio is None:
            return None
        # Placeholder — will be replaced in TASK_MEE_003
        return {"emotion": "neutral", "confidence": 0.0, "scores": {}}

    def _fuse(self, face: _MEEFaceResult, voice: dict | None) -> dict:
        """TASK_MEE_004: Fusion — vision now available, voice still stubbed."""
        if face.has_face and voice:
            # Both present — take higher-confidence prediction
            if face.confidence >= voice["confidence"]:
                return {"emotion": face.emotion or "neutral", "confidence": face.confidence, "conflict": False}
            else:
                conflict = (face.emotion != voice["emotion"]) and face.confidence > self.config.conflict_threshold and voice["confidence"] > self.config.conflict_threshold
                return {
                    "emotion": voice["emotion"],
                    "confidence": voice["confidence"],
                    "conflict": conflict,
                }
        elif face.has_face:
            return {"emotion": face.emotion or "neutral", "confidence": face.confidence, "conflict": False}
        elif voice:
            return {"emotion": voice["emotion"], "confidence": voice["confidence"], "conflict": False}
        else:
            raise ValueError("Both modalities are None — must supply at least one input")

    def _compute_trend(self, emotion: str) -> str:
        # Stub: history not yet populated in G2 phase
        return "unknown"

    @property
    def is_ready(self) -> bool:
        return self._model_ready


# Convenience import alias
EmotionEngine = EmotionEngine  # pylint: disable=invalid-name
