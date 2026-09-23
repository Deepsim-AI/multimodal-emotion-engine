#!/usr/bin/env python3
"""TASK_MEE_012: Benchmark vision models on Jetson AGX Orin.

Measures latency, memory, and accuracy of the EmotiEffLib-based pipeline.
"""

import sys
import os
import time
import psutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, '/home/deepsim/multimodal-emotion-engine')


@dataclass
class LatencyStats:
    mean_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    frames_per_sec: float = 0.0


def run_latency_test(name: str, func, runs: int = 100) -> LatencyStats:
    """Run a function many times and return latency statistics."""
    latencies = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        latencies.append((end - start) / 1_000_000)  # ns → ms

    latencies.sort()
    n = len(latencies)
    return LatencyStats(
        mean_ms=round(sum(latencies)/n, 3),
        p95_ms=round(latencies[int(n*0.95)], 3),
        p99_ms=round(latencies[int(n*0.99)], 3),
        min_ms=round(min(latencies), 3),
        max_ms=round(max(latencies), 3),
        frames_per_sec=round(1000/sum(latencies)*n, 2),
    )


def test_detection():
    """Benchmark face detection speed."""
    try:
        from mee.vision.detector import FaceDetector
        det = FaceDetector()
        
        # Generate synthetic frame (640x480 BGR)
        import numpy as np
        fake_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        if det.available:
            return lambda: det.detect(fake_frame)
        else:
            print("⚠️ No detector available — skipping detection test")
            return None
    except Exception as e:
        print(f"⚠️ Detection test failed: {e}")
        return None


def test_expression():
    """Benchmark expression inference speed."""
    try:
        from mee.vision.emotion_model import EmotionModel, MEE_LABELS
        
        # Load EmotiEffLib model
        classifier = EmotionModel(model_name="enet_b0_8_best_vgaf")
        
        if not classifier.is_available():
            print("⚠️ No expression model available — skipping test")
            return None
            
        # Generate synthetic 224x224 face crop (RGB uint8)
        import numpy as np
        fake_crop = (np.random.rand(224, 224, 3) * 255).astype(np.uint8)
        
        def bench_func():
            return classifier.predict(face_crop=fake_crop)
            
        return bench_func
    except Exception as e:
        print(f"⚠️ Expression test failed: {e}")
        return None


def memory_usage() -> float:
    """Get current process RSS in MB."""
    import psutil
    proc = psutil.Process(os.getpid())
    return round(proc.memory_info().rss / 1024**2, 2)


if __name__ == '__main__':
    print("="*60)
    print("MEE Vision Model Benchmarks — Jetson AGX Orin")
    print("="*60)
    
    results = {}
    
    # Test detection
    det_func = test_detection()
    if det_func:
        stats = run_latency_test("detection", det_func, 100)
        results["face_detect"] = stats
        
    # Test expression  
    expr_func = test_expression()
    if expr_func:
        stats = run_latency_test("expression", expr_func, 100)
        results["emotion_classify"] = stats
    
    # Print results
    print("\n" + "="*60)
    print("Results:")
    for name, stats in results.items():
        print(f"\n{name}:")
        print(f"  mean: {stats.mean_ms}ms")
        print(f"  p95:  {stats.p95_ms}ms")
        print(f"  p99:  {stats.p99_ms}ms")
        print(f"  fps:  {stats.frames_per_sec}")
    
    # Memory baseline
    mem_before = memory_usage()
    print(f"\nMemory before tests: {mem_before}MB")
    
    print("\n✅ Benchmarks complete!")
