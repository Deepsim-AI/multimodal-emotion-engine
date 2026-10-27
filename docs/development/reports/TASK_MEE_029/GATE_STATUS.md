# TASK_MEE_029 — Gate Status

**Task ID:** TASK_MEE_029
**Title:** Fulcio Keyless Release Signing Deployment (Option A from MEE_025_A POC)
**Date:** 2026-10-26 (PDT)
**Supersedes:** original G1 plan (Option B / Cosign) — owner 2026-10-26 corrected the technical premises.

## Current Gate Status

| Gate | Status | Artifacts Present | Notes |
|------|--------|-------------------|-------|
| G0 | ✅ Complete | G0_INTAKE_CHECKLIST.md, LOCK.md, RELEASED.md | Intake complete; lock released by CTO |
| G1 | ✅ Approved | G1_PLAN/CTO_TASK_PLAN.md | CTO plan (Option A) approved — exact file/line guidance |
| G2 | ✅ Complete (Option B) + CI verified | G2_COMPLETION_EVIDENCE.md §7, G2_KEY_PROTECTION.md, cosign-public.pem, tools/verify_cosign.sh | Cosign key-based signing implemented + validated. **CI pipeline verified 2026-10-27 (task 38): build → sign → verify (5× Verified OK) → release v0.4.5 → 9 assets uploaded.** |
| G3 | ⏳ Pending | — | Reviewer verification (production signing change — highest scrutiny) |
| G4 | ⏳ Pending | — | CTO approval (owner + security sign-off required) |
| G5 | ⏳ Pending | — | PM closure |

## Authorization

**Parent task: TASK_MEE_025_A** (signed POC, CLOSED G5 2026-10-26).
Owner 2026-10-26 selected **Option A (Fulcio keyless + OIDC)** over Option B (Cosign) after correcting
two incorrect premises in the original G1 plan (see Correction Record in G1 plan).

## Critical Constraints (from MEE_025_A POC + owner 2026-10-26)

- **Owner 2026-10-26: Option A (Fulcio keyless + OIDC) selected.** The original G1 had chosen Cosign
  on two incorrect premises, now corrected:
  - Forgejo Actions **does** have native OIDC (Gitea 1.22.0 `id-token: write`). Forgejo at
    `17.0.0+gitea-1.22.0`; the current `release-sigstore.yml` already uses `id-token: write` (line 12).
  - Rekor no longer requires Trillian — **Tessera** (file-based, ARM64-compatible) is production-ready.
- Fulcio: self-hosted CA (HSM/TPM-backed root key preferred for production; pilot: encrypted volume + rotation).
- Rekor: host via **Tessera** (file-based, ARM64-compatible), not Trillian.
- Forgejo Actions OIDC (`id-token: write`) is the identity provider for Fulcio.
- Customer impact: distribute new Fulcio root (trust bundle update) via CHANGELOG/release notes.
- Both signing paths (public Fulcio + self-hosted Fulcio) remain **parallel** during migration — no breakage.

## Recommendation

Proceed to G2: implementer deploys Fulcio keyless signing into `release-sigstore.yml` (additive
parallel path). Highest-risk task in the pipeline (production signing). Reviewer scrutiny at G3 must
be proportionate to that risk.

---
*End of gate status.*
