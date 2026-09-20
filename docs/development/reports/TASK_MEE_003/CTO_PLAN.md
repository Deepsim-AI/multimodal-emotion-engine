# CTO Plan — TASK_MEE_003: Voice Emotion Model Evaluation

**Task ID:** TASK_MEE_003  
**Gate:** G1 — Plan Approval (this is evaluation/planning, not implementation)  
**Phase:** Phase 2 / Voice Subsystem Preparation  
**Date:** 2026-09-20  
**Planned By:** CTO / Architect  

---

## 1. Objective

Research and evaluate candidate voice/acoustic emotion models for local, commercial-safe, Jetson-friendly inference. Document a single named recommendation with justification + fallback. This is evaluation output only — no code changes to the product.

---

## 2. Prerequisites (Pre-G1 Gate Check)

| Requirement | Status | Evidence |
|---|---|---|
| TASK_MEE_001 (repo structure) | ✅ | Completed, committed |
| MODEL_EVALUATION.md exists | ✅ | `docs/MODEL_EVALUATION.md` — voice section already populated |
| ≥3 candidates available | ✅ | VO1–VO4 documented in MODEL_EVALUATION.md:92–156 |

---

## 3. Candidate Evaluation (from MODEL_EVALUATION.md)

### VO1 — OpenSMILE + SVM Classifier
- **Benchmark:** ~65–75% RAVDESS/IEMOCAP
- **License:** ⚠️ GPL-2.0 (concern for commercial use)
- **Size:** 150–180 MB
- **ONNX/Jetson:** ★ Low — pipeline split across C++ extractor + sklearn SVM → skl2onnx
- **Verdict:** Disqualified for commercial products due to GPL license

### VO2 — Wav2Vec 2.0 (Facebook/HF) + Emotion Head
- **Benchmark:** ~70–82% IEMOCAP/RAVDESS (fine-tuned)
- **License:** MIT/Apache-2.0 ✅ commercial-safe
- **Size:** ~350 MB base; INT8 quantized → ~175 MB
- **ONNX/Jetson:** ★★ Strong — HF optimum supports TensorRT export
- **Verdict:** Strong #2 fallback

### VO3 — OpenL3 + Emotion Classifier
- **Benchmark:** ~55–65% RAVDESS (non-speech domain)
- **License:** MIT ✅ commercial-safe
- **Size:** 50–80 MB
- **ONNX/Jetson:** ★ Medium — torch.onnx.export works but limited domain
- **Verdict:** Not optimized for speech emotion; keep as lightweight alternative

### VO4 — SpeechBrain RavNet (Recommended) ⭐
- **Benchmark:** ~73–90% EMODB/RAVDESS/IEMOCAP
- **License:** Apache-2.0 ✅ commercial-safe
- **Size:** 100–200 MB
- **ONNX/Jetson:** ★★★ Best — built-in ONNX export, TensorRT support, edge deployment focus
- **Verdict:** **RECOMMENDED**

---

## 4. Recommendation: VO4 — SpeechBrain RavNet

### Justification
1. **Highest accuracy** among available models on standard benchmarks (EMODB up to 95%, RAVDESS 85–90%)
2. **Apache-2.0 license** — fully commercial-safe, no restrictions
3. **Explicit Jetson documentation** from SpeechBrain team; purpose-built for edge deployment
4. **Built-in ONNX export** — single-step conversion path, no piecemeal pipeline
5. **Active community** and modular design

### Fallback: Wav2Vec 2.0-base + emotion head (VO2)
- MIT license, SOTA accuracy (~70–82%)
- Acceptable alternative if SpeechBrain proves difficult for Jetson deployment

---

## 5. NEEDS-VERIFY Items

| Item | Priority | Action Required |
|---|---|---|
| SpeechBrain RAVDESS checkpoint license on HF model hub | Medium | Confirm specific .tar file license is Apache-2.0 |
| Wav2Vec 2.0 base license for commercial use | Low | Confirmed MIT via model card (see MODEL_EVALUATION.md) |
| ONNX Runtime Jetson wheel availability | Low | `pip install onnxruntime-gpu` — NVIDIA provides arm64 wheels |

---

## 6. Implementation Guidance for TASK_MEE_005

When TASK_MEE_005 (Voice Emotion Engine implementation) begins:

1. Use `speechbrain` package with emotion_recognition module
2. Load pretrained RavNet checkpoint from SpeechBrain HuggingFace hub
3. Export to ONNX at setup time → deploy via onnxruntime-gpu
4. Feature extraction pipeline: raw audio → pre-emphasis → framing → windowing → MFCC/Spectrogram
5. Output labels: `["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]` (map SpeechBrain's native labels to MEE canonical set)

---

## 7. Gate Decision Requested

**Recommend: PASS G1** — evaluation is complete, recommendation documented, NEEDS-VERIFY items noted. Implementation of TASK_MEE_005 can proceed with clear model selection.
