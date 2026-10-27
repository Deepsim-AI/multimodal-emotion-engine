# TASK_MEE_029 — Gate Status

**Task ID:** TASK_MEE_029
**Title:** Cosign Key-Based Release Signing (Option B) — Final State
**Date:** 2026-10-27 (PDT)
**Supersedes:** G1 plan (which specified Option A / Fulcio keyless)

## Current Gate Status

| Gate | Status | Artifacts Present | Notes |
|------|--------|-------------------|-------|
| G0 | ✅ Complete | G0_INTAKE_CHECKLIST.md, LOCK.md, RELEASED.md | Intake complete; lock released by CTO |
| G1 | ✅ Approved (with correction) | G1_PLAN/CTO_TASK_PLAN.md | G1 plan approved but Option A was later proven un-deployable (see below) |
| G2 | ✅ Complete (Option B) + CI verified | G2_COMPLETION_EVIDENCE.md §7, G2_KEY_PROTECTION.md, cosign-public.pem, tools/verify_cosign.sh | Cosign key-based signing implemented + validated. **CI pipeline verified 2026-10-27 (task 38): build → sign → verify (5× Verified OK) → release v0.4.5 → 9 assets uploaded.** |
| G3 | ✅ Approved | REVIEW_REPORT.md, G3_REVIEW_PACKAGE.md | **Conditional approval** — approve Option B implementation; documentation must be corrected (see below); COSIGN_PROBE removed (post-G3 cleanup) |
| G4 | ✅ Approved | CTO_APPROVAL.md (pending write) | See CTO assessment above — approved with required cleanup items completed |
| G5 | ⏳ Pending | — | PM closure (update PROJECT_STATUS.md, CHANGELOG, send PM_CLOSED) |

## Historical Context: Option A Blocked → Pivoted to Option B

**Parent task:** TASK_MEE_025_A (signed POC, CLOSED G5 2026-10-26).

Owner initially selected **Option A (Fulcio keyless + OIDC)** on 2026-10-26. However, the Implementer's G2 investigation discovered that Option A is **not deployable** in this environment:

| Premise (from original G1) | Verified Reality |
|---------------------------|------------------|
| Forgejo Actions has native OIDC (`id-token: write`) | ✅ TRUE — confirmed on forge.deepsim.ai |
| Rekor/Tessera is production-ready, ARM64-compatible | ❌ **FALSE** — Rekor v1 requires Trillian (no pullable image); Tessera/Rekor-v2 is unreleased per sigstore/rekor README |

Without a reachable Rekor log, the entire Fulcio keyless path in sigstore 3.x is **inoperable**:
- Sign fails at `sigstore/sign.py:_finalize_sign()` — always POSTs to Rekor
- Verify fails at `verify/verifier.py` — always compares bundle against Rekor entry
- No public Rekor reachable from the runner's current network segment

**Result:** G2 blocked on Rekor. Owner pivoted to **Option B (Cosign key-based)**, which:
- Uses ECDSA P-256 + SHA-256 via `openssl dgst -sign/verify`
- Requires no Rekor, no transparency log, no external network from the runner
- Was proven in MEE_025_A POC (previously closed G5)
- Is deployed as an **additive/parallel path** to the existing keyless Sigstore — zero customer breakage

## Implementation Summary (Option B — Final State)

### What was delivered:
| Item | Status | Details |
|------|--------|---------|
| Additive Cosign signing step in `release-sigstore.yml` | ✅ Deployed | EC P-256 sign for all 4 artifacts (wheel, sdist, manifest, hashes) |
| CI self-check verification step | ✅ Deployed | 5× "Verified OK" in task 38 |
| Public key committed (`cosign-public.pem`) | ✅ Committed | EC P-256 SPKI format at repo root + release assets |
| Customer verification helper (`tools/verify_cosign.sh`) | ✅ Deployed | Offline, `openssl` only, exit codes: 0=PASS, 1=FAIL, 2=ERROR |
| Key protection doc (`G2_KEY_PROTECTION.md`) | ✅ Written | Rotation (§5), recovery (§6), supply-chain analysis (§7) |
| CHANGELOG entry | ✅ Written | Customer-facing — explains what changed, no customer action required |
| Keyless Sigstore path (unchanged) | ✅ Verified byte-for-byte identical | No breakage to existing releases |
| COSIGN_PRIVATE_KEY secret | ✅ Configured in Forgejo | Verified in CI probe #19 and task 38 |

### What was cleaned up:
- COSIGN_PROBE temporary step removed from `release-sigstore.yml`
- cosign-probe.yml workflow deleted
- Probe tags (`v0.0.0-probe-task-mee-029*`) deleted from Forgejo

## Current State of Option A (Fulcio Keyless)

**Status: BLOCKED — pending Rekor infrastructure.**

| Requirement | Status | Notes |
|-------------|--------|-------|
| Fulcio CA chain generated | ✅ Done | On VPS at `/opt/fulcio-ca/` (inert, no service running) |
| Forgejo OIDC issuer configured | ✅ Confirmed | `https://forge.deepsim.ai:8443` returns full OIDC metadata |
| Rekor server deployable | ❌ **BLOCKED** | No Trillian image; Tessera unreleased |
| Fulcio-to-Rekor path functional | ❌ BLOCKED (depends on above) | Cannot sign without Rekor entry |

**Recommendation:** Treat Option A as a **separate future task**, gated on:
1. A verified, pullable Rekor server image for this environment (or Tessera when released)
2. Runner egress to the self-hosted Rekor (current isolated `WORKFLOW-*` networks must reach it)
3. Fulcio OIDC issuer allowlist configuration

**Option B is the operational signing path from v0.4.5 onward.** Both paths coexist during migration; Option A may be activated later when the dependency is resolved.

## Release Status

- **Latest release:** v0.4.5 (Forgejo release ID 21)
- **URL:** `https://forge.deepsim.ai:8443/deepsim/multimodal-emotion-engine/releases/tag/v0.4.5`
- **Assets:** 9 files (wheel, sdist, 2× .sig, manifest, hashes, 2× manifest/hashes .sig, cosign-public.pem)
- **All signatures verified in CI:** ✅ 5× "Verified OK"

---
*Last updated: 2026-10-27. Task pending G5 closure.*
