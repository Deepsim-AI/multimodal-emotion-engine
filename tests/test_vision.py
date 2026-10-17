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
# TASK_MEE_013: detection-frequency knob (detect_every_n_frames)
# ---------------------------------------------------------------------------

class CountingFaceDetector:
    """Stub detector that counts detect() invocations."""

    def __init__(self):
        self.available = True
        self.model_type = "counting-fake"
        self.detect_calls = 0

    def detect(self, frame_bgr):
        self.detect_calls += 1
        h, w = frame_bgr.shape[:2]
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


class CountingNoFaceDetector:
    """Stub detector returning no faces; counts detect() invocations."""

    def __init__(self):
        self.available = True
        self.model_type = "counting-noface"
        self.detect_calls = 0

    def detect(self, frame_bgr):
        self.detect_calls += 1
        return []

    def crop_face(self, frame_bgr, face):
        return None


class CountingEmotionModel:
    """Stub emotion model that counts predict() invocations."""

    def __init__(self):
        self.available = True
        self.model_type = "counting-fer"
        self.predict_calls = 0

    def predict(self, frame_bgr, face_crop=None):
        self.predict_calls += 1
        scores = {l: 0.0 for l in EMOTION_LABELS}
        scores["happy"] = 0.95
        return {"emotion": "happy", "confidence": 0.95, "scores": scores}


class SwitchingDetector:
    """Detector whose result depends on frame content: face when sum>0 else none."""

    def __init__(self):
        self.available = True
        self.model_type = "switching-fake"
        self.detect_calls = 0

    def detect(self, frame_bgr):
        self.detect_calls += 1
        if int(np.sum(frame_bgr)) > 0:  # non-zero frame => face
            h, w = frame_bgr.shape[:2]
            x1 = w * 0.35
            y1 = h * 0.25
            x2 = w * 0.65
            y2 = h * 0.75
            return [Face(bbox=np.array([x1, y1, x2, y2]), det_score=0.92)]
        return []

    def crop_face(self, frame_bgr, face):
        x1, y1, x2, y2 = face.bbox.astype(int)
        return frame_bgr[y1:y2, x1:x2]


def test_mee013_default_detection_every_call():
    """n == 1 (default): detector runs on every process() call."""
    det = CountingFaceDetector()
    emo = CountingEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo)
    frame = _make_frame()

    for _ in range(5):
        result = vp.process(frame)
        assert result.has_face is True
        assert result.emotion == "happy"

    assert det.detect_calls == 5
    assert emo.predict_calls == 5


def test_mee013_decoupling_n3():
    """n == 3: 6 process() calls on the same frame => 2 detections, 6 emotion passes,
    identical outputs across reused calls."""
    det = CountingFaceDetector()
    emo = CountingEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=3)
    frame = _make_frame()

    results = [vp.process(frame) for _ in range(6)]

    assert det.detect_calls == 2          # calls #1 and #4
    assert emo.predict_calls == 6         # every pass runs emotion
    for r in results:
        assert r.has_face is True
        assert r.emotion == "happy"
        assert r.confidence == pytest.approx(0.95, abs=0.01)
    # Reused results feed Stage 3 exactly as fresh detections: identical output
    for r in results[1:]:
        assert r.face_count == results[0].face_count
        assert r.best_emotion == results[0].best_emotion
        assert set(r.scores.keys()) == set(results[0].scores.keys())


def test_mee013_staleness_frame_identity():
    """n == 3: different array object invalidates cache — detection re-runs.

    Frame A (non-zero) detects a face; frame B (zeros) is a different array
    object, so the cached face must NOT be reused: detection re-runs and
    reports B's no-face state.
    """
    det = SwitchingDetector()
    emo = CountingEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=3)

    frame_a = _make_frame()  # non-zero => face
    result_a = vp.process(frame_a)
    assert result_a.has_face is True
    assert det.detect_calls == 1

    # call #2 is within the n=3 window but frame B is a different object
    frame_b = np.zeros((200, 300, 3), dtype=np.uint8)  # zero => no face
    result_b = vp.process(frame_b)
    assert det.detect_calls == 2  # stale cache rejected, re-detected
    assert result_b.has_face is False  # B's true no-face state, not A's cached face


def test_mee013_staleness_shape_change():
    """n == 3: same array object but a different shape view forces re-detection.

    A sub-view of the same array has a different shape; the shape check must
    trigger re-detection rather than reusing the stale bbox (defensive check)."""
    det = CountingFaceDetector()
    emo = CountingEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=3)

    frame = _make_frame()  # (200, 300, 3)
    r1 = vp.process(frame)
    assert r1.has_face is True
    assert det.detect_calls == 1

    # Same buffer, different shape: (100, 300, 3)
    view = frame[:100, :, :]  # type: ignore[assignment]
    r2 = vp.process(view)
    assert det.detect_calls == 2  # shape change forced re-detection
    assert r2.has_face is True


