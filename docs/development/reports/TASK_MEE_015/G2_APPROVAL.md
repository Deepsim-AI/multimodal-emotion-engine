# G2 Approval — TASK_MEE_015: MEE License Integration (Gate C)

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Approved by:** Owner (gateway-owner)  
**CTO Status:** Approved with amendments (see CORE_CONTRACTS.md §7, GATE_C_EXTENSIBILITY_ANALYSIS.md)  

---

## Decision: APPROVED for G2 Implementation

The CTO plan is approved subject to the owner's implementation requirements below. The Implementer must satisfy ALL conditions before marking G2 complete.

### Prerequisites (Implementer must complete before coding):

1. **Read all required documents:**
   - `GATE_C_SPECIFICATION.md` (amended, now includes R28–R47)
   - `CORE_CONTRACTS.md` §7 (Amendments A–G)
   - `GATE_C_EXTENSIBILITY_ANALYSIS.md` (full — required reading)
   - `CTO_PLAN.md` (section 9: Notes for Implementer + section 11: Extensibility Amendment Notes)
   - `BOUNDARIES.md`

2. **Pre-flight check:** Verify `cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey.from_public_bytes()` imports successfully on the MEE host. Record proof in implementation report.

### Mandatory Implementation Requirements:

1. Implement all 7 owner-conditions verbatim. No shortcuts.
2. The `VerificationResult` dataclass is a required replacement for the original bare `bool` return from `verify()`.
3. Trial duration resolution precedence (Keygate feature > env var > default) must be tested and documented.
4. No hardcoded plan_name matching anywhere in MEE licensing code. Feature map drives all behavior.
5. Unknown features are stored but ignored — no implicit capability grants, no crashes.
6. Temporary network failures are distinguished from license expiration with correct offline fallback logic.

### Deliverables:

| Deliverable | Owner | Location |
|---|---|---|
| `mee/licensing/` package (8+ files) | Implementer | `<repo>/mee/licensing/` |
| Engine integration | Implementer | `mee/api/engine.py` + `mee/api/license.py` |
| CLI (`mee-lic`) | Implementer | `mee/licensing/cli.py` + pyproject entry point |
| Unit + integration + E2E tests (~18 total) | Implementer | `tests/test_licensing_*.py` + `tools/license_smoke_test.py` |
| Implementation report | Implementer | `IMPLEMENTATION_REPORT.md` in task directory |

### Post-G2 Handoff:

After G2 completion, the Implementer writes `IMPLEMENTATION_REPORT.md` and hands off to the Reviewer for G3 independent verification. The CTO_APPROVAL.md artifact (pre-written, located at `CTO_APPROVAL.md`) will be evaluated post-review.

---

**G2 APPROVED. Forward to Implementer for execution.**
