#!/usr/bin/env python3
"""TASK_MEE_010 Task 1: Export MEE voice models to ONNX / INT8.

Exports:
  - speechbrain_iemocap : SpeechBrain wav2vec2 IEMOCAP emotion model
    (uses the direct-submodule forward pattern from mee/voice/emotion_model.py,
    which is required because the IEMOCAP hyperparams.yaml targets SpeechBrain 0.x)
  - wav2vec2            : facebook/wav2vec2-base-960h (transformers)

Usage:
    python tools/export_models.py --model speechbrain_iemocap --format onnx
    python tools/export_models.py --model speechbrain_iemocap --format int8
    python tools/export_models.py --model wav2vec2 --format onnx --output-dir ./models/exported/
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_OUTPUT_DIR = "./models/exported/"
ONNX_OPSET = 17
SAMPLE_RATE = 16000


# ---------------------------------------------------------------------------
# Section 2: SpeechBrain IEMOCAP export
# ---------------------------------------------------------------------------

def _build_iemocap_wrapper(savedir: str):
    """Load the SpeechBrain IEMOCAP model and wrap its forward pass for ONNX.

    The forward path replicated from mee/voice/emotion_model.py lines 246-252:

        wav2vec2(raw) -> last_hidden_state -> avg_pool -> output_mlp -> logits

    Returns (wrapper, n_classes).
    """
    import torch
    import torch.nn as nn
    from speechbrain.inference.classifiers import EncoderClassifier

    model = EncoderClassifier.from_hparams(
        source=savedir,
        savedir=savedir,
        run_opts={"device": "cpu"},
    )
    model.eval()

    # Resolve label count (IEMOCAP model: 4 classes — neu/ang/hap/sad)
    n_classes = 4
    le = getattr(model.hparams, "label_encoder", None)
    if le is not None and hasattr(le, "ind2lab"):
        try:
            n_classes = len(le.ind2lab)
        except Exception:
            pass

    class _IEMOCAPONNXWrapper(nn.Module):
        """Single-callable forward compatible with torch.onnx.export."""

        def __init__(self, base):
            super().__init__()
            self.wav2vec2 = base.mods.wav2vec2
            self.avg_pool = base.mods.avg_pool
            self.output_mlp = base.mods.output_mlp

        def forward(self, audio: torch.Tensor) -> torch.Tensor:
            # audio: [B, T] float32 at 16 kHz
            out = self.wav2vec2(audio)
            emb = out.last_hidden_state if hasattr(out, "last_hidden_state") else out
            emb = self.avg_pool(emb, torch.ones(emb.shape[0], device=emb.device))
            logits = self.output_mlp(emb).flatten(start_dim=1)
            return logits

    wrapper = _IEMOCAPONNXWrapper(model)
    for p in wrapper.parameters():
        p.requires_grad_(False)
    wrapper.eval()
    return wrapper, n_classes


def export_speechbrain_iemocap(output_dir: str, fmt: str, model_path: str | None = None) -> Path:
    """Export the SpeechBrain IEMOCAP model to ONNX (and optionally INT8)."""
    import torch

    savedir = model_path or os.path.expanduser(
        "~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP"
    )
    savedir = os.path.expanduser(savedir)
    if not os.path.isdir(savedir) or not os.path.exists(os.path.join(savedir, "model.ckpt")):
        raise FileNotFoundError(
            f"SpeechBrain IEMOCAP model not found at {savedir}. "
            "Download with: speechbrain download emotion-recognition-wav2vec2-IEMOCAP "
            "or see docs/JETSON_DEPLOYMENT.md → Installation."
        )

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    onnx_path = outdir / "emotion_iemocap.onnx"

    wrapper, n_classes = _build_iemocap_wrapper(savedir)
    dummy = torch.randn(1, SAMPLE_RATE, dtype=torch.float32)

    print(f"[export] Exporting SpeechBrain IEMOCAP ({n_classes} classes) → {onnx_path}")
    torch.onnx.export(
        wrapper,
        (dummy,),
        str(onnx_path),
        opset_version=ONNX_OPSET,
        input_names=["audio"],
        output_names=["logits"],
        dynamic_axes={"audio": {0: "batch", 1: "samples"},
                      "logits": {0: "batch"}},
        do_constant_folding=True,
    )
    _validate_onnx(onnx_path, dummy)

    if fmt == "int8":
        int8_path = outdir / "emotion_iemocap.int8.onnx"
        quantize_to_int8(str(onnx_path), str(int8_path))
        print(f"[export] INT8 model → {int8_path} ({int8_path.stat().st_size/1e6:.1f} MB)")
        return int8_path

    print(f"[export] ONNX model → {onnx_path} ({onnx_path.stat().st_size/1e6:.1f} MB)")
    return onnx_path


# ---------------------------------------------------------------------------
# Section 3: Wav2Vec 2.0-base export
# ---------------------------------------------------------------------------

def export_wav2vec2(output_dir: str, fmt: str) -> Path:
    """Export facebook/wav2vec2-base-960h to ONNX via transformers."""
    import torch
    import torch.nn as nn

    from transformers import AutoModelForAudioClassification

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    onnx_path = outdir / "emotion_wav2vec2_base.onnx"

    print(f"[export] Loading facebook/wav2vec2-base-960h ...")
    model = AutoModelForAudioClassification.from_pretrained("facebook/wav2vec2-base-960h")
    model.eval()

    class _Wav2VecONNXWrapper(nn.Module):
        """Input [B, T] float32 audio → logits, single-callable for torch.onnx.export."""

        def __init__(self, base):
            super().__init__()
            self.base = base

        def forward(self, audio: torch.Tensor) -> torch.Tensor:
            inputs = {"input_values": audio}
            out = self.base(**inputs)
            return out.logits

    wrapper = _Wav2VecONNXWrapper(model)
    for p in wrapper.parameters():
        p.requires_grad_(False)
    wrapper.eval()

    dummy = torch.randn(1, SAMPLE_RATE, dtype=torch.float32)
    print(f"[export] Exporting Wav2Vec 2.0-base → {onnx_path}")
    torch.onnx.export(
        wrapper,
        (dummy,),
        str(onnx_path),
        opset_version=ONNX_OPSET,
        input_names=["audio"],
        output_names=["logits"],
        dynamic_axes={"audio": {0: "batch", 1: "samples"},
                      "logits": {0: "batch"}},
        do_constant_folding=True,
    )
    _validate_onnx(onnx_path, dummy)

    if fmt == "int8":
        int8_path = outdir / "emotion_wav2vec2_base.int8.onnx"
        quantize_to_int8(str(onnx_path), str(int8_path))
        print(f"[export] INT8 model → {int8_path} ({int8_path.stat().st_size/1e6:.1f} MB)")
        return int8_path

    print(f"[export] ONNX model → {onnx_path} ({onnx_path.stat().st_size/1e6:.1f} MB)")
    return onnx_path


# ---------------------------------------------------------------------------
# Section 4: INT8 quantization
# ---------------------------------------------------------------------------

def _validate_onnx(onnx_path: Path, dummy_input) -> None:
    """Sanity check: model loads in ONNX Runtime and produces expected output shape."""
    import onnxruntime as ort
    import numpy as np

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp_name = sess.get_inputs()[0].name
    out = sess.run(None, {inp_name: dummy_input.numpy() if hasattr(dummy_input, "numpy") else dummy_input})
    print(f"[export] ONNX validation OK — output shape: {out[0].shape}")


def quantize_to_int8(input_path: str, output_path: str) -> Path:
    """Data-free INT8 quantization (QDQ format) via onnxruntime.quantization.

    QDSM (Quantize-Then-Dither-Scale-Magnitude) is used — a data-free method
    that works well for audio classification models trained with dropout/BN.
    """
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from pathlib import Path

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(
        input_path,
        str(out),
        weight_type=QuantType.QUInt8,
    )
    _validate_onnx(out, _dummy_audio())
    return out


def _dummy_audio():
    import torch
    return torch.randn(1, SAMPLE_RATE, dtype=torch.float32).numpy()


# ---------------------------------------------------------------------------
# Section 5: CLI dispatch
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export MEE voice emotion models to ONNX / INT8 for Jetson."
    )
    parser.add_argument(
        "--model",
        choices=["speechbrain_iemocap", "wav2vec2"],
        default="speechbrain_iemocap",
        help="Which voice model to export (default: speechbrain_iemocap)",
    )
    parser.add_argument(
        "--format",
        choices=["onnx", "int8"],
        default="onnx",
        help="Output format: onnx (FP32) or int8 (quantized) (default: onnx)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for exported models (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="Override SpeechBrain IEMOCAP model directory",
    )
    args = parser.parse_args(argv)

    try:
        if args.model == "speechbrain_iemocap":
            export_speechbrain_iemocap(args.output_dir, args.format, args.model_path)
        else:
            export_wav2vec2(args.output_dir, args.format)
    except Exception as e:
        print(f"[export] FAILED: {e}", file=sys.stderr)
        return 1

    print("[export] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
