# REVIEW_REPORT — TASK_MEE_029 G3 (Senior Code Reviewer)

**Task ID:** TASK_MEE_029  
**Title:** Fulcio Keyless Release Signing Deployment — Actual State Review  
**Date:** 2026-10-27 (PDT)  
**Reviewer:** 🔍 (ollama/laguna-xs-2.1:q4_K_M)  
**Status:** ✅ **APPROVED — Conditions Met**

---

## EXECUTIVE SUMMARY

This review was initially issued as **CONDITIONAL APPROVAL** (see below). The two conditions were:
1. Update task documentation to reflect the actual implementation path (Option B), not the planned but blocked Option A.
2. Remove the COSIGN_PROBE temporary step from `release-sigstore.yml`.

**Both conditions have been satisfied:**

- GATE_STATUS.md updated (commit `f375fca`) — now correctly documents Option B as the final state and Option A as blocked pending Rekor infrastructure.
- COSIGN_PROBE removed (commit `72bb5e8`) — workflow is clean of temporary artifacts.

The implementation is **approved without conditions**. All security checks, correctness verifications, and robustness criteria from the original review are confirmed.**

## SECTION 1: VERIFICATION OF EVIDENCE

### 1.1 Private Key Never in Repository ✅

Verified: `cosign-private.pem` does not exist in the repository. Only `cosign-public.pem` is committed.

### 1.2 Public Key Validity ✅

The `cosign-public.pem` is a valid EC P-256 public key (SPKI format):
```
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEz/Kiuzp1SNB7WqArYQ+2UteNs6An
06USBH6AZn3jOsXa60/bAbrEDctEeHzUWAljRe/fhhAcHBt8u4f95oo2kg==
-----END PUBLIC KEY-----
```

### 1.3 Workflow Additive-Only Nature ✅

The workflow has two signing paths:

**Keyless Sigstore (Option A / Fulcio):** 
- Lines 88-99 in the current workflow
- Marked with `continue-on-error: true`
- Uses Forgejo OIDC (`id-token: write`) for Fulcio
- **Non-functional**: requires Rekor/Verifiable Log which is not deployed

**Cosign Key-Based (Option B):**
- Lines 101-119 in the current workflow  
- Added per `9f05231 TASK_MEE_029 G2: Option B (Cosign key-based) signing path`
- Fully functional and verified in CI

### 1.4 CI Verification Evidence ✅

From G2_COMPLETION_EVIDENCE.md §7, CI run #38 (2026-10-27T14:41Z):
- Built wheel and sdist successfully
- Signed all 4 artifacts with Cosign key
- Verified all 4 artifacts: **5× "Verified OK"**
- Created Forgejo release v0.4.5
- Uploaded **9 assets**

---

## SECTION 2: CRITICAL FINDINGS

### F1: Documentation Claims Option A, Implementation is Option B (HIGH)

| Source | Claims |
|--------|--------|
| GATE_STATUS.md | "Owner selected **Option A (Fulcio keyless + OIDC)**" |
| G1_PLAN/CTO_TASK_PLAN.md | Implements Option A with Tessera Rekor |
| G2_BLOCKER_EVIDENCE.md | Shows Option A blocked by missing Rekor |
| G2_COMPLETION_EVIDENCE.md | Comment says "Option B" |
| Workflow commit `9f05231` | Message: "TASK_MEE_029 G2: Option B (Cosign key-based)" |

**Root Cause:** The G0_INTAKE_CHECKLIST.md states owner corrected premises about OIDC and Tessera. However, the evidence shows the Tessera claim was **incorrect** — Tessera is still unreleased (sigstore/rekor states Rekor v2 is "in active development").

**Impact:** The CTO G1 plan for Option A cannot be implemented without a working Rekor log. The task proceeds with Option B which doesn't need Rekor.

**Recommendation:** 
1. Option A is **BLOCKED** — cannot proceed without Rekor infrastructure
2. Option B implementation is **ACCEPTABLE** — proceed with clear documentation of the actual path

### F2: COSIGN_PROBE Step Still Present (MEDIUM)

The temporary probe step at lines 111-143 should be removed. It's harmless but violates "no temporary code in production" principle.

**Recommendation:** Remove before G4.

### F3: Fingerprint Documentation Inconsistency (LOW)

G2_COMPLETION_EVIDENCE.md uses raw PEM file sha256 as "fingerprint". The cryptographic fingerprint (SPKI DER sha256) should be primary.

---

## SECTION 3: SECURITY ANALYSIS

