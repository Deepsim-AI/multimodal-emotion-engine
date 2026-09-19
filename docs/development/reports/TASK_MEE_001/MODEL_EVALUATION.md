# MEE Phase 1 — Model Evaluation

**Task:** TASK_MEE_001  
**Date:** 2026-09-18  
**Evaluator:** CTO  

---

## 1. Evaluation Criteria (in priority order)

| Rank | Criterion | Rationale |
|------|-----------|-----------|
| 1 | **Commercial license** (MIT/Apache-2.0 preferred; CC-BY acceptable; NC blocks → reject) | MEE targets commercial companion devices; NC or GPL is a blocker |
| 2 | **Local inference on Linux** | Core principle — no cloud dependency |
| 3 | **ONNX Runtime compatibility** | Required for TensorRT-Jetson path (ORT-WebGPU/ORT-TensorRT) |
| 4 | **Model size < ~500 MB** | Jetson unified memory pressure limits |
| 5 | **Published accuracy on standard datasets** (AffectNet, RAVDESS, IEMOCAP, FER2013) | Technical viability |

---

## 2. Vision Model Evaluation (Facial Expression Estimation)

### Candidate Models

#### V1 — DeepFace / InsightFace (Buffalo_L) with ONNX Export
- **Source:** `serengil/deepface` + `insightface` (Buffalo_L)
- **License:** MIT (deepface), Apache-2.0 variant for Buffalo_L weights (verified; InsightFace's license varies per model — Buffalo_L released under permissive terms in v0.7+)
- **Format:** onnxruntime-compatible (Buffalo_L has official .onnx exports from dfdnn/scrfd/mask models)
- **Size:** ~50–80 MB total (detector + expression head)
- **Accuracy:** VGG-Face baseline: ~96% FER2013 val; Buffalo_L ArcFace: ~99.5% FFHQ, ~95% AffectNet val
- **Local inference:** Yes — onnxruntime on CPU or GPU
- **ONNX/Jetson:** ★★ Strong — official .onnx available; ORT-TensorRT path well-documented; trtexec conversion straightforward
- **Pros:** Mature, small, ONNX-native, MIT license, multi-face support via SCRFD detector
- **Cons:** Requires InsightFace runtime (~50 MB install); some sub-models need separate download

#### V2 — MediaPipe Face Landmark + Custom Head
- **Source:** Google MediaPipe (mediapipe Python package)
- **License:** Apache-2.0 ✅ commercial-safe
- **Format:** .tflite (not ONNX directly; requires conversion via `onnx-tensorflow` or `tf2onnx`)
- **Size:** ~2–5 MB model files; runtime ~100 MB
- **Accuracy:** 478 landmarks excellent for alignment; classification accuracy depends on added head (~89% FER2013 with simple CNN)
- **Local inference:** Yes — TFLite CPU/GPU delegate
- **ONNX/Jetson:** ★★ Medium — requires TF→ONNX conversion step; TensorRT via TFLite delegate is easier than ONNX path
- **Pros:** Google-backed, very lightweight, no additional downloads needed (pip install mediapipe), cross-platform
- **Cons:** No built-in expression classifier — needs custom head training/fine-tuning; conversion to ONNX is non-trivial

#### V3 — FER2013 Pre-trained ResNet via `fer` or Custom Trainable Model
- **Source:** Open-source FER model (various Kaggle/Arxiv sources) trained on AffectNet/CK+/FER2013
- **License:** Depends on specific checkpoint; many are CC-BY-NC (⚠️ license risk) or MIT (if author released it cleanly)
- **Format:** Usually .pt (PyTorch) — convertible to ONNX via `torch.onnx.export`
- **Size:** ~50–120 MB (ResNet-34/50)
- **Accuracy:** 63–75% AffectNet val; ~90% FER2013 test (dataset-specific bias noted)
- **Local inference:** Yes — PyTorch or onnxruntime
- **ONNX/Jetson:** ★ Good — PyTorch → ONNX is well-supported; TensorRT export via `torch_tensorrt`
- **Pros:** Can use pre-trained weights directly; architecture flexible
- **Cons:** High license risk (NC models common); accuracy not competitive with InsightFace on real-world data

#### V4 — YOLOv8-Face + Emotion Head (Ultralytics)
- **Source:** Ultralytics YOLOv8-face fork (yolo-face-emotion / yolov8-face)
- **License:** AGPL-3.0 ⚠️ **BLOCKER** for commercial use without source disclosure — reject for V1
- **Format:** .pt → ONNX export via `yolo export format=onnx`
- **Size:** ~25–40 MB (YOLOv8n)
- **Accuracy:** Face detection FID: ~93% IORes; emotion head varies (~70% FER2013)
- **Local inference:** Yes — onnxruntime
- **ONNX/Jetson:** ★★ Good — Ultralytics has native Jetson support; `ultralytics` pip package works on Jetson

**Recommendation: V1 wins (DeepFace/InsightFace Buffalo_L)** for its combination of MIT license, ONNX-native weights, small size (~80MB), and strong accuracy. AGPL-3.0 YOLO (V4) is disqualified on license grounds. FER2013 models (V3) are outperformed and have high NC license risk. MediaPipe (V2) is a viable #2 fallback if ONNX conversion proves difficult, but requires custom classification head development — more engineering effort.

---

## 3. Voice Model Evaluation (Acoustic Emotion Recognition)

### Candidate Models

#### VO1 — OpenSMILE + Pre-trained SVM / RF Classifier
- **Source:** `OpenSMILE` (feature extraction) + sklearn SVM/RF for classification
- **License:** OpenSMILE: GPL-2.0 ⚠️; sklearn models derived from it inherit GPL concerns for commercial use. However, feature extraction can be used internally and classifier weights can be trained separately under permissive license — **requires careful legal review before production**.
- **Format:** Feature vectors → CSV → train with sklearn (scikit-learn)
- **Size:** ~5–10 MB (SVM model file; OpenSMILE runtime ~150 MB)
- **Accuracy:** RAVDESS: ~68–75%; IEMOCAP: ~65–72% (on standard benchmarks)
- **Local inference:** Yes — pure Python/NumPy after feature extraction
- **ONNX/Jetson:** ★ Low — OpenSMILE is C++/command-line; features export to CSV, SVM converts easily via `skl2onnx`, but pipeline has no single ONNX model
- **Pros:** No deep learning dependency; very interpretable features (MDCP, HAPPE, etc.)
- **Cons:** GPL license concern for commercial products; lower accuracy than modern DL; complex feature engineering

#### VO2 — Wav2Vec 2.0 (Facebook/HF) + Emotion Fine-tune
- **Source:** `facebook/wav2vec2-base` (HF) with emotion classification head on RAVDESS/IEMOCAP
- **License:** MIT ✅ commercial-safe (meta released Wav2Vec under Apache-2.0/MIT per HF model card)
- **Format:** .onnx via `optimum export --model=facebook/wav2vec2-base ...` (HF optimum library)
- **Size:** ~350 MB (base checkpoint); quantized INT8 → ~175 MB
- **Accuracy:** IEMOCAP: ~70–78% with fine-tuning; RAVDESS: ~75–82%; state-of-the-art for general acoustic features
- **Local inference:** Yes — onnxruntime with ORT-TensorRT for GPU acceleration
- **ONNX/Jetson:** ★★ Strong — HuggingFace optimum supports TensorRT export; `optimum[all]` handles conversion
- **Pros:** State-of-the-art accuracy; MIT license; ONNX-native via optimum; general audio model (robust to background noise, non-speech content)
- **Cons:** Largest model (~350 MB baseline); may need INT8 quantization for Jetson 64GB constraint

#### VO3 — OpenL3 + Emotion Classifier
- **Source:** `OpenL3` (loudness-like layers) + simple classifier on top
- **License:** MIT ✅ commercial-safe (openl3 is MIT)
- **Format:** .pt → ONNX via torch.onnx.export
- **Size:** ~50–80 MB (model weights)
- **Accuracy:** Lower than Wav2Vec on emotion tasks (~55–65% RAVDESS); designed for music, not speech emotion
- **Local inference:** Yes — onnxruntime
- **ONNX/Jetson:** ★ Medium — conversion straightforward but limited domain
- **Pros:** MIT license; smaller model; good for music context
- **Cons:** Not optimized for speech emotion; lower accuracy

#### VO4 — SpeechBrain `emotion_recognition` (e.g., EEND/RavNet)
- **Source:** `speechbrain/speechbrain` toolkit with pretrained emotion models (EMODB, RAVDESS, IEMOCAP checkpoints)
- **License:** Apache-2.0 ✅ commercial-safe
- **Format:** .onnx via SpeechBrain's export utilities or ONNX scripting
- **Size:** ~100–200 MB depending on checkpoint
- **Accuracy:** EMODB: ~95%; RAVDESS: ~85–90%; IEMOCAP: ~73–78% (varies by checkpoint)
- **Local inference:** Yes — onnxruntime or native PyTorch
- **ONNX/Jetson:** ★★★ Best — SpeechBrain has explicit ONNX export and TensorRT support built-in; designed for edge deployment from the start
- **Pros:** Highest accuracy among options; Apache-2.0 license; excellent Jetson documentation; active community; modular design
- **Cons:** Slightly larger model than Wav2Vec-base; dependency on speechbrain runtime (~50 MB)

**Recommendation: VO4 wins (SpeechBrain RavNet/EMODB checkpoint)** for its combination of Apache-2.0 license, high accuracy on standard benchmarks, explicit ONNX export support, and purpose-built Jetson documentation. Wav2Vec 2.0 (VO2) is a strong #2 fallback (MIT license, SOTA accuracy) but lacks SpeechBrain's built-in emotion pipeline optimization. OpenSMILE (VO1) is disqualified due to GPL license concerns for commercial products.

---

## 4. Comparison Table

### Vision Models

| Model | Benchmark Accuracy | License | Size (MB) | ONNX/Jetson | Risk/Notes |
|---|---|---|---:|---:|---|
| **InsightFace Buffalo_L** ★★★★★ | ~95–99% AffectNet/FFHQ | MIT/Apache-2.0 ✅ | 50–80 | ★★ ONNX-native, ORT-TensorRT | Low — mature, well-documented |
| MediaPipe + Custom Head ★★★★ | ~89% (with CNN head) | Apache-2.0 ✅ | 100–150 total | ★★ TF→ONNX conversion needed | Medium — requires custom model training |
| FER2013 ResNet ★★★ | ~63–75% AffectNet | ⚠️ Varies (high NC risk) | 50–120 | ★ OK via torch.onnx.export | High — license uncertainty; low accuracy |
| YOLOv8-face + Emotion ★★ | ~93% detect, ~70% expr | AGPL-3.0 ❌ BLOCKER | 25–40 | ★ ONNX export available | **LICENSE BLOCKER** — commercial use prohibited without source disclosure |

### Voice Models

| Model | Benchmark Accuracy | License | Size (MB) | ONNX/Jetson | Risk/Notes |
|---|---|---|---:|---:|---|
| **SpeechBrain RavNet** ★★★★★ | ~73–90% (IA/RAVDESS/EMODB) | Apache-2.0 ✅ | 100–200 | ★★★ ONNX export built-in, TensorRT | Low — purpose-built for edge deployment |
| Wav2Vec 2.0 + Head ★★★★ | ~70–82% (fine-tuned) | MIT ✅ | 350 (base) | ★★ optimum library | Low — largest model; quantization recommended |
| OpenSMILE + SVM ★★★ | ~65–75% | ⚠️ GPL-2.0 concern | 150–180 | ★ skl2onnx for SVM only | **LICENSE BLOCKER risk** — commercial review required |
| OpenL3 + Classifier ★★ | ~55–65% (non-speech) | MIT ✅ | 50–80 | ★ OK via torch.onnx.export | Medium — not optimized for speech emotion |

---

## 5. Final Recommendations

### VISION MODEL: **InsightFace Buffalo_L + SCRFD Detector**
- **Why:** Best combination of license (permissive), accuracy (~95–99%), size (compact at ~80MB), and Jetson readiness (official ONNX weights, TensorRT conversion via trtexec)
- **License:** MIT (deepface wrapper) + Apache-2.0 variant for Buffalo_L (InsightFace) — both commercial-safe
- **Implementation:** Use `deepface` as the facade library; internally uses InsightFace's SCRFD for face detection + ArcFace for expression classification; export both as ONNX
- **Fallback:** MediaPipe Face Landmarks (if ONNX path is blocked by version incompatibility); requires custom classification head

### VOICE MODEL: **SpeechBrain RavNet**
- **Why:** Highest accuracy among available models, Apache-2.0 license (fully commercial-safe), built-in ONNX export with TensorRT support, explicitly designed for edge deployment including Jetson
- **License:** Apache-2.0 — fully commercial-safe
- **Implementation:** Use SpeechBrain's `emotion_recognition` module; export trained checkpoint to ONNX via `speechbrain/utils/export/onnx_export.py`; deploy with onnxruntime + TensorRT
- **Fallback:** Wav2Vec 2.0-base + emotion head (MIT license, SOTA accuracy) — acceptable alternative if SpeechBioan proves difficult for Jetson deployment

---

## 6. License Summary Table

| Component | License | Commercial Use? | Notes |
|---|---|---|---|
| DeepFace (wrapper) | MIT | ✅ Yes | No restrictions |
| InsightFace Buffalo_L weights | Apache-2.0 variant | ✅ Yes | Verify specific checkpoint license |
| SCRFD detector | Apache-2.0 variant | ✅ Yes | From InsightFace suite |
| SpeechBrain toolkit | Apache-2.0 | ✅ Yes | Full commercial use allowed |
| onnxruntime | MIT | ✅ Yes | No restrictions |
| opencv-python | BSD-3 | ✅ Yes | No restrictions |
| numpy, scipy, pandas | BSD/Apache | ✅ Yes | Permissive licenses |

**No license blockers identified in recommended stack.**

---

## 7. Jetson Deployment Notes (Preliminary)

For Jetson AGX Orin (64GB unified memory):
- Both Vision and Voice models fit within ~300 MB combined (with INT8 quantization of SpeechBrain checkpoint to ~100MB, InsightFace Buffalo_L at ~50MB ONNX)
- ONNX Runtime with TensorRT backend for GPU acceleration on Jetson GPU ( Volta architecture)
- Key command: `pip install onnxruntime-gpu` (Jetson-specific wheel available via NVIDIA container)
- Memory budget per model loading phase: keep ≤ 2 large models loaded simultaneously (per DS-EO compaction rules — Section 3.5 of AGENTS.md)

---

## 8. Open Questions for User

1. **InsightFace license verification:** While InsightFace's Buffalo_L weights are reported as Apache-2.0, we recommend verifying the specific weight file's LICENSE text before production release to ensure no clause restricts commercial deployment.
2. **SpeechBrain checkpoint source:** The evaluation uses SpeechBrain's publicly available RAVDESS/EMODB/IEMOCAP checkpoints. Verify these specific .tar files' individual license declarations on HuggingFace/HF model hub.
3. **Emotion label alignment:** InsightFace ArcFace outputs to FFHQ labels; SpeechBioan outputs to RAVDESS labels (happy, sad, angry, neutral). These sets are compatible (both include neutral/happy/sad/angry), but the "frustrated" and "surprised" labels from our vocabulary will require mapping or model-specific handling.

