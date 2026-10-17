# MEE Model Storage

Where Multimodal Emotion Engine stores its model weights, which are **active** in
the production path, and which are research-only / legacy / optional.

> **All weights live outside the repo** except for one pre-exported ONNX in
> `models/exported/` (see "In-repo" below). Nothing under `mee/` contains
> weights — the package is pure Python and imports the model libraries
> (EmotiEffLib, SpeechBrain, MediaPipe, insightface) that locate their own
> weights in the user's home / cache directories.

**Audited:** 2026-10-17. Sizes measured on the operator's Jetson AGX Orin host
(`deepsim`).

---

## Active (production) models

These are loaded by the default pipeline on every run.

| Component | Model | Default location | Size | Backend |
|-----------|-------|------------------|------|---------|
| **Vision — face detection** | MediaPipe face landmark (`face_landmark.tflite`) | `~/.local/lib/python3.10/site-packages/mediapipe/modules/face_landmark/` (in the pip wheel) | ~6 MB | MediaPipe (active; `FaceDetector._backend == "mediapipe"`) |
| **Vision — emotion** | `enet_b0_8_best_vgaf` (EmotiEffLib) | `~/.emotiefflib/enet_b0_8_best_vgaf.onnx` (+ `.pt`) | 31 MB | ONNX Runtime |
| **Voice — emotion** | wav2vec2-IEMOCAP (SpeechBrain) | `~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP/` → `wav2vec2.ckpt` (377 MB) | 361 MB | SpeechBrain (runs in a **separate worker process** — see `MEE_VOICE_ENABLED`) |

**Active total: ≈ 400 MB** (excluding the ~6 MB MediaPipe model that ships
inside the pip package).

### How each is located (code)

- **Vision emotion** — `mee/vision/emotion_model.py` constructs
  `EmotiEffLibRecognizer(engine="onnx", model_name="enet_b0_8_best_vgaf", device="cpu")`.
  EmotiEffLib loads its weights from `~/.emotiefflib/` (the package default).
  Override with `MEEConfig.vision_model_path` or
  `EmotionModel(model_path=...)`.
- **Voice emotion** — `mee/voice/emotion_model.py:79-81` hardcodes the default
  `model_path = ~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP`.
  `EncoderClassifier.from_hparams(source=model_path, savedir=model_path)` loads
  `wav2vec2.ckpt` + `hyperparams.yaml` from there. Override with
  `MEEConfig.voice_model_path`.
- **Vision detection** — `mee/vision/detector.py` imports `mediapipe` and uses
  the bundled `face_landmark.tflite` (no home-dir download).

> **`label_encoder.ckpt` is a symlink** into
> `~/.cache/huggingface/hub/models--speechbrain--emotion-recognition-wav2vec2-IEMOCAP/...`.
> Do **not** delete `~/.cache/huggingface` without re-linking — the voice model
> needs it at load time.

---

## In-repo model (optional alternative voice model)

| Path | Model | Size | Role |
|------|-------|------|------|
| `models/exported/emotion_iemocap.onnx` | IEMOCAP emotion → ONNX | 724 KB | ORT/TRT graph |
| `models/exported/emotion_iemocap.onnx.data` | weights blob | 361 MB | external data |

`mee/voice/emotion_model.py:243-256` (`_find_tensorrt_engine`) will load this
if it is placed in the voice `model_dir` **and** ONNX Runtime with a
TensorRT/CUDA execution provider is available — it is the pre-exported ONNX
alternative for GPU-accelerated voice. It is **not** the default (the default
is the SpeechBrain `wav2vec2.ckpt` above), so it is only used when you point
`MEEConfig.voice_model_path` at `models/exported/` (or move the files into the
SpeechBrain dir). Kept in the repo so the GPU-accelerated path is reproducible.

> **Note:** `models/*.onnx.data` is listed in `.gitignore`
> ("Binary data (ONNX data splits, too large for git)"), so the 361 MB
> `.data` file is present on the operator's disk but **not committed**. Only
> the 724 KB `.onnx` graph is under version control.