def test_mee013_noface_state_cached():
    """n == 2: no-face state is cached and reused for the next call
    (cheap no-face result) until a changed frame re-triggers detection (G4 R3)."""
    det = CountingNoFaceDetector()
    emo = CountingEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=2)
    frame = _make_frame()

    r1 = vp.process(frame)
    assert r1.has_face is False
    assert det.detect_calls == 1

    # same frame, call #2 within window: cached no-face reused
    r2 = vp.process(frame)
    assert r2.has_face is False
    assert det.detect_calls == 1
    assert emo.predict_calls == 0  # no faces => no emotion pass either way

    # call #3 due for detection again
    r3 = vp.process(frame)
    assert r3.has_face is False
    assert det.detect_calls == 2


def test_mee013_force_detection():
    """force_detection=True bypasses the cache and re-runs detection."""
    det = CountingFaceDetector()
    emo = CountingEmotionModel()
    vp = VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=3)
    frame = _make_frame()

    vp.process(frame)
    assert det.detect_calls == 1

    vp.process(frame)  # normally cached (call #2)
    assert det.detect_calls == 1

    vp.process(frame, force_detection=True)  # forced re-detection
    assert det.detect_calls == 2


def test_mee013_validation():
    """detect_every_n_frames < 1 raises ValueError (no silent clamp)."""
    det = CountingFaceDetector()
    emo = CountingEmotionModel()
    with pytest.raises(ValueError):
        VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=0)
    with pytest.raises(ValueError):
        VisionProcessor(detector=det, emotion_model=emo, detect_every_n_frames=-1)


def test_mee013_engine_config_field():
    """MEEConfig exposes detect_every_n_frames with default None (= 1 pass behavior)."""
    from mee.api.engine import MEEConfig

    cfg = MEEConfig()
    assert cfg.detect_every_n_frames is None  # default unset -> engine passes 1

    cfg2 = MEEConfig(detect_every_n_frames=4)
    assert cfg2.detect_every_n_frames == 4


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


# ---------------------------------------------------------------------------
# TASK_MEE_016: MediaPipe Face Detection backend (Jetson AGX Orin CPU path)
# ---------------------------------------------------------------------------

def test_mee016_mediapipe_detector_instantiable():
    """TASK_MEE_016 A2: MediaPipeFaceDetector instantiates without error."""
    from mee.vision.detector import MediaPipeFaceDetector
    det = MediaPipeFaceDetector(min_detection_confidence=0.5)
    assert det is not None


def test_mee016_mediapipe_detect_returns_face_list():
    """TASK_MEE_016 A3 (structural): detect() on a synthetic frame returns a
    list (empty for an all-zeros frame). MediaPipe itself has already been
    smoke-verified at install time; here we only check the wrapper contract.
    """
    from mee.vision.detector import MediaPipeFaceDetector
    det = MediaPipeFaceDetector(min_detection_confidence=0.5)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = det.detect(frame)
    assert isinstance(faces, list)


def test_mee016_mediapipe_detect_rejects_non_array():
    """detect() must return [] for non-array input (contract with other backends)."""
    from mee.vision.detector import MediaPipeFaceDetector
    det = MediaPipeFaceDetector(min_detection_confidence=0.5)
    assert det.detect(None) == []
    assert det.detect("not-an-array") == []


def test_mee016_face_detector_autoselect_mediapipe_when_cuda_unavailable():
    """TASK_MEE_016 B1: when torch.cuda.is_available() is False (this host
    = Jetson AGX Orin with cu130 PyTorch + cu12.x driver), FaceDetector
    auto-selects the MediaPipe CPU backend.
    """
    from mee.vision.detector import FaceDetector
    det = FaceDetector()  # use_mediapipe=None → auto
    assert det.model_type == "mediapipe", (
        f"expected auto-select to prefer mediapipe on this host, got {det.model_type}"
    )


def test_mee016_face_detector_explicit_use_mediapipe():
    """Explicit use_mediapipe=True forces the MediaPipe backend."""
    from mee.vision.detector import FaceDetector
    det = FaceDetector(use_mediapipe=True)
    assert det.model_type == "mediapipe"


def test_mee016_face_detector_forced_mediapipe_on_no_face_frame():
    """detect() must still return [] (not raise) on a synthetic no-face frame."""
    from mee.vision.detector import FaceDetector
    det = FaceDetector(use_mediapipe=True)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert det.detect(frame) == []


def test_mee016_processor_threads_use_mediapipe():
    """VisionProcessor exposes use_mediapipe and forwards it to the detector."""
    from mee.vision.processor import VisionProcessor
    vp = VisionProcessor(use_mediapipe=True)
    assert vp._detector.model_type == "mediapipe"


def test_mee016_meeconfig_has_use_mediapipe():
    """MEEConfig exposes use_mediapipe with default None (= auto)."""
    from mee.api.engine import MEEConfig
    cfg = MEEConfig()
    assert cfg.use_mediapipe is None
    cfg2 = MEEConfig(use_mediapipe=True)
    assert cfg2.use_mediapipe is True


def test_mee016_mediapipe_detector_is_available():
    """MediaPipeFaceDetector.is_available() must reflect mediapipe importability."""
    from mee.vision.detector import MediaPipeFaceDetector
    # On this host mediapipe is installed (verified at install time).
    assert MediaPipeFaceDetector.is_available() is True
