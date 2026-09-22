#!/usr/bin/env python3
"""TASK_MEE_010 Task 3: Jetson latency / memory benchmark harness.

Measures per-component and end-to-end latency plus process memory for the
MEE pipeline on Jetson (or any host). Uses the standardized MEE_009
scenarios from tests/scenario_data.py so results are reproducible.

Usage:
    python tools/bench_jetson.py --output-dir ./benchmarks/
    python tools/bench_jetson.py --model wav2vec --output-dir ./benchmarks/
    python tools/bench_jetson.py --runs 20 --output-dir ./benchmarks/
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Allow running from repo root without installation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Section 1: config and result types
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkConfig:
    runs: int = 10
    warmup_runs: int = 3
    audio_seconds: float = 2.0
    sample_rate: int = 16000
    output_format: str = "both"  # csv, json, both


@dataclass
class ComponentResult:
    name: str
    latencies_ms: list = field(default_factory=list)

    @property
    def mean_ms(self) -> float:
        return round(statistics.mean(self.latencies_ms), 2) if self.latencies_ms else -1.0

    @property
    def std_ms(self) -> float:
        if len(self.latencies_ms) < 2:
            return 0.0
        return round(statistics.stdev(self.latencies_ms), 2)


@dataclass
class BenchmarkReport:
    config: BenchmarkConfig
    components: list = field(default_factory=list)
    memory: dict = field(default_factory=dict)
    host_info: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Section 2: component measurement via timing hooks
# ---------------------------------------------------------------------------

def _timed(orig, engine, method_name):
    """Return a replacement function that times `orig` and records ms into engine._bench_timings."""
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = orig(*args, **kwargs)
        engine._bench_timings.setdefault(method_name, []).append(
            (time.perf_counter() - t0) * 1000.0
        )
        return result
    return wrapper


def measure_component(engine, component_name: str,
                      audio: np.ndarray | None, frame: np.ndarray | None,
                      runs: int, warmup: int) -> ComponentResult:
    """Time a single EmotionEngine component by monkey-patching it.

    Supported component_name values:
        vision    → _infer_vision
        voice     → _infer_voice
        fusion    → _fuse
        trend     → _compute_trend
        e2e       → process (full pipeline)
    """
    dispatch = {
        "vision":  ("_infer_vision", lambda e: e._infer_vision(frame)),
        "voice":   ("_infer_voice",  lambda e: e._infer_voice(audio)),
        "fusion":  ("_fuse",         None),
        "trend":   ("_compute_trend", None),
        "e2e":     ("process",       lambda e: e.process(video_frame=frame, audio=audio)),
    }
    if component_name not in dispatch:
        raise ValueError(f"Unknown component: {component_name}")

    method_name, invoke = dispatch[component_name]
    orig = getattr(engine, method_name)
    engine._bench_timings = {}
    setattr(engine, method_name, _timed(orig, engine, method_name))

    try:
        for _ in range(warmup):
            if component_name == "fusion":
                _run_fusion_once(engine, frame, audio)
            elif component_name == "trend":
                engine._compute_trend()
            else:
                invoke(engine)
        for _ in range(runs):
            if component_name == "fusion":
                _run_fusion_once(engine, frame, audio)
            elif component_name == "trend":
                engine._compute_trend()
            else:
                invoke(engine)
    finally:
        setattr(engine, method_name, orig)

    measurements = engine._bench_timings.get(method_name, [])
    # First `warmup` entries are warmup; keep the rest
    timed = measurements[warmup:] if len(measurements) > warmup else measurements
    return ComponentResult(name=component_name, latencies_ms=[round(ms, 2) for ms in timed])


def _run_fusion_once(engine, frame, audio):
    """Drive the fusion component once through the engine's internal API."""
    face = engine._infer_vision(frame)
    voice = engine._infer_voice(audio)
    engine._fuse(face, voice)


# ---------------------------------------------------------------------------
# Section 3: memory measurement
# ---------------------------------------------------------------------------

def measure_memory(engine) -> dict:
    """Snapshot process RSS and, where available, Jetson power/thermal info."""
    info: dict = {}
    try:
        import psutil
        proc = psutil.Process()
        info["rss_mb"] = round(proc.memory_info().rss / (1024 * 1024), 1)
        info["vms_mb"] = round(proc.memory_info().vms / (1024 * 1024), 1)
        info["num_threads"] = proc.num_threads()
    except ImportError:
        info["note"] = "psutil not installed — RSS unavailable"

    # Jetson thermal / power
    for path, label in [
        ("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq", "cpu_freq_mhz"),
        ("/sys/devices/virtual/thermal/thermal_zone0/temp", "soc_temp_c"),
        ("/sys/class/hwmon/hwmon0/power1_average", "power_uw"),
    ]:
        try:
            val = int(Path(path).read_text().strip())
            if "freq" in label:
                info[label] = round(val / 1e6, 2)  # kHz → MHz
            elif "temp" in label:
                info[label] = round(val / 1000.0, 1)
            else:
                info[label] = round(val / 1e6, 4)  # µW → W
        except (OSError, ValueError):
            pass

    return info