---

## Research-only / legacy / unused weights

Present on the host, **not** on the default production path. Safe to keep or
remove depending on whether you want the research / GPU / legacy options.

| Path | Model | Size | Status |
|------|-------|------|--------|
| `~/.insightface/models/buffalo_l/` (5 ONNX: det_10g, w600k_r50, 1k3d68, 2d106det, genderage) | InsightFace SCRFD | 326 MB | **Research-only.** `detector.py`: "buffalo_l / InsightFace is intentionally ABSENT from the production path." Loads only when `INSIGHTFACE_RESEARCH_ONLY=true`. |
| `~/.insightface/buffalo_l.zip` | same, compressed | 276 MB | **Duplicate** of the extracted `buffalo_l/` — safe to delete (re-downloadable from insightface). |
| `~/.insightface/models/mtl-mimic-rep-vanilla/` | (empty stub) | 4 KB | Not referenced anywhere in MEE code. |
| `~/.deepface/weights/retinaface.h5` | RetinaFace | 114 MB | **Legacy.** Used only if the `retinaface` PyPI lib is active (`_try_retinaface()`, needs CUDA + `use_retinaface=True`). Not imported by MEE directly; this is the DeepFace tool's cache. |
| `~/.cache/torch/hub/checkpoints/` (`2DFAN4-*.pth.tar`, `s3fd-*.pth`) | torch face-det | 177 MB | Torch face-detection checkpoints; not referenced in the active `mee/vision` path (detector uses mediapipe). |
| `~/.cache/huggingface/hub/` (speechbrain) | HF cache | 28 KB | **Load-bearing** for the voice model via the `label_encoder.ckpt` symlink — do not delete without re-linking. |

**Research/legacy/unused total: ≈ 1.1 GB.**

---

## Removing unused weights (reclaim ~1 GB)

Only do this if you are sure you will not use the research / GPU / legacy paths.

```bash
# Safest first — the zip is a pure duplicate of the extracted dir:
rm /home/deepsim/.insightface/buffalo_l.zip            # -276 MB

# Research-only SCRFD (need INSIGHTFACE_RESEARCH_ONLY to use):
rm -rf /home/deepsim/.insightface/models/buffalo_l     # -326 MB

# DeepFace legacy RetinaFace (need the `retinaface` lib + CUDA to use):
rm -rf /home/deepsim/.deepface                          # -114 MB

# Torch face-det checkpoints (not in the active path):
rm -rf /home/deepsim/.cache/torch/hub/checkpoints      # -177 MB
```

**Do NOT delete:**
- `~/.emotiefflib/` (active vision emotion)
- `~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP/` (active voice)
- `~/.cache/huggingface/` (voice `label_encoder.ckpt` symlink target)
- `models/exported/` (in-repo GPU voice option; `.onnx` graph is committed)

---

## Reproducing the weights on a fresh host

- **Vision emotion:** `pip install emotiefflib` then run once (it downloads
  `enet_b0_8_best_vgaf` to `~/.emotiefflib/`), or copy the two files from an
  existing host.
- **Voice (SpeechBrain):** `pip install speechbrain transformers` then run
  `EmotionModel._ensure_loaded()` once — it pulls wav2vec2-IEMOCAP into
  `~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP/` (and the HF
  cache).
- **Vision detection (MediaPipe):** `pip install mediapipe` — the
  `face_landmark.tflite` ships inside the wheel; nothing to download separately.
- **GPU voice ONNX (optional):** copy `models/exported/emotion_iemocap.onnx`
  + `.onnx.data` into the voice model dir and enable an ORT TensorRT/CUDA
  provider.

---

## Related

- `docs/ARCHITECTURE.md` — pipeline design
- `docs/THIRD_PARTY_LICENSES.md` — model + library licenses
- `docs/DEMO.md` — demo behavior (incl. voice worker isolation)
- `docs/remotedemo/DEPLOYMENT.md` — deployment + voice-worker + mic-silence troubleshooting
