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
import os
from dataclasses import dataclass, field
from typing import Optional

from ..fusion.emotion_fusion import EmotionFusion, EmotionFusionConfig
from ..state.history import EmotionHistory
from ..state.estimator import TrendConfig, analyze_trend


def _repo_root() -> str:
    """The repo root (parent of the ``mee/`` package).

    ``engine.py`` lives at ``<repo>/mee/api/engine.py`` — three dirs up.
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_model_root() -> Optional[str]:
    """Default models root: ``<repo>/models`` if it exists, else None."""
    env = os.environ.get("MEE_MODEL_ROOT")
    if env:
        return env
    cand = os.path.join(_repo_root(), "models")
    return cand if os.path.isdir(cand) else None


def _sub_model_dir(name: str) -> Optional[str]:
    """Resolve a canonical subfolder (e.g. ``voice``) under the models root,
    or None if the models root is unset/missing (so the backend falls back to
    its own default location)."""
    root = _default_model_root()
    if not root:
        return None
    cand = os.path.join(root, name)
    return cand if os.path.isdir(cand) else None


@dataclass
class MEEConfig:
    """V1 configuration — all defaults work without user input.

    2026-10-17: model weights default to the canonical ``<repo>/models/``
    tree (populated by ``tools/download_models.py``) instead of the scattered
    per-library home caches. Override with ``MEE_MODEL_ROOT`` or by passing an
    explicit ``vision_model_path`` / ``voice_model_path``.
    """
    fusion_weights: dict = field(default_factory=lambda: {"vision": 0.5, "voice": 0.5})
    conflict_threshold: float = 0.5
    trend_window: int = 30
    trend_min_samples: int = 5
    # Canonical models root — <repo>/models/ by default.
    model_root: Optional[str] = field(default_factory=_default_model_root)
    vision_model_path: Optional[str] = field(default_factory=lambda: (
        os.environ.get("MEE_VISION_MODEL_PATH") or _sub_model_dir("vision_emotion")
    ))
    face_confidence_threshold: float = 0.7
    detect_every_n_frames: Optional[int] = None  # TASK_MEE_013 Task 2: 1=every pass (default); n>1 reuses detection for n passes
    use_mediapipe: Optional[bool] = None  # TASK_MEE_016 Task C: None=auto (CUDA-driven); True=force MediaPipe CPU; False=force legacy chain
    voice_model_path: Optional[str] = field(default_factory=lambda: (
        os.environ.get("MEE_VOICE_MODEL_PATH") or _sub_model_dir("voice")
    ))
    # 2026-10-16: On this Jetson host, loading the SpeechBrain/torch voice
    # runtime in the same process as the MediaPipe vision runtime segfaults
    # (native C-runtime collision — verified: each works alone, combined load
    # dumps core). The browser remote demo is camera-only (no mic audio is
    # sent), so the voice path is not needed there. Set voice_enabled=False
    # (or env MEE_VOICE_ENABLED=0) to skip the voice runtime entirely and let
    # vision results flow. Default True preserves existing behaviour.
    voice_enabled: bool = field(default_factory=lambda: os.environ.get("MEE_VOICE_ENABLED", "1") != "0")
    audio_sample_rate: int = 16000
    output_format: str = "json"
    # TASK_MEE_CONTRACT_ENHANCEMENT_001 Gap A: opt-in conflict-reason exposure.
    # "off" (default) -> output identical to prior behaviour (no conflict_reason key).
    # "reason_only" -> when overall.conflict is True, overall.conflict_reason is
    # included (human-readable string from FusionResult.conflict_reason). New key;
    # never replaces/renames an existing key.
    detail_level: str = "off"


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
                    # TASK_MEE_016 Task C: thread backend-preference knob
                    use_mediapipe=self.config.use_mediapipe,
                )
            except Exception:
                self._vision_processor = None  # graceful degradation
                return None
        return self._vision_processor
    def _ensure_voice(self):
        """TASK_MEE_005: Lazy-load the voice processor (one-time cost).

        .. deprecated:: 2026-10-17
            Retained for backward compatibility / tests, but the engine now
            routes voice through :meth:`_ensure_voice_worker` (out-of-process)
            to avoid the native runtime collision on this Jetson host.
        """
        if not hasattr(self, '_voice_processor') or self._voice_processor is None:
            try:
                from ..voice.processor import VoiceProcessor
                self._voice_processor = VoiceProcessor()
            except Exception:
                self._voice_processor = None  # graceful degradation
        return self._voice_processor

    def _ensure_voice_worker(self):
        """2026-10-17: Lazy-spawn the out-of-process voice worker.

        Returns a ``VoiceWorkerClient`` (or None). The worker runs the
        SpeechBrain/torch voice runtime in its OWN process so it never shares
        an address space with the MediaPipe vision runtime (which segfaults
        this host). Importing the client here is safe — it does not import
        the voice runtime itself, only manages the subprocess.
        """
        if getattr(self, "_voice_worker", None) is None:
            try:
                from ..voice.voice_worker_client import VoiceWorkerClient
                self._voice_worker = VoiceWorkerClient(
                    cwd=os.environ.get("MEE_REPO_ROOT") or None,
                    # 2026-10-17: canonical models/voice tree (resolver layer).
                    model_path=self.config.voice_model_path,
                )
            except Exception:
                self._voice_worker = None
        return self._voice_worker

    def shutdown(self) -> None:
        """2026-10-17: Release the out-of-process voice worker if running."""
        worker = getattr(self, "_voice_worker", None)
        if worker is not None:
            try:
                worker.shutdown()
            except Exception:
                pass
            self._voice_worker = None

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
        # 2026-10-16: voice runtime disabled (see MEEConfig.voice_enabled) —
        # skip the SpeechBrain/torch load that collides with the MediaPipe
        # vision runtime and segfaults the process. Camera-only demos rely on
        # this so vision results still flow.
        if not getattr(self.config, "voice_enabled", True):
            return None
        if audio is None:
            return None
        # 2026-10-17: run voice in a SEPARATE worker process (see
        # mee/voice/voice_worker_client.py). The SpeechBrain/torch runtime
        # collides with the MediaPipe vision runtime if loaded in-process on
        # this Jetson host (segfault), so we isolate it across a process
        # boundary and only ship base64 audio / a result dict across it.
        client = self._ensure_voice_worker()
        if client is None or not client.available():
            scores = {label: 0.0 for label in ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]}
            return {"emotion": "neutral", "confidence": 0.0, "scores": scores}
        result = client.infer(audio, self.config.audio_sample_rate)
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
        overall = {
            "emotion": result.emotion,
            "confidence": result.confidence,
            "conflict": result.conflict,
        }
        # TASK_MEE_CONTRACT_ENHANCEMENT_001 Gap A: surface conflict_reason when opted in.
        # Additive: only present when detail_level == "reason_only" AND conflict is True.
        # Never present under the default detail_level ("off"), preserving the prior contract.
        if getattr(self.config, "detail_level", "off") == "reason_only" and result.conflict:
            overall["conflict_reason"] = result.conflict_reason
        return overall

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

    def health(self) -> dict:
        """TASK_MEE_CONTRACT_ENHANCEMENT_001 Gap B: real readiness signal.

        Pure read of internal model-load state. Does NOT call process(), the
        constructor, or any other method. Never raises — returns a dict with:
          status: "ready" | "degraded" | "unavailable"
          detail: human-readable explanation

        Status derivation:
          - ready       : both vision and voice processors loaded
          - degraded    : exactly one of {vision, voice} loaded
          - unavailable : neither loaded
        """
        vision_ok = self._vision_processor is not None
        voice_ok = self._voice_processor is not None

        if vision_ok and voice_ok:
            return {"status": "ready", "detail": "All models loaded (vision + voice)"}
        if vision_ok or voice_ok:
            return {
                "status": "degraded",
                "detail": (
                    f"Vision: {'OK' if vision_ok else 'missing'}, "
                    f"Voice: {'OK' if voice_ok else 'missing'}"
                ),
            }
        return {"status": "unavailable", "detail": "No models loaded"}


# Convenience import alias
EmotionEngine = EmotionEngine  # pylint: disable=invalid-name
