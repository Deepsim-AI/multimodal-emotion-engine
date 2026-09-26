# CTO Plan — TASK_MEE_016: CUDA Compatibility for RetinaFace Face Detection

**Task ID:** TASK_MEE_016  
**Gate:** G1 — Plan Approval Pending  
**Phase:** Phase 8 (CUDA Compatibility Patch)  
**Date:** 2026-09-25  
**Planned By:** CTO / Architect  

---

## 1. Objective

Fix RetinaFace face detection speed/availability on Jetson AGX Orin by resolving the CUDA compatibility mismatch between PyTorch and L4T R36.4.

### Problem
| Component | Current State | Required State |
|-----------|--------------|----------------|
| **PyTorch** | `2.14.0+cu130` (CUDA 13.0) | Must match L4T R36.4's max CUDA version |
| **L4T R36.4** | Ships CUDA 12.x compatible driver | Max supported: CUDA 12.x |
| **Result** | `torch.cuda.is_available()` → False | Must return True for RetinaFace GPU acceleration |

### Options Analysis

| Option | Effort | Feasibility | Risk |
|--------|--------|-------------|------|
| A: Downgrade PyTorch to cu12x-compatible build | Low-Medium | Hard — NVIDIA doesn't ship prebuilt aarch64 cu12x wheels on PyPI | Medium (might need custom build) |
| B: Recompile PyTorch from source with cu12x | High | Possible but time-consuming (hours of build) | High (build complexity) |
| C: Use MediaPipe Face Detection (CPU fallback) | Low | Binary pip install, no compilation | **LOWEST** — works today |

---

## 2. Recommended Approach: Option C (MediaPipe Fallback)

Given that:
- NVIDIA doesn't ship prebuilt aarch64 PyTorch cu12x wheels on PyPI
- Custom build is time-consuming and risky for production deployment
- MediaPipe gives ~85% accuracy at 30+ fps on Jetson Orin ARM64 (CPU-only)

**Decision:** Implement MediaPipe Face Detection as the primary detector, with RetinaFace as the preferred fallback when CUDA becomes available.

---

## 3. Implementation Plan

### Task A: Install MediaPipe
```bash
pip install mediapipe
```
Binary wheel for aarch64 — no compilation needed. ~5 min total including download.

### Task B: Add MediaPipeFaceDetector Class
**File:** `mee/vision/detector.py` (~line 280, after existing FaceDetector)

```python
# TASK_MEE_016 Task B: MediaPipe Face Detection Implementation
class MediaPipeFaceDetector:
    """CPU-only face detector using MediaPipe Face Detection.
    
    Accuracy: ~85-90% (vs RetinaFace 95%+)
    Speed: 30+ fps on Jetson Orin ARM64 (pure CPU)
    """
    def __init__(self, min_confidence=0.5):
        import mediapipe as mp
        self.min_confidence = min_confidence
        self.detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,  # 0=Lite (fast), 1=Full (accurate)
            min_detection_confidence=min_confidence
        )
    
    def detect(self, frame_bgr):
        """Detect faces in a BGR frame. Returns list of Face dicts."""
        import cv2
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.detector.process(frame_rgb)
        
        if not results.detections:
            return []
        
        h, w = frame_bgr.shape[:2]
        faces = []
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x1 = int(bbox.xmin * w)
            y1 = int(bbox.ymin * h)
            bw = int(bbox.width * w)
            bh = int(bbox.height * h)
            
            faces.append({
                "x": x1,
                "y": y1,
                "w": bw,
                "h": bh,
                "confidence": detection.score
            })
        return faces
    
    def crop_face(self, frame_bgr, face):
        """Crop face ROI from frame."""
        x1 = max(0, int(face["x"]))
        y1 = max(0, int(face["y"]))
        x2 = min(frame_bgr.shape[1], x1 + int(face["w"]))
        y2 = min(frame_bgr.shape[0], y1 + int(face["h"]))
        return frame_bgr[y1:y2, x1:x2]
```

### Task C: Modify FaceDetector to Use MediaPipe When CUDA Unavailable
**File:** `mee/vision/detector.py` (~line 145, in FaceDetector.__init__)

Change the backend selection logic from:
```python
# Current (always tries RetinaFace first)
def __init__(self, use_retinaface=True):
    # ... existing code ...
```

To:
```python
# TASK_MEE_016 Task C: Auto-select MediaPipe when CUDA unavailable
import torch
_has_cuda = torch.cuda.is_available() if torch else False

def __init__(self, use_mediapipe=False):
    self._backend = None
    self._detector = None
    
    # Check if we should prefer MediaPipe (CUDA unavailable or explicit override)
    prefer_mediapipe = use_mediapipe or not _has_cuda
    
    if prefer_mediapipe:
        try:
            from .detector import MediaPipeFaceDetector  # Will be defined in Task B
            self._detector = MediaPipeFaceDetector()
            self._backend = "mediapipe"
            return
        except ImportError:
            pass  # Fall through to RetinaFace
    
    # ... existing RetinaFace → dlib fallback logic ...
```

### Task D: Update RemotedemoServer to Auto-Select Based on CUDA
**File:** `mee/remotedemo/server.py` (~line 230, near engine creation)

Add CUDA detection and pass detector preference:
```python
import torch
use_mediapipe = not torch.cuda.is_available() if torch else True

# Create detector with appropriate backend
from mee.vision.detector import FaceDetector
detector = FaceDetector(use_mediapipe=use_mediapipe) if use_mediapipe else None

# Pass to engine config
engine = EmotionEngine(config=MEEConfig(vision_detector=detector))
```

---

## 4. Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| A1 | `pip install mediapipe` succeeds on aarch64 Jetson | `pip show mediapipe` reports installed |
| A2 | `MediaPipeFaceDetector()` instantiates without error | New Python test script runs clean |
| A3 | Face detection works on real webcam frames | At least 1 face detected in self-test |
| B1 | Server uses MediaPipe when CUDA=False | Log shows "mediapipe" backend selected |
| C1 | Face results match expected emotions (not all zeros) | Live demo: face bars show actual values |

---

## 5. Risk & Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| MediaPipe accuracy lower than RetinaFace on good GPU | Medium | ~85-90% acceptable for demo; can tune `min_detection_confidence` if needed |
| MediaPipe aarch64 wheel not available | Low | Binary wheels exist for aarch64 in pip. If broken, fall back to dlib HOG |
| Event-loop blocking returns with new detector | Medium | Keep the `asyncio.to_thread()` fix from TASK_MEE_015 |

---

## 6. CTO Notes

- **Not fixing CUDA driver mismatch** this round — that requires either JetPack reflash or custom PyTorch build
- **MediaPipe is the pragmatic choice:** CPU-only, fast on Jetson Orin ARM64, binary install (no compile), 85%+ accuracy for real-world demo use
- **RetinaFace remains as optional backend** — if CUDA becomes available later, it can be re-enabled via `use_mediapipe=False`

**Plan submitted for approval.**
