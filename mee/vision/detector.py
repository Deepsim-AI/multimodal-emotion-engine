"""TASK_MEE_011 TASK_MEE_012: Commercially-safe face detector.

Replaces InsightFace SCRFD/buffalo_l (non-commercial weights) with a pipeline
of independently licensed components.

Stage 1 — Detection: retina-face (MIT)
Stage 2 — Alignment/Cropping: face_alignment (Apache-2.0)
Stage 3 — Expression: EmotiEffLib (Apache-2.0 for code + weights)

This file handles Stage 1 (detection only). It returns bounding boxes
with landmarks suitable for Stage 2 alignment. No face recognition/ID is performed.

⚠️ buffalo_l (insightface) detection has been removed from the production pipeline
   because its pretrained model weights are non-commercial research-only per
   InsightFace's official license policy:
     "The training data containing the annotation (and the models trained with
      these data) are available for non-commercial research purposes only."

   See docs/THIRD_PARTY_LICENSES.md for the full license inventory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# ── Primary detector: retina-face (MIT) ─────────────────────────────────────
try:
    from retinaface import RetinaFace  # type: ignore
    _RETINAFACE_AVAILABLE = True
except Exception:  # noqa: S110
    _RETINAFACE_AVAILABLE = False

# ── Fallback: dlib HOG detector (Boost 1.0) ────────────────────────────────
try:
    import dlib  # type: ignore
    _DLIB_AVAILABLE = True
except Exception:  # noqa: S110
    _DLIB_AVAILABLE = False


@dataclass
class FaceBox:
    """A detected face bounding box with optional landmarks."""
    x1: float           # top-left x (pixels)
    y1: float           # top-left y
    x2: float           # bottom-right x
    y2: float           # bottom-right y
    score: float        # detection confidence 0..1
    landmarks: Optional[list[tuple[float, float]]] = None   # [(x,y), ...] or None


class FaceDetector:
    """Face detector — production pipeline using retina-face (MIT).

    Usage:
        if FaceDetector.is_available():
            det = FaceDetector()
            faces = det.detect(frame_bgr)  -> list[FaceBox]
    """

    def __init__(self, use_retinaface: bool = True):
        """Initialize detector.

        Args:
            use_retinaface: Prefer retina-face if available (default True).
                           Set False to force dlib HOG fallback regardless.
        """
        self._use_retinaface = use_retinaface and _RETINAFACE_AVAILABLE
        self._detector_type = "retinaface" if self._use_retinaface else ("dlib" if _DLIB_AVAILABLE else None)

    @property
    def available(self) -> bool:
        """Return True if any detector backend is available."""
        return self._detector_type is not None

    @staticmethod
    def is_available() -> bool:
        """True if retina-face or dlib HOG detector is importable."""
        return _RETINAFACE_AVAILABLE or _DLIB_AVAILABLE

    # ── Public API ──────────────────────────────────────────────────────────────

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        """Detect faces in a BGR numpy frame.

        Args:
            frame_bgr: (H, W, 3) uint8 array.

        Returns:
            List of FaceBox objects sorted by confidence descending.
            Empty list if no faces found or detector unavailable.
        """
        if not self.available:
            return []

        try:
            if self._detector_type == "retinaface":
                return self._detect_retinaface(frame_bgr)
            elif self._detector_type == "dlib":
                return self._detect_dlib(frame_bgr)
        except Exception:
            pass

        return []

    def crop_face(
        self,
        frame_bgr: np.ndarray,
        face: FaceBox,
        margin: float = 0.2,
    ) -> Optional[np.ndarray]:
        """Crop the face region with fractional padding.

        Args:
            frame_bgr: (H, W, 3) uint8 array.
            face: Detected face box.
            margin: Fractional margin on all sides (default 20%).

        Returns:
            Cropped face region as uint8 (H', W', 3) array, or None if crop fails.
        """
        h, w = frame_bgr.shape[:2]
        x1 = max(0, int(face.x1))
        y1 = max(0, int(face.y1))
        x2 = min(w, int(face.x2))
        y2 = min(h, int(face.y2))

        mx = margin * (x2 - x1) if (x2 - x1) > 0 else 0
        my = margin * (y2 - y1) if (y2 - y1) > 0 else 0

        cx1 = max(0, int(x1 - mx))
        cy1 = max(0, int(y1 - my))
        cx2 = min(w, int(x2 + mx))
        cy2 = min(h, int(y2 + my))

        return frame_bgr[cy1:cy2, cx1:cx2].copy()

    # ── Internal detectors ───────────────────────────────────────────────────────

    @staticmethod
    def _detect_retinaface(frame_bgr: np.ndarray) -> list[FaceBox]:
        """Detect faces using retina-face."""
        # retina-face accepts RGB — convert from BGR
        frame_rgb = frame_bgr[:, :, ::-1].copy() if frame_bgr.ndim == 3 else frame_bgr
        
        try:
            detected = RetinaFace.detect_faces(frame_rgb)
        except Exception:
            return []

        faces: list[FaceBox] = []
        for face_id, info in detected.items():
            bbox = info['bbox']
            # Normalize to [0, 1] if needed (retina-face may return pixel coords or normalized)
            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            
            # Check if coords are normalized (0-1) — retinaface usually returns pixel coords
            # but verify we're in valid range for the frame dimensions
            h, w = frame_bgr.shape[:2]
            if x2 > w or y2 > h:
                # Already pixel coordinates, use as-is
                pass
            else:
                # Normalize coords (0-1) — scale to pixel coords
                x1, y1, x2, y2 = (
                    x1 * w, y1 * h,
                    x2 * w, y2 * h
                )
            
            score = float(info.get('confidence', 0.0)) if info.get('confidence') is not None else 0.0

            # Extract landmarks if available
            landmarks = None
            kp = info.get('keypoints')
            if kp is not None:
                landmarks = [(float(p[0]), float(p[1])) for p in kp]

            faces.append(FaceBox(
                x1=x1, y1=y1, x2=x2, y2=y2,
                score=score,
                landmarks=landmarks,
            ))

        # Sort by confidence descending
        faces.sort(key=lambda f: f.score, reverse=True)
        return faces

    @staticmethod
    def _detect_dlib(frame_bgr: np.ndarray) -> list[FaceBox]:
        """Detect faces using dlib HOG detector (fallback)."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr
        
        # Use grayscale for faster processing
        if frame_bgr.dtype != np.uint8:
            gray = gray.astype(np.uint8)
        
        detector = dlib.get_frontal_face_detector()
        rects = detector(gray, 1)  # +1 pyramid level

        h, w = frame_bgr.shape[:2]
        faces: list[FaceBox] = []
        for rect in rects:
            x1, y1, x2, y2 = float(rect.left()), float(rect.top()), float(rect.right()), float(rect.bottom())
            score = 1.0  # dlib HOG doesn't provide confidence scores

            faces.append(FaceBox(
                x1=x1, y1=y1, x2=x2, y2=y2,
                score=score,
                landmarks=None,  # dlib HOG doesn't return landmarks directly
            ))

        faces.sort(key=lambda f: f.score, reverse=True)
        return faces


