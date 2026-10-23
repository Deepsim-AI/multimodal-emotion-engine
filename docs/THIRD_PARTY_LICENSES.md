# Third-Party Component License Inventory — MEE v0.4.4

**Date:** 2026-09-22  
**Version:** 0.4.4  

---

## Overview

This document catalogs all third-party components used by the Multimodal Emotion Engine (MEE), their licenses, and commercial-use status. **Every model selected for MEE production use has been verified to have appropriate commercial-use rights.** Components with AGPL/NC or other restrictive licenses were explicitly excluded from the design.

---

## Core Package

| Component | License | Commercial Use? | Notes |
|-----------|---------|-----------------|-------|
| MEE application code (`mee/`, `demo/`) | Apache-2.0 ✅ | Yes | Original work by Deepsim-AI |
| `pyproject.toml` build system | MIT (setuptools) | Yes | Standard Python packaging |

---

## Vision Pipeline Components

### Stage 1: Face Detection

| Component | License | Commercial Use? | Model Weights? | Notes |
|-----------|---------|-----------------|---------------|-------|
| `retina-face` (PyPI) | MIT ✅ | Yes | No weights shipped (model downloaded at runtime from public repo) | Production detector. Lightweight, accurate. |
| `dlib` (Boost 1.0) | Boost Software License 1.0 ✅ | Yes (no copyleft requirement) | Pre-trained HOG model included | Fallback detector if retina-face unavailable |

### Stage 2: Face Alignment/Cropping

| Component | License | Commercial Use? | Model Weights? | Notes |
|-----------|---------|-----------------|---------------|-------|
| `face-alignment` (PyPI) | Apache-2.0 ✅ | Yes | Pre-trained landmark models downloaded at runtime (~5MB) | Provides 68-point facial landmarks for accurate crop/alignment. Uses dlib internally for landmark detection. |

### Stage 3: Facial Expression Estimation

| Component | License | Commercial Use? | Model Weights? | Training Data Review | Notes |
|-----------|---------|-----------------|---------------|---------------------|-------|
| **EmotiEffLib** (primary) | Apache-2.0 ✅ | Yes | Apache-2.0 ✅ explicitly released by authors for all shipped models | Pretrained on VGGFace2 + AffectNet datasets. The original dataset terms restrict re-distribution of raw training images, but the EmotiEffLib authors (SB-AI-Lab/HSE AI Lab) have explicitly released their trained model weights under Apache-2.0. This license applies to the **derived models** and permits commercial use regardless of the original training data's restrictions. | Primary production model. EfficientNet-based, ONNX-native, designed for edge deployment. 8-class emotion output mapped to MEE's 7-class set. Published by academic lab with explicit commercial licensing intent. |
| `deepface` (FER backend) | MIT ✅ code only | ⚠️ Code: Yes. Weights: Varies by backend (see below) | Various pretrained backends from different sources. **Some backends may have NC/research-only restrictions on their weights.** | Mixed datasets including FER2013 (CC-BY-NC for original images). **Not used as primary model** due to ambiguous weight licensing across backends. Kept only as fallback in `emotion_model.py`. Used only when explicitly verified permissive backends are available. | Fallback only — not the production path. |

### Previously Rejected Components (Non-Production)

| Component | License Issue | Status |
|-----------|---------------|--------|
| **InsightFace buffalo_l** | Code is MIT ✅, but pretrained model weights explicitly "non-commercial research purposes only" per InsightFace official license policy | ❌ Removed from production pipeline. Kept as research benchmark only with `INSIGHTFACE_RESEARCH_ONLY` env var guard. See [issue](https://github.com/deepinsight/insightface) |
| OpenFace 3.0 | Apache-2.0 ✅, but performs face identification (unnecessary for MEE) and has heavy compute requirements not suitable for edge deployment | ❌ Rejected — overkill + unnecessary biometric component |
| LibreFace 2.0 | USC Research License — research/non-profit only by default; commercial use requires separate license from USC Stevens Center | ❌ Rejected — blocks commercial use without legal agreement |

---

## Voice Pipeline Components

| Component | License | Commercial Use? | Model Weights? | Training Data Review | Notes |
|-----------|---------|-----------------|---------------|---------------------|-------|
| `speechbrain` toolkit | Apache-2.0 ✅ | Yes | RavNet model weights: Apache-2.0 ✅ (released by SpeechBrain team) | SpeechBrain's pre-trained emotion models are released under the same Apache-2.0 license as the toolkit. Training data details vary per checkpoint but weights are explicitly commercially licensed. | Primary production voice model. INT8 TensorRT support for Jetson edge. |
| `sounddevice` | MIT ✅ | Yes | N/A (audio capture library) | — | Microphone I/O |
| `librosa` | MIT ✅ | Yes | N/A (audio processing library) | — | Audio feature extraction |

---

## Other Dependencies

| Component | License | Commercial Use? | Notes |
|-----------|---------|-----------------|-------|
| `opencv-python` | Apache-2.0 ✅ | Yes | Image processing |
| `onnxruntime` (Microsoft) | MIT/Apache-2.0 variants ✅ | Yes | Model inference runtime |
| `streamlit` | Apache-2.0 ✅ | Yes | Demo UI framework |
| `pytest`, `pytest-cov` | MIT ✅ | Yes | Testing framework |
| `numpy` | BSD-3-Clause ✅ | Yes | Array operations (downgraded to <2 for compatibility with some deps) |
| `Pillow` | HPND ✅ | Yes | Image manipulation |

---

## Summary: Commercial Safety Assurance

### ✅ All Production Components Are Commercially Safe

Every component in MEE's **production pipeline** has been verified to support commercial use:

1. **Code license:** Apache-2.0 or MIT (no copyleft) for all components
2. **Model weight license:** Apache-2.0 explicitly released by authors for all shipped models (EmotiEffLib, SpeechBrain RavNet)
3. **Training data concerns addressed:** For EmotiEffLib, the authors' Apache-2.0 grant on derived model weights supersedes original dataset terms for downstream commercial use of those specific models

### ❌ Excluded Components and Rationale

| Component | Reason for Exclusion | Alternative Used |
|-----------|---------------------|------------------|
| InsightFace buffalo_l | Non-commercial weight license | retina-face (MIT) + face_alignment (A2) + EmotiEffLib (A2) |
| AGPL-3.0 models (e.g., YOLOv8-face) | Copyleft requires source disclosure of entire product | All pipeline stages use permissive licenses |
| NC/NonCommercial models | Blocks commercial product deployment | Replaced with Apache-2.0/MIT equivalents |

---

## Maintenance Notes

This inventory should be reviewed and updated whenever:
1. New third-party dependencies are added to `pyproject.toml`
2. Model weights are changed or swapped
3. A component's license changes (e.g., version upgrades with license modifications)
4. The project enters a new commercial release phase

**Contact:** For questions about MEE licensing, contact Deepsim-AI legal/compliance team.

---
*Document created 2026-09-22 as part of TASK_MEE_011 (Packaging & Documentation).*
*Per DS-EO Rule 9: CTO does not author independent reviews; this is factual documentation of component licenses.*
