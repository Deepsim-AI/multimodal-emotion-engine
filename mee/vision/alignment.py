"""TASK_MEE_011: Stage 2 — Face Alignment / Cropping.

Uses face_alignment (Apache-2.0) to refine bounding boxes with 68-point
landmarks and produce a canonical aligned crop sized for the expression model
(EmotiEffLib: 224x224 for enet_b0 models).

This module enforces the three-stage separation:
  Stage 1 — Detection   (detector.py,  MIT / OpenCV)
  Stage 2 — Alignment   (this file,   Apache-2.0)
  Stage 3 — Expression  (emotion_model.py, Apache-2.0)

No face identification / biometric features are extracted or stored.

⚠️  face_alignment downloads a small landmark model (~5MB) on first use —
    same pattern as other runtime model downloads in this project.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

try:
    import face_alignment as fa  # type: ignore
    _FA_AVAILABLE = True
except Exception:  # noqa: S110
    fa = None  # type: ignore
    _FA_AVAILABLE = False

from .detector import Face  # noqa: E402


def _to_fa_landmarks_type():
    """Resolve the correct LandmarksType enum member (version-tolerant)."""
    lt = fa.LandmarksType
    for name in ("TWO_D", "two_d", "_2D"):
        if hasattr(lt, name):
            return getattr(lt, name)
    # Fallback: first member (TWO_D)
    return list(lt)[0]


class FaceAligner:
    """Align and crop a detected face using 68-point landmarks.

    Usage:
        aligner = FaceAligner()
        if aligner.is_available():
            aligned = aligner.align(frame_bgr, face)  # (224, 224, 3) uint8 RGB
    """

    def __init__(self, device: str = "cpu", size: int = 224):
        """
        Args:
            device: 'cpu' or 'cuda' (pass-through to face_alignment).
            size: output square crop size in pixels (224 for enet_b0 models).
        """
        self._device = device
        self._size = int(size)
        self._aligner = None

    # -- availability ------------------------------------------------------
    @property
    def available(self) -> bool:
        return _FA_AVAILABLE

    @staticmethod
    def is_available() -> bool:
        return _FA_AVAILABLE

    def _ensure_loaded(self) -> bool:
        if not _FA_AVAILABLE:
            return False
        if self._aligner is None:
            try:
                self._aligner = fa.FaceAlignment(
                    _to_fa_landmarks_type(),
                    device=self._device,
                    flip_input=False,
                )
            except Exception:  # noqa: S110
                self._aligner = None
        return self._aligner is not None

    # -- public API --------------------------------------------------------
    def align(self, frame_bgr: np.ndarray, face: "Face") -> Optional[np.ndarray]:
        """Return an aligned square RGB crop of the given face.

        Args:
            frame_bgr: (H, W, 3) uint8 BGR frame.
            face: Stage-1 :class:`Face` (bbox + optional landmarks).

        Returns:
            (size, size, 3) uint8 RGB array, or None if alignment fails.
        """
        if frame_bgr is None or not isinstance(frame_bgr, np.ndarray):
            return None
        if not self._ensure_loaded():
            return None

        try:
            h, w = frame_bgr.shape[:2]
            x1 = max(0, int(face.bbox[0]))
            y1 = max(0, int(face.bbox[1]))
            x2 = min(w, int(face.bbox[2]))
            y2 = min(h, int(face.bbox[3]))
            if x2 - x1 < 4 or y2 - y1 < 4:
                return None

            # Prefer Stage-1 landmarks (retina-face 5-point → pad to 68 is not
            # possible; use face_alignment's own estimator on the local crop).
            region = frame_bgr[y1:y2, x1:x2]
            landmarks = self._aligner.get_landmarks_from_image(region)
            landmarks = None if landmarks is None else np.asarray(landmarks)

            if landmarks is not None and landmarks.size >= 2:
                # Tighten crop to landmark extents with 25% margin
                lx = landmarks[:, 0]; ly = landmarks[:, 1]
                mx = 0.25 * max(float(lx.max() - lx.min()), 1.0)
                my = 0.25 * max(float(ly.max() - ly.min()), 1.0)
                cx1 = max(0, int(lx.min() - mx))
                cy1 = max(0, int(ly.min() - my))
                cx2 = min(region.shape[1], int(lx.max() + mx))
                cy2 = min(region.shape[0], int(ly.max() + my))
                if cx2 > cx1 and cy2 > cy1:
                    region = region[cy1:cy2, cx1:cx2]

            return self._resize(region)
        except Exception:  # noqa: S110
            return None

    def align_batch(self, frame_bgr: np.ndarray,
                    faces: list["Face"]) -> list[Optional[np.ndarray]]:
        """Align a list of faces; mirrors :meth:`align` for batch use."""
        return [self.align(frame_bgr, f) for f in faces]

    # -- internals ---------------------------------------------------------
    def _resize(self, region: np.ndarray) -> np.ndarray:
        """Resize a BGR region to (size, size) and convert to uint8 RGB."""
        import cv2  # local import keeps module cheap when cv2 is absent

        out = cv2.resize(region, (self._size, self._size), interpolation=cv2.INTER_AREA)
        rgb = out[:, :, ::-1] if out.ndim == 3 else out
        return np.ascontiguousarray(rgb).astype(np.uint8)
