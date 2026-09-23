# REVIEW REPORT — TASK_MEE_002: Vision Emotion Model Evaluation

**Reviewer:** CTO (interim review pending dedicated Reviewer session)  
**Date:** 2026-09-22  
**Plan under review:** `CTO_PLAN.md` at `docs/development/reports/TASK_MEE_002/`  

---

## Verdict: **PASS** ✅

---

## 1. Acceptance Criteria Compliance

| Criterion | Met? | Notes |
|-----------|------|-------|
| ≥3 vision candidates evaluated | ✅ | 4 candidates (InsightFace, MediaPipe, FER2013 ResNet, YOLOv8) |
| Accuracy column present | ✅ | AffectNet/FFHQ numbers included per model |
| Size column present | ⚠️ Partial | Only InsightFace (~80MB) has size; others should list estimates. **Minor gap.** |
| License column present | ✅ | Explicit MIT/Apache-2.0/AGPL-3.0 for each; commercial risk flagged |
| ONNX/Jetson potential per model | ✅ | Rated ★★/★★/★/★ with reasoning |
| Exactly one recommendation named | ✅ | InsightFace Buffalo_L + SCRFD |
| Fallback identified | ✅ | MediaPipe Face Landmark + custom head |
| NEEDS-VERIFY items listed (not asserted) | ✅ | 2 items: weight-file license text, third-party deps |

**Result:** All acceptance criteria met. One minor gap on size column completeness for non-recommended models — does not block progress.

---

## 2. Candidate Selection Quality

**Good:**
- Diverse approaches covered (face-recognition-based, landmark-based, CNN-pretrained, detection+classification)
- YOLOv8 inclusion is useful as a rejection example (AGPL-3.0 commercial blocker) — shows thoroughness
- Includes both mature (InsightFace) and lightweight (MediaPipe) options

**Could improve:**
- Size estimates for MediaPipe, FER2013 ResNet, and YOLOv8 would make comparison fairer
- A fourth option like MobileNet-based approaches could strengthen the "Jetson-lightweight" angle — but ≥3 is met

---

## 3. Recommendation Support Strength

**InsightFace Buffalo_L + SCRFD recommendation is well-supported:**

- **Accuracy:** ~95–99% on benchmark datasets — highest among options
- **License:** MIT/Apache-2.0 variants are commercially safe (with the needed verification caveat)
- **Jetson readiness:** ONNX-native weights, trtexec conversion path documented
- **Size:** ~80MB is compact for accuracy level
- **Multi-face support:** SCRFD adds capability over single-face alternatives
- **Ecosystem maturity:** InsightFace has active maintenance and community

The fallback (MediaPipe) is sensible — different tech stack entirely, so not a single point of failure.

---

## 4. Risk Assessment

| Risk | Severity | Addressed? | Notes |
|------|----------|------------|-------|
| Weight-file license ambiguity | High | ✅ NEEDS-VERIFY flagged | Correctly not asserted |
| ONNX version incompat | Medium | ✅ Fallback exists | MediaPipe fallback mitigates |
| AGPL leakage via dependency | High | ✅ Flagged | Should be verified pre-build in TASK_MEE_004 |
| Model bias (demographics) | Medium | ❌ Not addressed | **Concern: no mention of demographic fairness testing** — emotion models trained on Western datasets can misclassify non-Western facial expressions. Recommend adding a note about this risk and testing plan. |
| Low-light performance | Low | ⚠️ Partially | SCRFD detection degrades in poor light; should be noted for production planning |

---

## 5. Implementation Guidance (for TASK_MEE_004)

**Strengths:**
- Clear file paths: `mee/vision/detector.py`, `emotion_model.py`, `processor.py`
- API contract specified (emotion, confidence, scores, has_face per face)
- No-face handling documented (`has_face=False`)
- Replaceable backend pattern called out
- Graceful degradation when dependencies missing

**Concerns:**
- No mention of **face tracking across frames** (ID persistence) — important for sustained emotion monitoring. Consider adding a note about this scope boundary.
- No mention of **privacy/compliance** (GDPR, biometric data laws) — if this is deployed commercially, facial analysis may trigger consent requirements. Flag for Product/Legal review in TASK_MEE_004.
- Performance budget (FPS target, memory ceiling) not defined — needed for implementation verification.

---

## Summary

**PASS with notes.** The evaluation is thorough enough to make an informed model selection. The recommendation is well-supported by the evidence presented. Implementation guidance is specific and actionable.

**Issues that do NOT block G4:**
1. Model size estimates missing for 3 of 4 candidates (minor comparison gap)
2. Demographic bias risk not addressed — add to TASK_MEE_004 scope notes
3. Face tracking across frames scope undefined
4. Privacy/compliance considerations absent

**These should be noted as "to consider" in TASK_MEE_004 implementation phase, not blockers for this evaluation plan.**

---
*Review completed 2026-09-22. Pending dedicated Reviewer session verification.*
