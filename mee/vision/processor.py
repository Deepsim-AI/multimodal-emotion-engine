"""TASK_MEE_004 Task 4 (rewired for TASK_MEE_011 three-stage pipeline):
Vision processor — orchestrates detection + alignment + emotion per frame.

Pipeline (commercially-safe, see docs/THIRD_PARTY_LICENSES.md):
  1. FaceDetector.detect(frame)  → list[Face]            (Stage 1, MIT/OpenCV)
  2. FaceAligner.align(frame,f)  → aligned RGB crop       (Stage 2, Apache-2.0)
  3. EmotionModel.predict(crop)  → emotion scores          (Stage 3, Apache-2.0)

Public entry point:
  process(frame) → VisionResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .detector import FaceDetector, Face
from .alignment import FaceAligner
from .emotion_model import EmotionModel


@dataclass
class FaceEmotion:
    """Emotion prediction for a single detected face."""
    label: str = "neutral"
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)
    bbox: tuple = (0.0, 0.0, 0.0, 0.0)  # (x, y, w, h)


@dataclass
class VisionResult:
    """Result of processing one video frame.

    Fields used by EmotionEngine._infer_vision:
      has_face, emotion, confidence, scores

    Additional fields for richer reporting:
      face_count, faces, best_emotion, best_confidence, channel_scores
    """
    has_face: bool = False
    emotion: str = ""
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)
    face_count: int = 0
    faces: list = field(default_factory=list)
    best_emotion: str = ""
    best_confidence: float = 0.0
    channel_scores: dict = field(default_factory=dict)


class VisionProcessor:
    """Combines FaceDetector + FaceAligner + EmotionModel into one call/frame.

    Usage:
        vp = VisionProcessor()
        result = vp.process(frame_bgr)
        if result.has_face:
            print(result.best_emotion, result.best_confidence)
    """

    def __init__(self,
                 detector: Optional[FaceDetector] = None,
                 aligner: Optional[FaceAligner] = None,
                 emotion_model: Optional[EmotionModel] = None,
                 model_path: Optional[str] = None,
                 confidence_threshold: float = 0.5,
                 aligner_size: int = 224,
                 detect_every_n_frames: int = 1,  # TASK_MEE_013 Task 1
                 use_mediapipe: Optional[bool] = None):  # TASK_MEE_016 Task C
        """
        Args:
            detector: inject for tests; default FaceDetector().
            aligner: inject for tests; default FaceAligner() if available.
            emotion_model: inject for tests; default EmotionModel().
            model_path: forwarded to EmotionModel (optional explicit path).
            confidence_threshold: forwarded to FaceDetector.
            aligner_size: crop size for Stage 2 (default 224).
            detect_every_n_frames: TASK_MEE_013 Task 1 — run Stage-1 face
                detection once every N process() calls instead of every call.
                1 (default) preserves the original behavior exactly. Values
                < 1 raise ValueError. The cached detection result is reused
                for alignment + emotion until invalidated by a changed frame
                (different array object or shape) or force_detection=True.
                Not thread-safe: one VisionProcessor per thread.
            use_mediapipe: TASK_MEE_016 Task C — forwarded to FaceDetector
                when the default detector is constructed. ``None`` (default)
                lets FaceDetector auto-select based on CUDA availability;
                ``True`` forces the MediaPipe CPU backend; ``False`` forces
                the legacy retina-face → dlib → OpenCV HOG chain.
        """
        # TASK_MEE_013 Task 1: validate detection-frequency knob
        if detect_every_n_frames < 1:
            raise ValueError(
                "detect_every_n_frames must be >= 1, got "
                f"{detect_every_n_frames!r}"
            )
        self._detector = detector or FaceDetector(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            use_mediapipe=use_mediapipe,  # TASK_MEE_016 Task C
        )
        self._aligner = aligner  # may be None (degrade to direct crop)
        self._emotion = emotion_model or EmotionModel(model_path=model_path)
        # TASK_MEE_013 Task 1: detection-frequency state (G4 revision R1)
        self._detect_every_n_frames = int(detect_every_n_frames)
        self._last_faces: Optional[list[Face]] = None  # None=uninitialized; []="no face" (R3)
        self._last_frame_id: int | None = None         # id(frame_bgr) at detection time
        self._last_frame_shape: tuple[int, ...] | None = None  # frame.shape before flattening
        self._call_counter: int = 0                    # mod-n counter

    def process(self, frame_bgr: np.ndarray, force_detection: bool = False) -> VisionResult:
        """Process one BGR frame.

        Args:
            frame_bgr: (H, W, 3) uint8 BGR array.
            force_detection: TASK_MEE_013 Task 1 — bypass the detection
                cache and re-run Stage 1 even when n > 1.

        Returns:
            VisionResult — always returns (never raises on no-face).
        """
        # TASK_MEE_013 Task 1: detection-frequency gate
        # n == 1: fast path — identical to the pre-change code path, no cache consulted.
        if self._detect_every_n_frames <= 1:
            return self._run_once(frame_bgr)

        self._call_counter += 1
        due = (self._call_counter % self._detect_every_n_frames) == 1
        if not force_detection and self._last_faces is not None and not due:
            fid = id(frame_bgr)
            shape = tuple(frame_bgr.shape)  # type: ignore[union-attr]
            if fid == self._last_frame_id and shape == self._last_frame_shape:
                return self._build_result(frame_bgr, self._last_faces)

        faces = self._detector.detect(frame_bgr)
        self._last_faces = faces if faces else []  # TASK_MEE_013 Task 1: cache [] for no-face (G4 R3)
        self._last_frame_id = id(frame_bgr)
        self._last_frame_shape = tuple(frame_bgr.shape)  # type: ignore[union-attr]
        return self._build_result(frame_bgr, faces)

    def _run_once(self, frame_bgr: np.ndarray) -> VisionResult:
        """TASK_MEE_013 Task 1: single detect→align→emit cycle (n == 1 path)."""
        faces = self._detector.detect(frame_bgr)

        if not faces:
            return VisionResult(
                has_face=False,
                emotion="",
                confidence=0.0,
                scores={},
                face_count=0,
                faces=[],
                best_emotion="",
                best_confidence=0.0,
                channel_scores={},
            )

        face_results: list[FaceEmotion] = []
        for face in faces:
            # Stage 2: align (preferred) or fall back to a direct crop.
            crop = None
            if self._aligner is not None and self._aligner.available:
                try:
                    crop = self._aligner.align(frame_bgr, face)
                except Exception:  # noqa: S110
                    crop = None
            if crop is None:
                crop = self._detector.crop_face(frame_bgr, face)

            pred = self._emotion.predict(frame_bgr, face_crop=crop)
            x1, y1, x2, y2 = (float(v) for v in np.asarray(face.bbox).reshape(4))
            face_results.append(FaceEmotion(
                label=pred["emotion"],
                confidence=pred["confidence"],
                scores=pred["scores"],
                bbox=(x1, y1, x2 - x1, y2 - y1),
            ))

        # Best face = highest confidence
        best = max(face_results, key=lambda f: f.confidence)

        return VisionResult(
            has_face=True,
            emotion=best.label,
            confidence=best.confidence,
            scores=best.scores,
            face_count=len(face_results),
            faces=face_results,
            best_emotion=best.label,
            best_confidence=best.confidence,
            channel_scores={"vision": best.scores},
        )

    # TASK_MEE_013 Task 1: shared helper — build a VisionResult from a detection result
    def _build_result(self, frame_bgr: np.ndarray, faces: list[Face]) -> VisionResult:
        """TASK_MEE_013 Task 1: align + predict for `faces`, returning a VisionResult.

        Works for fresh or cached detection results; downstream stages
        (alignment, emotion) are fed exactly as with a fresh detection.
        """
        if not faces:
            return VisionResult(
                has_face=False,
                emotion="",
                confidence=0.0,
                scores={},
                face_count=0,
                faces=[],
                best_emotion="",
                best_confidence=0.0,
                channel_scores={},
            )

        face_results: list[FaceEmotion] = []
        for face in faces:
            # Stage 2: align (preferred) or fall back to a direct crop.
            crop = None
            if self._aligner is not None and self._aligner.available:
                try:
                    crop = self._aligner.align(frame_bgr, face)
                except Exception:  # noqa: S110
                    crop = None
            if crop is None:
                crop = self._detector.crop_face(frame_bgr, face)

            pred = self._emotion.predict(frame_bgr, face_crop=crop)
            x1, y1, x2, y2 = (float(v) for v in np.asarray(face.bbox).reshape(4))
            face_results.append(FaceEmotion(
                label=pred["emotion"],
                confidence=pred["confidence"],
                scores=pred["scores"],
                bbox=(x1, y1, x2 - x1, y2 - y1),
            ))

        # Best face = highest confidence
        best = max(face_results, key=lambda f: f.confidence)

        return VisionResult(
            has_face=True,
            emotion=best.label,
            confidence=best.confidence,
            scores=best.scores,
            face_count=len(face_results),
            faces=face_results,
            best_emotion=best.label,
            best_confidence=best.confidence,
            channel_scores={"vision": best.scores},
        )

    def process_frame(self, frame_bgr: np.ndarray) -> VisionResult:
        """Alias for process() — used by EmotionEngine._infer_vision."""
        return self.process(frame_bgr)