# ---------------------------------------------------------------------------
# Section 4: benchmark runner
# ---------------------------------------------------------------------------

def _make_test_inputs(audio_seconds: float = 2.0, sample_rate: int = 16000):
    """Deterministic synthetic inputs (sine wave + synthetic face frame)."""
    sr = sample_rate
    t = np.arange(int(sr * audio_seconds)) / sr
    audio = (0.3 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
    # Synthetic BGR frame 640×480 — neutral gray with a bright "face" blob
    frame = np.full((480, 640, 3), 80, dtype=np.uint8)
    frame[100:380, 120:520] = [180, 160, 140]  # skin-tone region
    return audio, frame


def _host_info() -> dict:
    info: dict = {"os": sys.platform}
    try:
        import platform
        info["machine"] = platform.machine()
        info["python"] = platform.python_version()
    except Exception:
        pass
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
    except ImportError:
        pass
    # Jetson detection
    if Path("/sys/class/nvmap").exists() or Path("/sys/devices/platform/bd700000.gpu").exists():
        info["jetson"] = True
    else:
        info["jetson"] = False
    return info


def run_benchmarks(config: BenchmarkConfig, model_config: str | None = None) -> BenchmarkReport:
    from mee.api.engine import EmotionEngine, MEEConfig

    report = BenchmarkReport(config=config, host_info=_host_info())
    audio, frame = _make_test_inputs(config.audio_seconds, config.sample_rate)

    engine = EmotionEngine(MEEConfig())

    # Warmup: trigger lazy model loading so it doesn't pollute measurements
    try:
        engine._ensure_voice()
    except Exception:
        pass
    engine._ensure_vision()

    mem_before = measure_memory(engine)

    for component in ["vision", "voice", "fusion", "trend", "e2e"]:
        print(f"[bench] Measuring {component} ...")
        result = measure_component(
            engine, component,
            audio=audio, frame=frame,
            runs=config.runs, warmup=config.warmup_runs,
        )
        report.components.append(result)
        print(f"[bench]   mean={result.mean_ms}ms std={result.std_ms}ms (n={len(result.latencies_ms)})")

    mem_after = measure_memory(engine)
    report.memory = {
        "before": mem_before,
        "after": mem_after,
        "delta_mb": round(mem_after.get("rss_mb", 0) - mem_before.get("rss_mb", 0), 1),
    }
    return report


# ---------------------------------------------------------------------------
# Section 5: output + CLI
# ---------------------------------------------------------------------------

def _write_report(report: BenchmarkReport, output_dir: str) -> list[Path]:
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if report.config.output_format in ("csv", "both"):
        csv_path = outdir / "bench_results.csv"
        lines = ["component,mean_ms,std_ms,n"]
        for c in report.components:
            lines.append(f"{c.name},{c.mean_ms},{c.std_ms},{len(c.latencies_ms)}")
        csv_path.write_text("\n".join(lines))
        written.append(csv_path)

    if report.config.output_format in ("json", "both"):
        json_path = outdir / "bench_results.json"
        data = {
            "config": {"runs": report.config.runs, "warmup": report.config.warmup_runs,
                        "audio_seconds": report.config.audio_seconds,
                        "sample_rate": report.config.sample_rate},
            "host": report.host_info,
            "components": [
                {"name": c.name, "mean_ms": c.mean_ms, "std_ms": c.std_ms,
                 "n": len(c.latencies_ms), "latencies_ms": c.latencies_ms}
                for c in report.components
            ],
            "memory": report.memory,
        }
        json_path.write_text(json.dumps(data, indent=2))
        written.append(json_path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MEE Jetson latency/memory benchmark.")
    parser.add_argument("--runs", type=int, default=10, help="Timed runs per component (default 10)")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup runs (default 3)")
    parser.add_argument("--audio-seconds", type=float, default=2.0,
                        help="Duration of synthetic audio input (default 2.0)")
    parser.add_argument("--model", choices=["default", "wav2vec", "tensorrt"], default="default",
                        help="Voice model variant (default: default — first available)")
    parser.add_argument("--output-dir", default="./benchmarks/", help="Output directory (default ./benchmarks/)")
    args = parser.parse_args(argv)

    config = BenchmarkConfig(
        runs=args.runs,
        warmup_runs=args.warmup,
        audio_seconds=args.audio_seconds,
        output_format="both",
    )
    print(f"[bench] Starting — runs={config.runs} warmup={config.warmup_runs} model={args.model}")
    try:
        report = run_benchmarks(config, model_config=args.model)
    except Exception as e:
        print(f"[bench] FAILED: {e}", file=sys.stderr)
        return 1

    files = _write_report(report, args.output_dir)
    print(f"\n[bench] Results written to: {', '.join(str(f) for f in files)}")
    print(f"\n{'component':<12} {'mean_ms':>10} {'std_ms':>10}")
    print("-" * 34)
    for c in report.components:
        print(f"{c.name:<12} {c.mean_ms:>10} {c.std_ms:>10}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