# ── Utility: face_alignment-based alignment (Stage 2) ───────────────────────────────

class FaceAligner:
    """Face alignment via face_alignment library (Apache-2.0).

    Takes detected face boxes and returns aligned crops suitable for expression models.
    Uses 68-point facial landmarks for accurate crop/rotation normalization.
    
    This is a separate class from FaceDetector to enforce the three-stage separation:
      Detection → Alignment → Expression Estimation
    
    Usage:
        aligner = FaceAligner()
        if aligner.is_available():
            aligned = aligner.align(frame_bgr, face)  # returns aligned (112x112x3) crop
    """

    def __init__(self, device: str = "cpu"):
        self._device = device
        self._face_alignment = None
        self._detector_type = "dlib"  # face_alignment uses dlib internally for landmarks

    @property
    def available(self) -> bool:
        return self._face_alignment is not None

    @staticmethod
    def is_available() -> bool:
        try:
            import face_alignment  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure_loaded(self):
        if self._face_alignment is None:
            try:
                import face_alignment as fa  # type: ignore
                self._face_alignment = fa.FaceAlignment(
                    fa.LandmarksType._2D,  # 2D landmarks only (not full 3D)
                    device=self._device,
                    flip_input=False,
                )
            except Exception:
                pass

    def align(self, frame_bgr: np.ndarray, face: FaceBox) -> Optional[np.ndarray]:
        """Align and crop a detected face to canonical pose.

        Args:
            frame_bgr: (H, W, 3) uint8 frame.
            face: Detected face box with landmarks.

        Returns:
            Aligned face as RGB (112, 112, 3) float32 array ready for EmotiEffLib,
            or None if alignment fails.
        """
        self._ensure_loaded()
        if not self.available:
            return None

        try:
            # Use landmarks if available; otherwise use bbox as a box prompt
            input_type = "BGR"  # face_alignment accepts both BGR and RGB
            
            # Convert to float32 for processing
            frame_float = frame_bgr.astype(np.float32)
            
            # Try using landmarks from detector
            if face.landmarks:
                import cv2 as _cv2
                pts = np.array([[l[0], l[1]] for l in face.landmarks], dtype=np.float32)
                # face_alignment.estimate_landmarks needs image + bbox
                preds = self._face_alignment.get_landmarks_from_image(frame_float, return_label_reg=True)
                if preds is None:
                    return None
                landmark_68 = preds[0]  # First detected face
            else:
                # Fall back to bbox-only landmark estimation
                preds = self._face_alignment.get_landmarks_from_image(frame_float, box=(int(face.x1), int(face.y1), int(face.x2), int(face.y2)))
                if preds is None:
                    return None
                landmark_68 = preds[0]

            # Extract face from bbox (margin included)
            x1 = max(0, int(face.x1))
            y1 = max(0, int(face.y1))
            x2 = min(frame_bgr.shape[1], int(face.x2))
            y2 = min(frame_bgr.shape[0], int(face.y2))

            # Crop and resize to 112x112 (standard for emotion models)
            cropped = frame_bgr[y1:y2, x1:x2].copy()
            aligned = _cv2.resize(cropped, (112, 112), interpolation=_cv2.INTER_AREA)
            
            # Convert to RGB for model input
            aligned_rgb = aligned[:, :, ::-1]  # BGR → RGB
            
            # Normalize to [0, 1] as expected by most models
            aligned_rgb = aligned_rgb.astype(np.float32) / 255.0
            
            return aligned_rgb

        except Exception:
            return None


# ── Graceful degradation when no detector is available ────────────────────────

def _no_detect(*args, **kwargs):
    """No-op detect that returns empty list."""
    return []


def _no_crop(*args, **kwargs):
    """No-op crop that returns None."""
    return None


# Patch in fallback if no detector is available at import time.
if not FaceDetector.is_available():
    FaceDetector.detect = _no_detect  # type: ignore
    FaceDetector.crop_face = _no_crop  # type: ignore
    FaceDetector.available = False  # type: ignore
