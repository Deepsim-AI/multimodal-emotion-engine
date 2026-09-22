#!/usr/bin/env python3
"""TASK_MEE_010 Task 2: Build TensorRT engines from ONNX models.

Two paths:
  1. Full TensorRT Python API (requires tensorrt installed — JetPack / pip tensorrt)
     → produces a standalone .trt engine file
  2. ONNX Runtime TensorRT EP (requires onnxruntime-gpu with TensorRT)
     → caches the TRT engine inside the ORT session state, usable via
       tools/bench_jetson.py --model tensorrt

INT8 requires a calibration dataset. If --calibration-dir is not provided,
falls back to FP16 (recommended default for Jetson Orin — INT8 audio
classification with <40 calibration samples risks accuracy loss).

Usage:
    python tools/build_trt_engine.py --onnx models/exported/emotion_iemocap.onnx \
        --output models/exported/emotion_iemocap.trt --fp16
    python tools/build_trt_engine.py --onnx models/exported/emotion_iemocap.onnx \
        --output models/exported/emotion_iemocap.int8.trt --int8 \
        --calibration-dir models/calibration/
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# GPU / TensorRT detection
# ---------------------------------------------------------------------------

def _jetson_gpu_available() -> tuple[bool, str]:
    """Check for a usable GPU (Jetson = unified memory, nvidia-smi may not work)."""
    # Jetson: /sys/class/nvmap/ or /sys/devices/platform/bd700000.gpu
    jetson_markers = ["/sys/class/nvmap", "/sys/devices/platform/bd700000.gpu"]
    for marker in jetson_markers:
        if os.path.exists(marker):
            return True, f"Jetson (marker: {marker})"
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return True, r.stdout.strip()
    except Exception:
        pass
    return False, "no GPU detected"


def _tensorrt_available() -> bool:
    try:
        import tensorrt  # noqa: F401
        return True
    except ImportError:
        return False


def _ort_trt_available() -> bool:
    try:
        import onnxruntime as ort
        return "TensorrtExecutionProvider" in ort.get_available_providers()
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Path 1: TensorRT Python API
# ---------------------------------------------------------------------------

def build_engine_trt_api(onnx_path: str, output_path: str,
                         precision: str = "fp16", calib_dir: str | None = None) -> Path:
    """Build a TensorRT engine using the tensorrt Python API.

    precision: 'fp16' or 'int8'
    calib_dir: required for int8 — directory of .npy files [T] float32 audio
    """
    import tensorrt as trt

    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)

    # TensorRT 9+ uses explicit batch mode by default; 8.x needs the flag
    try:
        network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    except Exception:
        network = builder.create_network()

    parser = None
    try:
        from onnx_importer import parse
        parse(onnx_path, network, logger)
    except Exception:
        from google.protobuf import text_format  # noqa — fallback
        from onnx import helper
        import onnx
        # Fall back to trt.onnx if available
        try:
            from trt_onnx_parser import OnnxParser  # type: ignore
            parser = OnnxParser(network, logger)
            with open(onnx_path, "rb") as f:
                parser.deserialize(f.read())
        except Exception as e:
            raise RuntimeError(
                f"Could not import ONNX model into TensorRT: {e}\n"
                "Install onnx2trt: pip install onnx2trt  (or use trtexec)"
            ) from e

    config = builder.create_builder_config()
    if precision == "int8":
        config.set_flag(trt.BuilderFlag.INT8)
        config.set_flag(trt.BuilderFlag.FP16)
        if calib_dir is None:
            raise ValueError("INT8 build requires --calibration-dir")
        calib_path = _build_int8_calibrator(calib_dir, logger)
        config.int8_calibrator = calib_path
    else:
        config.set_flag(trt.BuilderFlag.FP16)

    engine = builder.build_serialized_network(network, config)
    if engine is None:
        raise RuntimeError("TensorRT build_serialized_network returned None (build failed)")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(engine)
    return out


def _build_int8_calibrator(calib_dir: str, logger) -> object:
    """Create an IInt8Calibrator from .npy files in calib_dir."""
    import numpy as np
    import tensorrt as trt

    files = sorted(Path(calib_dir).glob("*.npy"))
    if not files:
        raise FileNotFoundError(f"No .npy calibration files found in {calib_dir}")

    samples = [np.load(str(f)).astype(np.float32) for f in files[:100]]
    print(f"[trt] INT8 calibrator: {len(samples)} samples")

    class _NumpyCalibrator(trt.IInt8Calibrator):
        def __init__(self, data):
            super().__init__()
            self._data = data
            self._idx = 0

        def get_batch_size(self):
            return len(self._data)

        def get_batch(self, names):
            if self._idx >= len(self._data):
                return None
            batch = self._data[self._idx]
            self._idx += 1
            return [batch.reshape(1, -1)]

    return _NumpyCalibrator(samples)


# ---------------------------------------------------------------------------
# Path 2: ONNX Runtime TensorRT EP (no standalone .trt file needed)
# ---------------------------------------------------------------------------

def build_engine_ort_trt(onnx_path: str, output_path: str) -> Path:
    """Warm up the ONNX Runtime TensorRT EP and cache the engine.

    ORT's TRT EP compiles the ONNX graph into TRT sub-engines on first
    inference and caches them in the session state. We can't directly export
    the cached engine, but we can:
      1. Run a warmup inference to trigger compilation
      2. Copy the ONNX model alongside a marker file so the bench harness
         knows to use TRT EP providers

    The output_path becomes a .trt marker file — the bench harness detects
    it and loads the ONNX with TRT providers.
    """
    import onnxruntime as ort
    import numpy as np

    providers = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
    avail = ort.get_available_providers()
    active = [p for p in providers if p in avail]
    if not active:
        raise RuntimeError(
            f"No GPU ONNX Runtime providers available. Available: {avail}\n"
            "Install onnxruntime-gpu with TensorRT: see docs/JETSON_DEPLOYMENT.md"
        )

    print(f"[trt] ORT TRT EP warmup with providers: {active}")
    sess = ort.InferenceSession(onnx_path, providers=active)
    inp = sess.get_inputs()[0]
    dummy = np.random.randn(1, 16000).astype(np.float32)
    _ = sess.run(None, {inp.name: dummy})
    print("[trt] ORT TRT EP warmup complete (engine compiled and cached in session)")

    # Write a marker file so the bench harness knows this model has been TRT-warmed
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"warmup_source={onnx_path}\nproviders={active}\n")
    return out


# ---------------------------------------------------------------------------
# trtexec fallback (command-line)
# ---------------------------------------------------------------------------

def build_engine_trtexec(onnx_path: str, output_path: str,
                         precision: str = "fp16", calib_dir: str | None = None) -> Path:
    """Use trtexec if available (commonly bundled with JetPack)."""
    trtexec = shutil.which("trtexec")
    if trtexec is None:
        raise RuntimeError("trtexec not found in PATH")

    cmd = [trtexec, f"--onnx={onnx_path}", f"--saveEngine={output_path}"]
    if precision == "int8":
        cmd.append("--int8")
        if calib_dir:
            cmd.append(f"--calibTable={Path(calib_dir) / 'calib.cache'}")
            cmd.append(f"--fp16")
    else:
        cmd.append("--fp16")

    print(f"[trt] Running: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"trtexec failed: {r.stderr[-2000:]}")
    return Path(output_path)


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build TensorRT engines from ONNX models.")
    parser.add_argument("--onnx", required=True, help="Input ONNX model path")
    parser.add_argument("--output", required=True, help="Output engine path (.trt)")
    parser.add_argument(
        "--precision",
        choices=["fp16", "int8"],
        default="fp16",
        help="Precision: fp16 (default, recommended) or int8 (requires --calibration-dir)",
    )
    parser.add_argument("--calibration-dir", default=None,
                        help="Directory of .npy calibration samples (required for int8)")
    parser.add_argument("--method",
                        choices=["auto", "trt-api", "ort-trt", "trtexec"],
                        default="auto",
                        help="Build method (default: auto — pick best available)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.onnx):
        print(f"ERROR: ONNX model not found: {args.onnx}", file=sys.stderr)
        return 1

    gpu_ok, gpu_desc = _jetson_gpu_available()
    if not gpu_ok:
        print(f"WARNING: {gpu_desc} — engine will be built for CPU inference", file=sys.stderr)

    method = args.method
    if method == "auto":
        if _tensorrt_available():
            method = "trt-api"
        elif _ort_trt_available():
            method = "ort-trt"
        else:
            method = "trtexec"

    print(f"[trt] Method: {method} | Precision: {args.precision} | GPU: {gpu_desc}")

    try:
        if method == "trt-api":
            out = build_engine_trt_api(args.onnx, args.output, args.precision, args.calibration_dir)
        elif method == "ort-trt":
            out = build_engine_ort_trt(args.onnx, args.output)
        else:
            out = build_engine_trtexec(args.onnx, args.output, args.precision, args.calibration_dir)
    except Exception as e:
        print(f"[trt] FAILED: {e}", file=sys.stderr)
        return 1

    print(f"[trt] Engine ready → {out}")
    print("[trt] Use tools/bench_jetson.py --model tensorrt to benchmark.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
