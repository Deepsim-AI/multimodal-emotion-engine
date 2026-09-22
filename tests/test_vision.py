"""TASK_MEE_004: Vision emotion engine tests.

Tests the detector, emotion model, and processor interfaces.
Runs with fake models (no real model downloads).
"""

import numpy as np
import pytest

from mee.vision.detector import FaceDetector, Face
from mee.vision.emotion_model import EmotionModel, EMOTION_LABELS
from mee.vision.processor import VisionProcessor, VisionResult, FaceEmotion
from tests.helpers import is_jetson


# TASK_MEE_010: skip GPU-specific tests on non-Jetson environments
requires_jetson = pytest.mark.skipif(
    not is_jetson(), reason="Jetson GPU hardware required"
)


# ---------------------------------------------------------------------------
# EmotionModel
# ---------------------------------------------------------------------------

class FakeEmotionModel:
    """Stub that returns a fixed happy prediction."""

    def __init__(self):
        self.available = True
        self.model_type = "fake-fer"

    def predict(self, frame_bgr, face_crop=None):
        scores = {l: 0.0 for l in EMOTION_LABELS}
        scores["happy"] = 0.95
        return {"emotion": "happy", "confidence": 0.95, "scores": scores}

    def predict_face(self, crop):
        return self.predict(None, face_crop=crop)


class FakeEmotionModelNoFace:
    """Stub with no backend (degraded)."""

    def __init__(self):
        self.available = False
        self.model_type = "none"

    def predict(self, frame_bgr, face_crop=None):
        scores = {l: 0.0 for l in EMOTION_LABELS}
        return {"emotion": "neutral", "confidence": 0.0, "scores": scores}

    def predict_face(self, crop):
        return self.predict(None, face_crop=crop)


def test_emotion_model_interface():
    m = FakeEmotionModel()
    result = m.predict(None)
    assert result["emotion"] in EMOTION_LABELS
    assert 0.0 <= result["confidence"] <= 1.0
    assert set(result["scores"].keys()) == set(EMOTION_LABELS)


def test_emotion_model_labels():
    assert len(EMOTION_LABELS) == 7
    assert "neutral" in EMOTION_LABELS
    assert "happy" in EMOTION_LABELS
    assert "anger" in EMOTION_LABELS


def test_emotion_model_degraded():
    m = FakeEmotionModelNoFace()
    result = m.predict(None)
    assert result["emotion"] == "neutral"
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# FaceDetector (interface test with stub)
# ---------------------------------------------------------------------------

