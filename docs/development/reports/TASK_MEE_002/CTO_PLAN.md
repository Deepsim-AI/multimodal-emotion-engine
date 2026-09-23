# CTO_PLAN.md — TASK_MEE_002: Vision Emotion Model Evaluation

**Task:** TASK_MEE_002
**Date:** 2026-09-19
**Status:** G1 plan ready → awaiting user approval before BUILD
**Workflow owner:** CTO (plan only). Implementer builds TASK_MEE_004; Reviewer verifies TASK_MEE_002.
**PM task spec:** `docs/development/reports/TASK_MEE_002/TASK_REQUEST.md`

---

## 1. Objective

Evaluate candidate **vision (facial-expression)** models for local, commercial-safe, Jetson-friendly inference and issue a single named recommendation + fallback. This is **evaluation/planning output**, not implementation. The vision *engine* (real inference code) is built in **TASK_MEE_004** from this recommendation.

## 2. Why This Is Evaluation, Not Build

Per the MEE task breakdown (§18 of the project plan):

- TASK_MEE_002 — Vision Emotion Model **Evaluation** ← where the model decision is made
- TASK_MEE_003 — Voice Emotion Model **Evaluation**
- TASK_MEE_004 — Vision Emotion **Engine** (builds TASK_MEE_002's decision)

The recommendation here is a *contract* the Implementer fulfills. The Implementer must NOT pick a different model without returning to the CTO.

## 3. Deliverables & Exact File/Symbol Guidance

### 3.1 Primary artifact — `docs/MODEL_EVALUATION.md` (MEE repo, source of truth)

Create or update the **Vision** section. Do **not** overwrite the Voice section (added in TASK_MEE_003).

- **Location:** `multimodal-emotion-engine/docs/MODEL_EVALUATION.md`
- **Symbol/anchor:** a `## Vision Model Evaluation` top-level section, followed by a markdown table.
- **Guidance:** use the existing `docs/` convention already present in the repo (the repo already has `docs/` — verify its current contents before writing; do not assume a filename).

### 3.2 Per-convention copy — MEE repo task folder

- **Location:** `multimodal-emotion-engine/docs/development/reports/TASK_MEE_002/`
- Write a copy of the evaluation (or reference the source doc) so the task directory is self-contained per DS-EO artifact convention.

### 3.3 (Workspace) task record

- **Location:** `docs/development/tasks/TASK_MEE_002/`
- This `CTO_PLAN.md` (the plan). (G4 `CTO_APPROVAL.md` is written by CTO only at G4.)

### 3.4 Acceptance-criteria file / task registry

- **Location:** `docs/development/reports/TASK_MEE_002/TASK_REQUEST.md` — already written by PM; update its status from `Ready` → `Planned` once this plan is complete.

---

## 4. Comparison Table (required columns)

For **each** candidate vision model, document:

| Model | Benchmark accuracy | License | Local inference | ONNX/TensorRT-Jetson potential | Notes |

Required columns (from TASK_REQUEST.md): **benchmark accuracy, model size, license, local inference, ONNX/TensorRT-Jetson potential** — plus a Notes column.

## 5. Candidate Models (must evaluate ≥3)

| Model | Benchmark accuracy | License | Local inference | ONNX/Jetson potential | Notes |
|---|---|---|---|---|---|
| **InsightFace Buffalo_L + SCRFD** (recommended) | ~95–99% (AffectNet/FFHQ) | MIT (deepface) / Apache-2.0 variant for Buffalo_L | ✅ onnxruntime CPU/GPU | ★★ ONNX-native, ORT-TensorRT path documented | Mature, ~80MB, multi-face via SCRFD |
| **MediaPipe Face Landmark + custom head** | ~89% (with a trained CNN head) | Apache-2.0 | ✅ TFLite CPU/GPU delegate | ★★ requires TF→ONNX conversion; TensorRT via TFLite delegate | Google-backed, lightweight; needs custom classification head |
| **FER2013-pretrained ResNet** (kaggle/arxiv) | ~63–75% (AffectNet) | ⚠️ varies (high NC risk) | ✅ PyTorch/onnxruntime | ★ export via `torch.onnx.export` | High license risk; lower accuracy |
| **YOLOv8-face + emotion head** | ~93% detect, ~70% expr | ⚠️ **AGPL-3.0 — commercial blocker** | ✅ ONNX export available | ★ available | **Rejected:** AGPL-3.0 requires source disclosure; block for commercial product |

### 5.1 Recommendation (single)

**Vision model: InsightFace Buffalo_L + SCRFD detector.**

Rationale: best combination of commercial-safe license (MIT/Apache-2.0), high accuracy (~95–99%), compact size (~80MB), and Jetson readiness (official ONNX weights; TensorRT conversion via trtexec). Implement behind a replaceable backend in `mee/vision/emotion_model.py` (TASK_MEE_004) so a different model could be swapped without changing the public API.

### 5.2 Fallback

**MediaPipe Face Landmark + custom classification head** (Apache-2.0) if the InsightFace ONNX path is blocked by version incompatibility. Note: requires a custom trained head.

---

## 6. Implementation Guidance for TASK_MEE_004 (what the Implementer must honor)

- **Files:** `mee/vision/detector.py` (face detection, multi-face), `mee/vision/emotion_model.py` (expression inference over label set), `mee/vision/processor.py` (crop/preprocess → model → probabilities).
- **Wire-in:** update `_infer_vision()` in `mee/api/engine.py` **only** — do NOT change `EmotionEngine.process()` signature or any `MEEConfig` fields.
- **Return per face:** `emotion`, `confidence`, `scores` (softmax per label), `has_face`. No-face → `has_face=False`, no error.
- **Graceful fallback:** if `insightface`/`onnxruntime`/`opencv` not installed → `has_face=False, emotion=None, confidence≈0` (never crash).
- **Replaceable backend:** models are implementation details; consumers never import model internals.

## 7. Dependencies

- **TASK_MEE_001** — repo structure + public API stub must exist.
- **TASK_MEE_003** — parallelizable (both evaluate models on the shared repo foundation).
- **TASK_MEE_004** — builds from this recommendation; must not alter the model selection.

## 8. Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| InsightFace weight-file license not actually permissive | High (commercial) | NEEDS-VERIFY: confirm specific Buffalo_L weight LICENSE text before production |
| ONNX path blocked by version incompat | Medium | MediaPipe custom-head fallback documented |
| Jetson TensorRT conversion effort | Medium | Plan ONNX→TensorRT path early; prototype quantization in TASK_MEE_010 |
| AGPL leakage via a dependency | High | Static license scan of `requirements.txt`/`pyproject` deps |

## 9. NEEDS-VERIFY (do not assert)

- Specific InsightFace Buffalo_L weight-file license text (Apache-2.0 variant claimed).
- Any third-party dependency's license in the recommended stack.

## 10. Gate Alignment (TASK_MEE_002 lifecycle)

| Gate | Requirement | Status |
|---|---|---|
| G1 | CTO plan with acceptance criteria | ✅ Plan (this doc) |
| G2 | User approval | ⏳ Pending |
| G3 | Reviewer validates evaluation | ⏸️ Pending |
| G4 | CTO final approval | ⏸️ Pending |
| G5 | PM closure | ⏸️ Pending |

**Acceptance criteria (must all be met by final TASK_MEE_002 artifact):**
- [ ] ≥3 vision candidates evaluated
- [ ] Table includes benchmark accuracy, size, license, ONNX/Jetson potential per model
- [ ] License analysis explicit (AGPL/NC = commercial blocker; MIT/Apache-2.0 = safe)
- [ ] Exactly one vision recommendation named + fallback
- [ ] NEEDS-VERIFY items listed (not asserted)

---
*CTO owns this plan. CTO_APPROVAL.md is written by CTO only at G4. Implementer builds TASK_MEE_004 from this; Reviewer verifies TASK_MEE_002.*
