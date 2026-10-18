# MEE Model Storage

All production model weights live in a **single canonical tree inside the repo**:

```
multimodal-emotion-engine/models/
├── vision_emotion/    # EmotiEffLib enet_b0_8_best_vgaf (AffectNet)
│   ├── enet_b0_8_best_vgaf.onnx    # 16 MB  (active vision emotion)
│   └── enet_b0_8_best_vgaf.pt      # 16 MB  (PyTorch weights, optional)
├── voice/             # SpeechBrain wav2vec2-IEMOCAP
│   ├── wav2vec2.ckpt           # 377 MB  (active voice emotion)
│   ├── model.ckpt              #   13 KB
│   ├── hyperparams.yaml
│   ├── label_encoder.txt
│   ├── custom_interface.py
│   └── {anger,hap,neutral,sad}.wav   # example clips (smoke tests)
├── voice_gpu/         # opt-in: IEMOCAP → ONNX for ORT/TensorRT
│   ├── emotion_iemocap.onnx          # 724 KB  (committed)
│   └── emotion_iemocap.onnx.data     # 361 MB  (.gitignore'd)
└── exported/          # same GPU ONNX, in-repo (committed graph)
```

The `models/` tree is the **source of truth**. The engine, worker, and
processors all resolve it directly — no per-library home caches required
(see "Resolver layer" below). Populate a fresh host with:

```bash
python3 tools/download_models.py            # downloads vision_emotion + voice
python3 tools/download_models.py --verify   # re-check sizes / checksums
```

**Audited:** 2026-10-17. Sizes measured on the operator's Jetson AGX Orin
host (`deepsim`).

---

## Active (production) models

| Component | Model | Canonical location | Size | Backend |
|-----------|-------|--------------------|------|---------|
| **Vision — face detection** | MediaPipe `face_landmark.tflite` | ships inside the `mediapipe` pip wheel | ~6 MB | MediaPipe |
| **Vision — emotion** | `enet_b0_8_best_vgaf` (EmotiEffLib) | `models/vision_emotion/` | 31 MB | ONNX Runtime |
| **Voice — emotion** | wav2vec2-IEMOCAP (SpeechBrain) | `models/voice/` → `wav2vec2.ckpt` | 377 MB | SpeechBrain (separate worker process) |

**Active total: ≈ 414 MB** (excluding the ~6 MB MediaPipe model in the wheel).

---

## How each is located (code)

- **Vision emotion** — `mee/vision/emotion_model.py`. `EmotionModel` now
  stages an explicit `model_path` into EmotiEffLib's hardcoded
  `~/.emotiefflib/` cache (which has no env override) before constructing
  `EmotiEffLibRecognizer(engine="onnx", model_name="enet_b0_8_best_vgaf")`.
  The engine defaults `vision_model_path` to `models/vision_emotion`.
- **Voice emotion** — `mee/voice/emotion_model.py`. `EmotionModel` accepts an
  explicit `model_path` and calls
  `EncoderClassifier.from_hparams(source=model_path, savedir=model_path)`.
  The out-of-process worker reads `MEE_VOICE_MODEL_PATH` (set by the engine
  from `config.voice_model_path`, default `models/voice`).
- **Vision detection** — `mee/vision/detector.py` imports `mediapipe` and uses
  the bundled `face_landmark.tflite` (no separate download).

---

## Resolver layer (2026-10-17)

The engine no longer depends on per-library home caches. `MEEConfig`
(`mee/api/engine.py`) resolves the model paths to the canonical tree:

| Field | Default | Env override |
|-------|---------|--------------|
| `model_root` | `<repo>/models` | `MEE_MODEL_ROOT` |
| `vision_model_path` | `<repo>/models/vision_emotion` | `MEE_VISION_MODEL_PATH` |
| `voice_model_path` | `<repo>/models/voice` | `MEE_VOICE_MODEL_PATH` |

Helpers `_default_model_root()` / `_sub_model_dir()` return `None` if the
directory is absent, so the backends fall back to their own defaults on a
machine that hasn't run `tools/download_models.py`.

The **out-of-process voice worker** gets its path two ways: the engine passes
`config.voice_model_path` into `VoiceWorkerClient(model_path=...)`, which sets
`MEE_VOICE_MODEL_PATH` in the worker's environment; the worker reads it to build
`EmotionModel(model_path=...)`.

> **Why the split process?** On this Jetson AGX (aarch64) host, loading the
> SpeechBrain/torch voice runtime in the *same* process as the MediaPipe vision
> runtime causes a native C-runtime collision (segfault). They must run in
> separate processes. See `docs/DEMO.md` and `docs/remotedemo/DEPLOYMENT.md`.

---

## Legacy / optional weights (outside the canonical tree)

Present on the operator's host; **not** on the default production path.

| Path | Model | Size | Status |
|------|-------|------|--------|
| `~/.insightface/models/buffalo_l/` | InsightFace SCRFD | 326 MB | **Removed** 2026-10-17 (research-only, `INSIGHTFACE_RESEARCH_ONLY`). |
| `~/.insightface/buffalo_l.zip` | same, compressed | 276 MB | **Removed** 2026-10-17 (duplicate). |
| `~/.deepface/` | RetinaFace (DeepFace) | 114 MB | **Removed** 2026-10-17 (legacy). |
| `~/.cache/torch/hub/checkpoints/` | torch face-det | 177 MB | **Removed** 2026-10-17 (not in active path). |

**Reclaimed on 2026-10-17: ≈ 893 MB.**

> The active voice model historically lived in
> `~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP/` and the vision
> model in `~/.emotiefflib/`. Those are now the *staging/legacy* fallback
> locations; the canonical copies are under `models/`. The `~/.cache/huggingface`
> HF cache may still be referenced by a `label_encoder.ckpt` symlink in some
> checkouts — if you delete it, re-run `tools/download_models.py --mirror` to
> re-stage.

---

## GPU voice (opt-in)

`models/voice_gpu/` (and the in-repo `models/exported/`) hold an ONNX export of
the IEMOCAP emotion model for ORT TensorRT/CUDA acceleration. `mee/voice/emotion_model.py`
(`_find_tensorrt_engine`) loads it when it is present in the voice `model_dir`
**and** an ORT TensorRT/CUDA provider is available. It is **not** the default.

> `models/*.onnx.data` is `.gitignore`'d (too large for git); only the small
> `.onnx` graph is committed. Re-stage with `tools/download_models.py --mirror`.

---

## Fresh-host setup (end-to-end)

```bash
git clone <repo> && cd multimodal-emotion-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # or: pip install mediapipe onnxruntime speechbrain transformers
python3 tools/download_models.py            # populate models/ (≈ 414 MB)
python3 tools/download_models.py --verify   # confirm
bash mee-remotedemo-start.sh                # launch the demo
```

---

## Related

- `models/README.md` — the `models/` tree itself
- `tools/download_models.py` — the population tool
- `docs/ARCHITECTURE.md` — pipeline design
- `docs/THIRD_PARTY_LICENSES.md` — model + library licenses
- `docs/DEMO.md` — demo behavior (incl. voice worker isolation)
- `docs/remotedemo/DEPLOYMENT.md` — deployment + voice-worker + mic-silence troubleshooting
