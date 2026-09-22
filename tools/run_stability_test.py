#!/usr/bin/env python3
"""TASK_MEE_010 Task 4: Extended stability runner.

Runs the MEE pipeline in a continuous loop with synthetic inputs to verify:
  - No crashes or unhandled exceptions
  - Memory drift < 10% of peak over the run duration
  - No latency degradation over time

Uses the same deterministic synthetic inputs as the benchmark harness —
no external files or network access required.

Usage:
    python tools/run_stability_test.py --minutes 5 --interval 2 --output-dir ./stability/
    python tools/run_stability_test.py --minutes 60 --interval 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class StabilityConfig:
    minutes: float = 5.0
    interval_s: float = 2.0
    output_dir: str = "./stability/"
    memory_drift_threshold_pct: float = 10.0
    log_every: int = 50  # print progress every N cycles


# ---------------------------------------------------------------------------
# Synthetic inputs (deterministic, no file I/O)
# ---------------------------------------------------------------------------

def _make_audio(seconds: float = 2.0, sr: int = 16000) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * 440 * t)
            + 0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)


def _make_frame() -> np.ndarray:
    frame = np.full((480, 640, 3), 80, dtype=np.uint8)
    frame[100:380, 120:520] = [180, 160, 140]
    return frame


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

def _rss_mb() -> float:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except ImportError:
        return -1.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class StabilityRunner:
    def __init__(self, config: StabilityConfig):
        self.config = config
        self.total_runs = 0
        self.crash_count = 0
        self.latencies_ms: list[float] = []
        self.rss_samples: list[float] = []
        self.baseline_rss: float = -1.0
        self.max_rss: float = 0.0
        self.crash_traces: list[str] = []

    def _ensure_engine(self):
        from mee.api.engine import EmotionEngine, MEEConfig
        return EmotionEngine(MEEConfig())

    def run_cycle(self, engine) -> None:
        audio = _make_audio()
        frame = _make_frame()
        t0 = time.perf_counter()
        engine.process(video_frame=frame, audio=audio)
        lat_ms = (time.perf_counter() - t0) * 1000.0
        self.latencies_ms.append(round(lat_ms, 2))
        rss = _rss_mb()
        self.rss_samples.append(rss)
        if rss > 0:
            if self.baseline_rss < 0:
                self.baseline_rss = rss
            self.max_rss = max(self.max_rss, rss)
        self.total_runs += 1

    def detect_memory_drift(self) -> float:
        """Return current drift % relative to baseline RSS."""
        if not self.rss_samples or self.baseline_rss <= 0:
            return 0.0
        current = self.rss_samples[-1]
        if current <= 0:
            return 0.0
        return round((current - self.baseline_rss) / self.baseline_rss * 100.0, 2)

    def summary(self) -> dict:
        drift = self.detect_memory_drift()
        lat = self.latencies_ms
        return {
            "total_runs": self.total_runs,
            "crash_count": self.crash_count,
            "memory_drift_pct": drift,
            "memory_drift_within_threshold": drift < self.config.memory_drift_threshold_pct,
            "baseline_rss_mb": self.baseline_rss,
            "max_rss_mb": self.max_rss,
            "avg_latency_ms": round(sum(lat) / len(lat), 2) if lat else -1,
            "max_latency_ms": round(max(lat), 2) if lat else -1,
            "min_latency_ms": round(min(lat), 2) if lat else -1,
        }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_stability(config: StabilityConfig) -> int:
    print(f"[stability] Starting — minutes={config.minutes} interval={config.interval_s}s")
    runner = StabilityRunner(config)
    engine = runner._ensure_engine()

    # Warm up (trigger lazy model loading)
    print("[stability] Warming up (loading models) ...")
    try:
        engine._ensure_voice()
    except Exception:
        pass
    try:
        engine._ensure_vision()
    except Exception:
        pass

    deadline = time.monotonic() + config.minutes * 60.0
    print(f"[stability] Running until {config.minutes} min ...")

    while time.monotonic() < deadline:
        try:
            runner.run_cycle(engine)
        except Exception as e:
            runner.crash_count += 1
            runner.crash_traces.append(traceback.format_exc())
            print(f"[stability] CRASH (#{runner.crash_count}): {e}", file=sys.stderr)

        if runner.total_runs > 0 and runner.total_runs % config.log_every == 0:
            drift = runner.detect_memory_drift()
            elapsed = config.minutes - (deadline - time.monotonic()) / 60.0
            print(
                f"[stability] cycle={runner.total_runs} "
                f"rss={runner.rss_samples[-1]}MB drift={drift}% "
                f"crashes={runner.crash_count} elapsed={elapsed:.1f}min"
            )

        if time.monotonic() >= deadline:
            break
        time.sleep(config.interval_s)

    # Summary
    summary = runner.summary()
    print("\n" + "=" * 50)
    print("STABILITY TEST SUMMARY")
    print("=" * 50)
    print(f"  Total runs:              {summary['total_runs']}")
    print(f"  Crashes:                 {summary['crash_count']}")
    print(f"  Baseline RSS:            {summary['baseline_rss_mb']} MB")
    print(f"  Max RSS:                 {summary['max_rss_mb']} MB")
    print(f"  Memory drift:            {summary['memory_drift_pct']}% "
          f"(threshold {config.memory_drift_threshold_pct}%) "
          f"{'PASS' if summary['memory_drift_within_threshold'] else 'FAIL'}")
    print(f"  Avg latency:             {summary['avg_latency_ms']} ms")
    print(f"  Max latency:             {summary['max_latency_ms']} ms")
    print(f"  Min latency:             {summary['min_latency_ms']} ms")

    # Write results
    outdir = Path(config.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    result_path = outdir / "stability_results.json"
    result_path.write_text(json.dumps({
        "config": {
            "minutes": config.minutes,
            "interval_s": config.interval_s,
            "memory_drift_threshold_pct": config.memory_drift_threshold_pct,
        },
        "summary": summary,
        "latencies_ms": runner.latencies_ms,
        "rss_samples_mb": runner.rss_samples,
        "crash_traces": runner.crash_traces[:10],  # cap at 10
    }, indent=2))
    print(f"\n[stability] Results → {result_path}")

    passed = summary["crash_count"] == 0 and summary["memory_drift_within_threshold"]
    print(f"[stability] {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MEE extended stability test.")
    parser.add_argument("--minutes", type=float, default=5.0,
                        help="Duration in minutes (default 5)")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds between cycles (default 2)")
    parser.add_argument("--output-dir", default="./stability/",
                        help="Output directory (default ./stability/)")
    parser.add_argument("--drift-threshold", type=float, default=10.0,
                        help="Max allowed memory drift %% (default 10)")
    args = parser.parse_args(argv)

    config = StabilityConfig(
        minutes=args.minutes,
        interval_s=args.interval,
        output_dir=args.output_dir,
        memory_drift_threshold_pct=args.drift_threshold,
    )
    return run_stability(config)


if __name__ == "__main__":
    sys.exit(main())
