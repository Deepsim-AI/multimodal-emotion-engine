# `models/` — canonical model weights

This directory is the **single source of truth** for every production model
weight. The engine, the out-of-process voice worker, and all processors resolve
their weights from here (no per-library home caches required).

## Layout

```
models/
├── vision_emotion/    # EmotiEffLib enet_b0_8_best_vgaf (AffectNet) — VISION emotion
│   ├── enet_b0_8_best_vgaf.onnx    # 16 MB   (active)
│   └── enet_b0_8_best_vgaf.pt      # 16 MB   (PyTorch weights, optional)
├── voice/             # SpeechBrain wav2vec2-IEMOCAP — VOICE emotion
│   ├── wav2vec2.ckpt           # 377 MB  (active)
│   ├── model.ckpt              #   13 KB
│   ├── hyperparams.yaml        # required
│   ├── label_encoder.txt       # required
│   ├── custom_interface.py     # required
│   └── {anger,hap,neutral,sad}.wav   # small example clips for smoke tests
├── voice_gpu/         # OPT-IN: IEMOCAP → ONNX for ORT/TensorRT
│   ├── emotion_iemocap.onnx          # 724 KB  (committed)
│   └── emotion_iemocap.onnx.data     # 361 MB  (.gitignore'd)
└── exported/          # same GPU ONNX, kept in-repo (committed graph)
```

**Active total ≈ 414 MB.**

## Populate a fresh host

```bash
python3 tools/download_models.py             # downloads vision_emotion + voice
python3 tools/download_models.py --verify    # re-check sizes / checksums
python3 tools/download_models.py --only voice        # just one subfolder
python3 tools/download_models.py --mirror    # copy already-present local weights
python3 tools/download_models.py --link      # (optional) legacy backend symlinks
```

The tool is idempotent — files already present with the expected size are
skipped. `--force` re-downloads.

## How the code finds these files

| Path | Resolved by |
|------|-------------|
| `models/vision_emotion/` | `MEEConfig.vision_model_path` (default) → `EmotionModel._stage_weights()` → EmotiEffLibRecognizer |
| `models/voice/` | `MEEConfig.voice_model_path` (default) → `VoiceWorkerClient(model_path=...)` → worker's `MEE_VOICE_MODEL_PATH` env → `EmotionModel(model_path=...)` |
| `models/voice_gpu/` | opt-in; loaded by `EmotionModel._find_tensorrt_engine()` when an ORT TensorRT/CUDA provider is present |

## Git policy

- Small text + the 724 KB `voice_gpu/*.onnx` graph are committed.
- Large binary weights (`*.onnx.data`, `*.pt`, `*.wav`, `*.ckpt`) are
  `.gitignore`'d — pull them with `tools/download_models.py` on each fresh
  host. This keeps the repo clone small while the weights stay reproducible.

## Do **not**

- Delete `models/voice/` or `models/vision_emotion/` without re-running
  `tools/download_models.py` — the active pipeline will not load.
- Commit `.onnx.data` (or other large binaries) directly to git — use the
  download tool instead.