| Check | Status | Notes |
|-------|--------|-------|
| Private key committed | ✅ PASS | Never occurred |
| Private key in logs | ✅ PASS | Uses `mktemp` + no echo |
| Temp file cleanup | ✅ PASS | `trap 'rm -f' EXIT` |
| No admin tokens | ✅ PASS | Uses repo-scoped `FORGEJO_TOKEN` |
| Helper has no secrets | ✅ PASS | Only public key + openssl |

**VERIFICATION STATUS: ✅ PASS**

---

## SECTION 4: CORRECTNESS ANALYSIS

| Check | Status | Evidence |
|-------|--------|----------|
| Additive-only | ✅ PASS | Cosign steps added, keyless unchanged |
| Signing covers all artifacts | ✅ PASS | wheel, sdist, manifest, hashes |
| CI verification passes | ✅ PASS | 5× "Verified OK", 9 assets |
| Customer helper correct | ✅ PASS | Uses only public key |

**VERIFICATION STATUS: ✅ PASS (for Option B)**

---

## SECTION 5: BLOCKING ISSUE FOR OPTION A

The core problem preventing G3 approval for the documented Option A path:

**Rekor is a hard dependency for sigstore keyless signing**

From `sigstore/sign.py`:
```python
entry = self._signing_ctx._rekor.log.entries.post(proposed_entry)  # ALWAYS
```

And from `sigstore/verify.py`:
```python
actual_body = rekor_types.Hashedrekord.model_validate_json(entry.body)
# Must match expected_body
```

**No option to disable Rekor** in sigstore 3.x.

**Verified state of Trillian/Rekor:**
- Rekor v1 images require Trillian server (no pullable image)
- Tessera (Rekor v2 backend) is unreleased: "Rekor v2 will be backed by... Tessera" (sigstore/rekor README)
- No Docker image exists for either

**Therefore: Option A CANNOT BE DEPLOYED** in this environment.

---

## SECTION 6: FINAL RECOMMENDATION

### For the CTO (G4):

1. **Clarify the actual intent:**
   - If Option A (Fulcio) is still desired, Rekor/Tessera infrastructure must be deployed first
   - If Option B (Cosign) is acceptable, approve that path with corrected documentation

2. **The cosign-public.pem is the authoritative public key** for customer verification. It covers:
   - All releases from v0.4.5 onward
   - Verification via `openssl dgst -sha256 -verify cosign-public.pem -signature <artifact>.sig <artifact>`
   - Customer helper at `tools/verify_cosign.sh`

3. **Remove COSIGN_PROBE step** before G4 approval

### For the Implementer:

If proceeding with Option B:
- Update all task documentation to reflect "Option B (Cosign key-based)" 
- The keyless Sigstore path remains non-functional but must be preserved (per AC#6)
- Document that Fulcio path will be activated later when Rekor is available

---

## VERIFICATION CHECKLIST

### Security ✅
- [x] Private key never committed
- [x] Private key not echoed in logs  
- [x] Proper temp file cleanup
- [x] No admin tokens used
- [x] Customer helper has no secrets

### Correctness ✅
- [x] Additive-only changes
- [x] CI verification passed (5× Verified OK)
- [x] All artifacts signed and verified

### Blocking Issues 🛑
- [x] **Option A BLOCKED** — Rekor infrastructure missing
- [ ] COSIGN_PROBE should be removed

---

## GATE STATUS RECOMMENDATION

**G3 Status: ⚠️ CONDITIONAL APPROVAL**

Approve **with the understanding that**:
1. Option B (Cosign) is the actual implemented and shippable path
2. Option A (Fulcio) is blocked by missing Rekor infrastructure
3. Documentation must be corrected to reflect actual implementation
4. COSIGN_PROBE must be removed before G4

**Without addressing these issues, G3 approval cannot be granted for the documented Option A path.**

---

## NEXT STEPS

1. **CTO Decision Required:**
   - Choose: Option A (deploy Rekor first) OR Option B (proceed with Cosign)
   - Either: Update documentation to match reality

2. **Cleanup Required:**
   - Remove COSIGN_PROBE step
   - Update GATE_STATUS.md to reflect actual state

3. **If choosing Option B:**
   - Commit corrected documentation
   - Update LOCK.md scope
   - Proceed to G4

---

*Review complete.*  
*Reviewer: 🔍 (ollama/laguna-xs-2.1:q4_K_M)*

---

**APPENDIX: Key Evidence File Locations**

| File | Purpose |
|------|---------|
| `G2_BLOCKER_EVIDENCE.md` | Proves Option A blocked by Rekor |
| `G2_COMPLETION_EVIDENCE.md` | Shows Option B implemented + CI passed |
| `.github/workflows/release-sigstore.yml` | Workflow with both paths |
| `cosign-public.pem` | Committed public key |
| `tools/verify_cosign.sh` | Customer verification helper |