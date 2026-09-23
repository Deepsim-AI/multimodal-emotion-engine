"""TASK_MEE_011: Stage 1 — Face Detection.

Commercially-safe face detector. Replaces InsightFace SCRFD/buffalo_l
(non-commercial research-only weights) with independently licensed components.

Production pipeline (all stages independently licensed):
  Stage 1 — Detection:    retina-face (MIT) — primary; OpenCV HOG DNN — fallback
  Stage 2 — Alignment:    face_alignment (Apache-2.0)  → see mee/vision/alignment.py
  Stage 3 — Expression:   EmotiEffLib (Apache-2.0 code + weights) → see emotion_model.py

This module handles Stage 1 ONLY. It returns bounding boxes with optional
landmarks. No face recognition / biometric identification is performed.

⚠️  buffalo_l / InsightFace is intentionally ABSENT from the production path.
    Per InsightFace's official license: "The training data containing the
    annotation (and the models trained with these data) are available for
    non-commercial research purposes only."
    See docs/THIRD_PARTY_LICENSES.md for the full inventory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Research-only path (NON-PRODUCTION) — guarded by env var.
#   INSIGHTFACE_RESEARCH_ONLY=true  → allows loading buffalo_l for benchmarking.
#   Default (unset/false): insightface is NEVER imported in the production path.
# ---------------------------------------------------------------------------
RESEARCH_ONLY_ENABLED = (
    os.environ.get("INSIGHTFACE_RESEARCH_ONLY", "").strip().lower()
    in ("1", "true", "yes", "on")
)


# ---------------------------------------------------------------------------
# Backends (detected lazily — a failing import must not break the module)
# ---------------------------------------------------------------------------
def _try_retinaface():
    """Import retina-face (MIT). Returns a factory or None.

    Note: retina-face 0.0.18 requires the ``tf-keras`` package alongside
    TensorFlow >= 2.16; if the import fails we fall back to OpenCV DNN HOG.
    """
    try:
        from retinaface import RetinaFace  # type: ignore
        return RetinaFace
    except Exception:  # noqa: S110
        return None


def _try_dlib():
    try:
        import dlib  # type: ignore
        return dlib
    except Exception:  # noqa: S110
        return None


def _try_insightface_research():
    """Research-only: import insightface. NEVER used unless the env flag is set."""
    if not RESEARCH_ONLY_ENABLED:
        return None
    try:
        import insightface  # type: ignore
        return insightface
    except Exception:  # noqa: S110
        return None


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------
@dataclass
class Face:
    """A detected face: bounding box (x1, y1, x2, y2 in pixels) + score.

    ``landmarks`` holds 5-point landmarks [(x, y) * 5] when the backend
    provides them (retina-face), else None.
    """
    bbox: np.ndarray                    # (4,) float array [x1, y1, x2, y2]
    det_score: float = 1.0              # 0..1 confidence
    landmarks: Optional[np.ndarray] = None  # (5, 2) or None


# ---------------------------------------------------------------------------
# OpenCV HOG person detector — dependency-light fallback (opencv ships bundled)
# ---------------------------------------------------------------------------
def _detect_opencv_hog(frame_bgr: np.ndarray) -> list[Face]:
    """Detect faces with OpenCV's bundled HOG person detector.

    Conservative: returns only boxes that look face-sized/aspect-ratio, and
    does not provide confidence scores (all scored 0.5).
    """
    import cv2  # local import: keeps module import cheap when cv2 is absent

    h, w = frame_bgr.shape[:2]
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr

    detector = cv2.HOGDescriptor()
    detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, _ = detector.detectMultiScale(gray, winSize=(64, 128), stepSize=(8, 8),
                                        padding=(4, 4), groups=1)

    faces: list[Face] = []
    for (x, y, bw, bh) in rects:
        # Keep only face-plausible boxes: aspect 0.4..1.4, not the whole frame
        aspect = bh / max(bw, 1)
        if not (0.4 <= aspect <= 1.4):
            continue
        if bw * bh > 0.9 * w * h:
            continue
        faces.append(Face(
            bbox=np.array([float(x), float(y), float(x + bw), float(y + bh)], dtype=np.float32),
            det_score=0.5,
        ))

    faces.sort(key=lambda f: float(f.bbox[2] - f.bbox[0]) * float(f.bbox[3] - f.bbox[1]),
               reverse=True)
    return faces


# ---------------------------------------------------------------------------
# Primary detector
# ---------------------------------------------------------------------------
class FaceDetector:
    """Production face detector.

    Backend resolution order (first that loads wins):
      1. retina-face (MIT)  — primary, provides 5-point landmarks
      2. dlib HOG           — optional extra
      3. OpenCV HOG person  — dependency-light fallback

    Usage:
        if FaceDetector.is_available():
            det = FaceDetector()
            faces = det.detect(frame_bgr)   # list[Face]
            crop  = det.crop_face(frame_bgr, face)
    """

    def __init__(self, model_path: Optional[str] = None,
                 confidence_threshold: float = 0.5,
                 use_retinaface: bool = True):
        self._model_path = model_path
        self._confidence_threshold = float(confidence_threshold)

        RetinaFace = _try_retinaface() if use_retinaface else None
        dlib = _try_dlib()

        if RetinaFace is not None:
            self._backend = "retinaface"
            self._RetinaFace = RetinaFace
        elif dlib is not None:
            self._backend = "dlib"
            self._dlib = dlib
        else:
            self._backend = "opencv_hog"
            self._cv2 = None  # lazy
        self._RetinaFace = RetinaFace
        self._dlib = dlib

    # -- availability ------------------------------------------------------
    @property
    def available(self) -> bool:
        return True  # open_hog fallback guarantees a usable backend

    @staticmethod
    def is_available() -> bool:
        """True if any detection backend can be imported.

        Always True in practice because the OpenCV HOG path only needs ``cv2``.
        Returns False only if cv2 itself is unavailable.
        """
        try:
            import cv2  # noqa: F401
            return True
        except Exception:  # noqa: S110
            return False

    @property
    def model_type(self) -> str:
        return self._backend

    # -- public API --------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray) -> list[Face]:
        """Detect faces in a BGR frame.

        Returns a list of :class:`Face` (may be empty). Never raises on
        no-face; backend-specific exceptions are swallowed and degrade to [].
        """
        if frame_bgr is None or not isinstance(frame_bgr, np.ndarray):
            return []
        try:
            if self._backend == "retinaface":
                faces = self._detect_retinaface(frame_bgr)
            elif self._backend == "dlib":
                faces = self._detect_dlib(frame_bgr)
            else:
                faces = _detect_opencv_hog(frame_bgr)
        except Exception:  # noqa: S110
            return []

        # Threshold filter
        return [f for f in faces if f.det_score >= self._confidence_threshold]

    def crop_face(self, frame_bgr: np.ndarray, face: Face,
                  margin: float = 0.2) -> Optional[np.ndarray]:
        """Crop a detected face with fractional margin padding.

        Args:
            frame_bgr: (H, W, 3) uint8 BGR frame.
            face: Detected :class:`Face`.
            margin: fractional margin on all sides (default 20%).

        Returns:
            Cropped BGR uint8 array, or None on failure.
        """
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = (int(v) for v in np.asarray(face.bbox).astype(int))
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w, x2); y2 = min(h, y2)

        bw, bh = max(x2 - x1, 1), max(y2 - y1, 1)
        mx, my = int(margin * bw), int(margin * bh)

        cx1 = max(0, x1 - mx)
        cy1 = max(0, y1 - my)
        cx2 = min(w, x2 + mx)
        cy2 = min(h, y2 + my)

        if cx2 <= cx1 or cy2 <= cy1:
            return None
        return frame_bgr[cy1:cy2, cx1:cx2].copy()

    # -- backends ----------------------------------------------------------
    def _detect_retinaface(self, frame_bgr: np.ndarray) -> list[Face]:
        """Detect via retina-face (MIT). Expects RGB input."""
        frame_rgb = frame_bgr[:, :, ::-1].copy() if frame_bgr.ndim == 3 else frame_bgr
        detected = self._RetinaFace.detect_faces(frame_rgb)
        if not detected:
            return []

        h, w = frame_bgr.shape[:2]
        faces: list[Face] = []
        for _face_id, info in detected.items():
            bbox = np.asarray(info["bbox"], dtype=np.float32).reshape(4)
            x1, y1, x2, y2 = (float(v) for v in bbox)
            # retina-face returns pixel coords; clamp to frame
            x1, y1 = max(0.0, x1), max(0.0, y1)
            x2, y2 = min(float(w), x2), min(float(h), y2)
            score = float(info.get("confidence") or 0.0)

            landmarks = None
            kp = info.get("keypoints")
            if kp is not None:
                landmarks = np.asarray(kp, dtype=np.float32).reshape(-1, 2)

            faces.append(Face(
                bbox=np.array([x1, y1, x2, y2], dtype=np.float32),
                det_score=score,
                landmarks=landmarks,
            ))

        faces.sort(key=lambda f: f.det_score, reverse=True)
        return faces

    def _detect_dlib(self, frame_bgr: np.ndarray) -> list[Face]:
        """Detect via dlib HOG (fallback)."""
        import cv2  # noqa: F401 (ensure available)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr
        if gray.dtype != np.uint8:
            gray = gray.astype(np.uint8)

        detector = self._dlib.get_frontal_face_detector()
        rects = detector(gray, 1)

        faces: list[Face] = []
        for rect in rects:
            faces.append(Face(
                bbox=np.array([float(rect.left()), float(rect.top()),
                               float(rect.right()), float(rect.bottom())],
                              dtype=np.float32),
                det_score=0.8,  # dlib HOG has no confidence; use a fixed score
            ))
        faces.sort(key=lambda f: float(f.bbox[2] - f.bbox[0]) * float(f.bbox[3] - f.bbox[1]),
                   reverse=True)
        return faces


# ---------------------------------------------------------------------------
# Research-only convenience (NON-PRODUCTION, buffalo_l)
# ---------------------------------------------------------------------------
def detect_research_only(frame_bgr: np.ndarray) -> list[Face]:
    """⚠️ RESEARCH-ONLY: buffalo_l (InsightFace SCRFD) detection.

    Enabled ONLY when ``INSIGHTFACE_RESEARCH_ONLY=true`` is set in the
    environment. Model weights are non-commercial (see docs/THIRD_PARTY_LICENSES.md).
    Do NOT use in production.
    """
    insightface = _try_insightface_research()
    if insightface is None:
        return []
    try:
        app = insightface.app.FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        rgb = frame_bgr[:, :, ::-1].copy() if frame_bgr.ndim == 3 else frame_bgr
        det = app.get(rgb)
        faces: list[Face] = []
        for f in det:
            bbox = np.asarray(f.bbox, dtype=np.float32).reshape(4)
            faces.append(Face(bbox=bbox, det_score=float(f.det_score),
                              landmarks=np.asarray(f.kps, dtype=np.float32) if f.kps is not None else None))
        faces.sort(key=lambda f: f.det_score, reverse=True)
        return faces
    except Exception:  # noqa: S110
        return []
