# TASK_MEE_029 — G4 CTO Approval

**Task ID:** TASK_MEE_029  
**Title:** Cosign Key-Based Release Signing (Option B)  
**Date:** 2026-10-27 (PDT)  
**Approver:** 🏗️ CTO (ollama/qwen3.6:35b)

---

## G4 Decision: APPROVED

This task is **approved as Option B (Cosign key-based)** — the final and operational signing path from v0.4.5 onward.

### Formal Adoption of Option B

The CTO hereby adopts **Option B** as the authoritative signing method for this task:

- **Algorithm:** ECDSA P-256 (prime256v1) with SHA-256
- **Tool:** `openssl dgst -sha256 -sign/verify` — no external dependencies, no network required
- **Key storage:** Forgejo secret `COSIGN_PRIVATE_KEY` (never committed)
- **Public key:** `cosign-public.pem` at repo root + release assets (distributable to customers)
- **Customer verification:** `tools/verify_cosign.sh <artifact>` — offline, `openssl` only

### Option A Status: BLOCKED — Deferred

Option A (Fulcio keyless + OIDC) is **not approved for this task** because its core dependency is unavailable:

| Requirement | Status |
|-------------|--------|
| Fulcio CA chain generated | ✅ Done (`/opt/fulcio-ca/` on VPS) |
| Forgejo OIDC issuer confirmed | ✅ Confirmed |
| Rekor server deployable | ❌ **BLOCKED** — no pullable Trillian image; Tessera unreleased |

Option A will require a **separate future task**, gated on:
1. Verified Rekor server image for this environment (or Tessera when released)
2. Runner egress to self-hosted Rekor
3. Fulcio OIDC issuer allowlist configuration

This task does **not** resolve the Option A blocker. Closing MEE_029 with Option B is correct and complete.

### Implementation Verification

| Check | Result |
|-------|--------|
| Additive-only change to `release-sigstore.yml` | ✅ Verified — keyless path byte-for-byte unchanged |
| Cosign signing covers all artifacts (wheel, sdist, manifest, hashes) | ✅ CI verified 5× "Verified OK" |
| Private key never committed | ✅ Only public key in repo |
| Customer verification works offline | ✅ `tools/verify_cosign.sh` tested |
| Both paths coexist — no customer breakage | ✅ Confirmed |
| Key protection documented (rotation + recovery) | ✅ `G2_KEY_PROTECTION.md` complete |
| CHANGELOG entry present and accurate | ✅ Written, reflects Option B |

### Security Assessment

| Concern | Status | Notes |
|---------|--------|-------|
| Long-lived signing key exposure | ⚠️ **Medium residual risk** (per MEE_025_A POC) | Key stored as Forgejo secret; rotation documented in G2_KEY_PROTECTION.md §5. Mitigated by: repo-scoped FORGEJO_TOKEN, temp-file isolation with `trap` cleanup, no log leakage. Acceptable until Rekor infrastructure is available. |
| Key theft → unauthorized releases | ⚠️ **Medium** | Only Forgejo secret holders can sign. If compromised: rotate per G2_KEY_PROTECTION.md §5; revoke old cosign-public.pem; issue new release with updated key. Public key update distributed via CHANGELOG and release assets. |
| No transparency log entry | ⚠️ **Low for Option B** | Rekor transparency is the exact benefit of Option A. Option B sacrifices this for deployability. If audit-trail is required, add as separate follow-on task. |

**Verdict:** Security posture is acceptable for production use. The medium residual risk is documented and mitigated. The trade-off (signing key vs. no transparency) is an engineering decision for future prioritization, not a blocker for this deployment.

### Pre-G4 Cleanups Verified ✅

1. **COSIGN_PROBE step removed** — `72bb5e8 chore(MEE_029): remove COSIGN_PROBE temporary step`
2. **GATE_STATUS.md corrected** — `f375fca docs(MEE_029): correct GATE_STATUS.md to reflect final Option B state and document Option A blocker`

Both cleanups committed on `master`. No further changes required before G5 handoff.

### Post-G4 Items (PM Responsibility)

- [ ] Update `PROJECT_STATUS.md` — mark MEE_029 as closed, Option B live from v0.4.5
- [ ] Verify CHANGELOG entry is accurate and customer-facing
- [ ] Send `PM_CLOSED` notification for TASK_MEE_029
- [ ] Ensure public key rotation procedures are known by the team

---

*Approved by 🏗️ CTO, 2026-10-27 (PDT)*  
*Option B adopted as the final signing path for this task.*  
*Option A deferred pending Rekor infrastructure.*
