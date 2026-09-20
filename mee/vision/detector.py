"""TASK_MEE_004 Task 2: Face detector — wraps InsightFace SCRFD (buffalo_l).

Provides a minimal, dependency-safe interface:
    detector = FaceDetector(model_path=None)
    faces = detector.detect(frame_bgr)  -> list[Face]

- First call downloads buffalo_l weights to ~/.insightface/models/ (~280MB)
- Subsequent calls are instant (model cached in memory)
- If InsightFace is not installed, FaceDetector returns [] on detect()
  (caller should check available first)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# InsightFace 2.0 API — FaceAnalysis class
try:
    from insightface.app import FaceAnalysis as _IF  # type: ignore
    _IF_AVAILABLE = True
except Exception:  # noqa: S110
    _IF = None
    _IF_AVAILABLE = False


@dataclass
class Face:
    """A single detected face with bounding box and landmarks."""
    bbox: np.ndarray        # (4,) float64: x1, y1, x2, y2 in pixel coords
    det_score: float        # detection confidence 0..1
    landmarks: Optional[np.ndarray] = None  # (5, 2) float64 or None


class FaceDetector:
    """SCRFD face detector via InsightFace buffalo_l.

    Usage:
        if FaceDetector.is_available():
            det = FaceDetector()
            faces = det.detect(frame_bgr)
            for f in faces:
                print(f.bbox, f.det_score)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        det_size: tuple[int, int] = (640, 640),
    ):
        self.model_path = model_path or "buffalo_l"
        self.device = device
        self.det_size = det_size
        # Lazy-loaded
        self._detector: Optional[object] = None
        self._initialized = False

    @property
    def available(self) -> bool:
        """Return True if InsightFace is importable and detector can be loaded."""
        if self._initialized:
            return self._detector is not None
        return _IF_AVAILABLE

    def _ensure_loaded(self) -> None:
        """Load InsightFace models on first call."""
        if self._initialized:
            return
        self._initialized = True
        if _IF_AVAILABLE and self._detector is None:
            try:
                self._detector = _IF(name=self.model_path, allowed_modules=["detection"])
                self._detector.prepare(ctx_id=0, det_size=tuple(self.det_size))
            except Exception:
                self._detector = None

    @staticmethod
    def is_available() -> bool:
        """True if insightface is importable (weights may still need download)."""
        return _IF_AVAILABLE

    def detect(self, frame_bgr: np.ndarray) -> list[Face]:
        """Detect faces in a BGR numpy frame.

        Args:
            frame_bgr: (H, W, 3) uint8 array.

        Returns:
            List of Face objects, sorted by det_score descending.
            Empty list if no faces found or detector unavailable.
        """
        self._ensure_loaded()
        if self._detector is None:
            return []

        try:
            raw = self._detector.get(frame_bgr)
        except Exception:
            return []

        faces: list[Face] = []
        for f in raw:
            bbox = f.bbox.astype(np.float64) if f.bbox is not None else np.zeros(4)
            lm = f.landmark_2d_106 if hasattr(f, "landmark_2d_106") and f.landmark_2d_106 is not None else None
            # Fall back to 5-point landmarks if 106-point not available
            if lm is None and hasattr(f, "kps") and f.kps is not None:
                lm = f.kps.astype(np.float64)  # (5, 2)
            faces.append(Face(
                bbox=bbox,
                landmarks=lm,
                det_score=float(f.det_score) if f.det_score is not None else 0.0,
            ))

        # Sort by confidence descending
        faces.sort(key=lambda x: x.det_score, reverse=True)
        return faces

    def crop_face(
        self,
        frame_bgr: np.ndarray,
        face: Face,
        margin: float = 0.2,
    ) -> np.ndarray:
        """Crop the face region with padding.

        Args:
            frame_bgr: (H, W, 3) uint8 array.
            face: Face to crop.
            margin: Fractional margin on all sides (default 20%).

        Returns:
            Cropped face region as uint8 (H, W, 3) array.
        """
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = face.bbox.tolist()
        # Add margin
        mx = margin * (x2 - x1)
        my = margin * (y2 - y1)
        cx1 = max(0, int(x1 - mx))
        cy1 = max(0, int(y1 - my))
        cx2 = min(w, int(x2 + mx))
        cy2 = min(h, int(y2 + my))
        return frame_bgr[cy1:cy2, cx1:cx2].copy()
