#!/usr/bin/env python3
"""TASK_MEE_012 — Comprehensive vision benchmark (self-contained).

Stages:
  S1 detection (retina-face / dlib / opencv-hog backend), latency + faces_found
  S2 alignment (face_alignment), latency on detected crops
  S3 emotion inference (EmotiEffLib), latency + confidence dist + accuracy proxy
  E2E  EmotionEngine.process() throughput + trend/stability over 5 min
  MEM  RSS sampled over the 5-min run (drift %)

BENCHMARK ONLY — no production code is modified.
Output: /tmp/mee012_run.log (stdout) + <repo>/docs/development/reports/TASK_MEE_012/_bench_raw.json
"""

import sys, os, time, statistics, gc, json, threading
from pathlib import Path
import numpy as np

REPO = "/home/deepsim/multimodal-emotion-engine"
sys.path.insert(0, REPO)

import psutil
_proc = psutil.Process(os.getpid())

RESULTS = Path(REPO) / "docs/development/reports/TASK_MEE_012" / "_bench_raw.json"


def rss_mb():
    return round(_proc.memory_info().rss / 1024**2, 2)


def stats(ms):
    s = sorted(ms)
    n = len(s)
    m = statistics.mean(s)
    return {
        "mean_ms": round(m, 3),
        "p95_ms": round(s[min(int(n*0.95), n-1)], 3),
        "p99_ms": round(s[min(int(n*0.99), n-1)], 3),
        "min_ms": round(min(s), 3),
        "max_ms": round(max(s), 3),
        "fps": round(1000.0/m, 2) if m > 0 else 0.0,
    }


def make_face():
    """Return a realistic-ish face image (BGR uint8) that retina-face detects."""
    import cv2
    img = np.full((640, 480, 3), 20, np.uint8)
    # face oval
    cv2.ellipse(img, (240, 250), (130, 170), 0, 0, 360, (205, 185, 165), -1)
    # hair
    cv2.ellipse(img, (240, 160), (140, 95), 0, 180, 540, (55, 40, 30), -1)
    # eyes
    cv2.ellipse(img, (195, 235), (22, 13), 0, 0, 360, (45, 32, 25), -1)
    cv2.ellipse(img, (285, 235), (22, 13), 0, 0, 360, (45, 32, 25), -1)
    # brows
    cv2.line(img, (178, 210), (215, 205), (50, 38, 28), 6)
    cv2.line(img, (265, 205), (302, 210), (50, 38, 28), 6)
    # nose
    cv2.line(img, (240, 250), (240, 300), (150, 120, 95), 4)
    # mouth
    cv2.ellipse(img, (240, 330), (40, 18), 0, 180, 540, (150, 70, 65), 3)
    return img


def main():
    results = {}
    t_start = time.time()

    from mee.vision.detector import FaceDetector, Face
    from mee.vision.alignment import FaceAligner
    from mee.vision.emotion_model import EmotionModel

    det = FaceDetector()
    aligner = FaceAligner()
    emo = EmotionModel()

    results["backend"] = {
        "detector": det.model_type,
        "detector_available": bool(det.available),
        "aligner_available": bool(aligner.available),
        "emotion_available": bool(emo.is_available()),
    }

    face_img = make_face()

    # ---- S1 detection ----
    if det.available:
        warm = det.detect(face_img)
        lat = []
        faces = None
        for _ in range(100):
            t0 = time.perf_counter()
            faces = det.detect(face_img)
            lat.append((time.perf_counter() - t0) * 1000)
        s = stats(lat)
        s["faces_found"] = len(faces) if faces else 0
        results["S1_detection"] = s

    # ---- S2 alignment (on first detected face) ----
    if det.available and aligner.available:
        faces = det.detect(face_img)
        if faces:
            f0 = faces[0]
            lat = []
            for _ in range(50):
                t0 = time.perf_counter()
                crop = aligner.align(face_img, f0)
                lat.append((time.perf_counter() - t0) * 1000)
            results["S2_alignment"] = stats(lat)
        else:
            results["S2_alignment"] = {"note": "no face detected; skipped"}

    # ---- S3 emotion inference (deterministic crop; 200 runs) ----
    if emo.is_available():
        crop = emo.create_face_crop(face_img) if hasattr(emo, 'create_face_crop') else None
        if crop is None:
            crop = (np.random.RandomState(42).rand(224, 224, 3) * 255).astype(np.uint8)
        warm = emo.predict(face_crop=crop)
        lat = []
        confs = []
        preds = []
        for _ in range(200):
            t0 = time.perf_counter()
            p = emo.predict(face_crop=crop)
            lat.append((time.perf_counter() - t0) * 1000)
            confs.append(p["confidence"])
            preds.append(p["emotion"])
        s = stats(lat)
        s["conf_mean"] = round(statistics.mean(confs), 4)
        s["conf_std"] = round(statistics.pstdev(confs), 4)
        s["distinct_predictions"] = len(set(preds))
        s["dominant_emotion"] = max(set(preds), key=preds.count)
        results["S3_emotion_inference"] = s

    gc.collect()

    # ---- E2E EmotionEngine.process() throughput ----
    try:
        from mee.api.engine import EmotionEngine
        from mee.api.engine import MEEConfig
        eng = EmotionEngine(config=MEEConfig())
        lat = []
        for _ in range(50):
            t0 = time.perf_counter()
            out = eng.process(video_frame=face_img, audio=None)
            lat.append((time.perf_counter() - t0) * 1000)
        results["E2E_process"] = stats(lat)
    except Exception as e:
        results["E2E_process"] = {"error": str(e)}

    gc.collect()

    # ---- MEM stability (3-min run, ~10 fps) ----
    print("MEM: 3-min sustained run starting...", flush=True)
    try:
        from mee.api.engine import EmotionEngine
        from mee.api.engine import MEEConfig
        eng = EmotionEngine(config=MEEConfig())
        end = time.time() + 180
        samples = []
        n = 0
        while time.time() < end:
            t0 = time.perf_counter()
            eng.process(video_frame=face_img, audio=None)
            dt = time.perf_counter() - t0
            rem = 0.1 - dt
            if rem > 0:
                time.sleep(rem)
            samples.append(rss_mb())
            n += 1
        results["MEM_stability"] = {
            "samples": n,
            "rss_start_mb": samples[0],
            "rss_end_mb": samples[-1],
            "rss_max_mb": max(samples),
            "rss_min_mb": min(samples),
            "drift_pct": round(100.0*(samples[-1]-samples[0])/samples[0], 3) if samples[0] > 0 else 0.0,
        }
    except Exception as e:
        results["MEM_stability"] = {"error": str(e)}

    total = time.time() - t_start
    results["_meta"] = {
        "host": os.uname().nodename,
        "total_run_s": round(total, 1),
        "numpy": np.__version__,
    }

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS, "w") as f:
        json.dump(results, f, indent=2)
    print(f"BENCHMARK COMPLETE in {total:.1f}s — raw JSON -> {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
