# TASK_REQUEST — TASK_MEE_002: Vision Emotion Model Evaluation

**Task ID:** TASK_MEE_002
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Research and evaluate candidate **vision** (facial-expression) models for local, commercial-safe, Jetson-friendly inference. Produce a documented recommendation. This task is **evaluation/planning output**, not implementation.

## Detailed Requirements
- Evaluate **≥3** candidate vision models on standard datasets (AffectNet, FER2013, etc.). Consider e.g. InsightFace Buffalo_L/SCRFD, MediaPipe (+ custom head), a FER ResNet, YOLOv8-face (+ emotion head).
- For each candidate, document: **benchmark accuracy**, **model size**, **license** (commercial-use — AGPL/NC are blockers), **local inference** feasibility, and **ONNX/TensorRT-Jetson potential**.
- Fill a comparison table (see below) and issue a single named recommendation with justification.
- Explicitly flag any license blocker (e.g., AGPL-3.0) and why it is rejected for commercial products.
- Record which items NEED external verification (e.g., specific weight-file license text on HuggingFace).

## Key Files (to create/modify)
- `docs/MODEL_EVALUATION.md` (create or update) — the canonical comparison table + recommendation.
- `docs/development/reports/TASK_MEE_002/MODEL_EVALUATION.md` (copy of the above, per DS-EO artifact convention).

## Acceptance Criteria
- [ ] Comparison table includes all columns: benchmark accuracy, size, license, ONNX/Jetson potential, per model.
- [ ] ≥3 vision candidates evaluated.
- [ ] License analysis explicit: AGPL/NC candidates flagged as commercial blockers; MIT/Apache-2.0 marked safe.
- [ ] Exactly one vision recommendation named with justification + a fallback option.
- [ ] NEEDS-VERIFY items listed (do not assert unverified license claims).

## Dependencies
- TASK_MEE_001 (repo structure + public API stub exist; vision module placeholder exists).

## Notes / Constraints
- MEE must remain independent of the AI Companion book.
- Model selection is a **CTO decision** — PM documents requirements only.
- "Facial-expression estimation"; never "reads true emotion."