class FakeFaceDetector:
    """Stub detector returning one fixed face."""

    def __init__(self):
        self.available = True
        self.model_type = "fake-scrfd"

    def detect(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        # One face in the center, 25% of width
        x1 = w * 0.35
        y1 = h * 0.25
        x2 = w * 0.65
        y2 = h * 0.75
        return [Face(bbox=np.array([x1, y1, x2, y2]), det_score=0.92)]

    def crop_face(self, frame_bgr, face):
        h, w = frame_bgr.shape[:2]
        x1 = int(face.bbox[0]); y1 = int(face.bbox[1])
        x2 = int(face.bbox[2]); y2 = int(face.bbox[3])
        return frame_bgr[y1:y2, x1:x2]


def test_detector_interface():
    d = FakeFaceDetector()
    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    faces = d.detect(frame)
    assert len(faces) == 1
    f = faces[0]
    assert 0.0 <= f.det_score <= 1.0
    # bbox should be a 4-element array
    assert len(f.bbox) == 4
    assert f.bbox[2] > f.bbox[0]  # x2 > x1
    assert f.bbox[3] > f.bbox[1]  # y2 > y1


def test_detector_crop_face():
    d = FakeFaceDetector()
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    faces = d.detect(frame)
    crop = d.crop_face(frame, faces[0])
    assert crop is not None
    assert crop.ndim == 3
    assert crop.shape[0] > 0 and crop.shape[1] > 0


def test_detector_no_face():
    class NoFaceDetector:
        available = True
        model_type = "none"
        def detect(self, frame):
            return []
        def crop_face(self, frame, face):
            return None

    d = NoFaceDetector()
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    assert d.detect(frame) == []


# ---------------------------------------------------------------------------
# VisionProcessor
# ---------------------------------------------------------------------------

def _make_frame():
    """Create a random BGR frame (200x300)."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)


def test_processor_with_face():
    det = FakeFaceDetector()
    emo = FakeEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    result = vp.process(_make_frame())

    assert result.has_face is True
    # TASK_MEE_004: engine-facing fields
    assert result.emotion == "happy"
    assert result.confidence == pytest.approx(0.95, abs=0.01)
    assert set(result.scores.keys()) == set(EMOTION_LABELS)
    # Richer fields
    assert result.face_count == 1
    assert result.best_emotion == "happy"
    assert result.best_confidence == pytest.approx(0.95, abs=0.01)
    assert len(result.faces) == 1
    f = result.faces[0]
    assert f.label == "happy"
    assert f.confidence > 0.5
    assert set(f.scores.keys()) == set(EMOTION_LABELS)
    assert "vision" in result.channel_scores


def test_processor_process_frame_alias():
    det = FakeFaceDetector()
    emo = FakeEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    result = vp.process_frame(_make_frame())
    assert result.has_face is True
    assert result.emotion == "happy"


def test_processor_no_face():
    det = type("NoFace", (), {
        "available": True, "model_type": "none",
        "detect": lambda self, f: [],
        "crop_face": lambda self, f, face: None,
    })()
    emo = FakeEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    result = vp.process(_make_frame())

    assert result.has_face is False
    assert result.face_count == 0
    assert result.faces == []
    assert result.best_emotion == ""
    assert result.best_confidence == 0.0


def test_processor_degraded_emotion():
    det = FakeFaceDetector()
    emo = FakeEmotionModelNoFace()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    result = vp.process(_make_frame())

    assert result.has_face is True
    assert result.best_emotion == "neutral"
    assert result.best_confidence == 0.0


def test_processor_channel_scores_structure():
    det = FakeFaceDetector()
    emo = FakeEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    result = vp.process(_make_frame())

    if result.has_face:
        scores = result.channel_scores.get("vision", {})
        assert set(scores.keys()) == set(EMOTION_LABELS)
        # Scores should be in [0, 1]
        for v in scores.values():
            assert 0.0 <= v <= 1.0


def test_processor_multiple_faces():
    class MultiFaceDetector:
        available = True
        model_type = "multi-fake"
        def detect(self, frame):
            h, w = frame.shape[:2]
            return [
                Face(bbox=np.array([w*0.1, h*0.2, w*0.35, h*0.6]), det_score=0.9),
                Face(bbox=np.array([w*0.6, h*0.2, w*0.9, h*0.6]), det_score=0.7),
            ]
        def crop_face(self, frame, face):
            x1, y1, x2, y2 = face.bbox.astype(int)
            return frame[y1:y2, x1:x2]

    det = MultiFaceDetector()
    emo = FakeEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    result = vp.process(_make_frame())

    assert result.has_face is True
    assert result.face_count == 2
    assert len(result.faces) == 2
    # Both should get a prediction
    for f in result.faces:
        assert f.label in EMOTION_LABELS
        assert f.confidence > 0


# ---------------------------------------------------------------------------
# TASK_MEE_010: Jetson GPU-specific tests
# ---------------------------------------------------------------------------

@requires_jetson
def test_jetson_gpu_available():
    """Verify the Jetson GPU is visible to the runtime."""
    import torch
    assert torch.cuda.is_available(), "CUDA device not available on Jetson"

@requires_jetson
def test_jetson_vision_inference_runs():
    """Run a real vision inference cycle on Jetson GPU (no crash, valid output)."""
    from mee.vision.processor import VisionProcessor
    vp = VisionProcessor()
    frame = _make_frame()
    result = vp.process_frame(frame)
    assert result is not None
    # Output must be structurally valid regardless of face detection result
    assert hasattr(result, "emotion")
    assert hasattr(result, "has_face")
