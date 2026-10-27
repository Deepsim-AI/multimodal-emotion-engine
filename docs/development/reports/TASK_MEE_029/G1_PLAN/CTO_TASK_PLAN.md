# G1 TASK PLAN — TASK_MEE_029: Fulcio Keyless Release Signing Deployment (Option A)

**Task ID:** TASK_MEE_029
**Gate:** G1 — CTO Plan (implementation of Option A, superseding the original Option B plan)
**Date:** 2026-10-26 (PDT)
**Author:** CTO 🏗️ (qwen3.6:35b)
**Parent:** TASK_MEE_025_A (Option A selected by owner 2026-10-26)
**Scope:** Implementation task. Deploys Fulcio keyless signing into the release pipeline.
**Risk:** **HIGH** — production signing change. Highest-scrutiny G3 review.

---

## 0. Correction Record (supersedes original G1)

The original MEE_029 G1 plan chose Option B (Cosign key-based) based on two incorrect premises.
Owner 2026-10-26 corrected both; this plan implements **Option A (Fulcio keyless + OIDC)**:

| Claim (original, now superseded) | Corrected fact (2026-10-26) |
|----------------------------------|-----------------------------|
| Forgejo Actions lacks native OIDC (v17.0.0+gitea-1.22.0) | **Gitea 1.22.0 added native OIDC** (`id-token: write`). Forgejo at `17.0.0+gitea-1.22.0`. The current `release-sigstore.yml` already uses `id-token: write` (line 12). |
| Rekor requires Trillian (not ARM64-available) | **Tessera** (file-based, lightweight) is a production-ready ARM64-compatible Rekor alternative. No Trillian needed. |

---

## 1. Objective

Deploy **Fulcio keyless signing** (Option A): Forgejo Actions OIDC identity → self-hosted Fulcio CA
→ Sigstore bundle → public Rekor (via Tessera). Ephemeral, identity-bound signing keys — no
long-lived signing key to compromise. Additive/parallel to the current keyless Sigstore path during
migration; no customer breakage.

---

## 2. Acceptance Criteria

| # | AC | Verification |
|---|----|--------------|
| 1 | Self-hosted Fulcio CA operational (root cert serves) | `/.well-known/future-certificate-chain.json` / root cert responds |
| 2 | Forgejo Actions OIDC (`id-token: write`) supplies identity to Fulcio | OIDC token exchange tested in CI |
| 3 | Fulcio signs ephemeral cert bound to Forgejo OIDC identity | Test release signed + verified against self-hosted root |
| 4 | Rekor (Tessera) accepts log entries on ARM64 | `POST /api/v1/logEntries` succeeds; `GET /api/v1/logEntry/byHash` resolves |
| 5 | Customer can verify a Fulcio-signed release against the new root | `sigstore verify --trust-root` PASS |
| 6 | Both signing paths coexist during migration (no breakage) | Existing Sigstore verify still PASS; new Fulcio verify PASS |
| 7 | Root key protection documented (HSM/TPM preferred) | KEY_PROTECTION.md updated for Option A |

---

## 3. Implementation Plan (exact guidance)

### Task 1: Fulcio CA deployment (510a1b1)
- **Component:** Self-hosted Fulcio CA on the VPS (forge.deepsim.ai).
- **Root key:** HSM-backed or TPM-backed root key preferred for production. For pilot: encrypted volume
  with LUKS + automated rotation script (manual review at each rotation).
- **Chain:** Self-signed root CA → intermediate CA per Fulcio instance. Root key never leaves HSM;
  intermediate signing key loaded/unloaded for sign operations.
- **Endpoint:** Fulcio serves `/.well-known/future-certificate-chain.json`; OIDC issuer config at
  `/.well-known/openid-configuration` pointing to Forgejo's OIDC issuer.
- **File:** Fulcio deployed via container/image on the VPS (infrastructure, not in MEE repo).

### Task 2: Rekor deployment via Tessera (520a2b1)
- **Component:** Self-hosted Rekor on the VPS, **backed by Tessera** (file-based, ARM64-compatible).
- **Resource:** ~100 MB RAM, SSD for log storage. Log retention: infinite append-only.
- **Endpoints:** `POST /api/v1/logEntries` (append); `GET /api/v1/logEntry/byHash/{hash}` (verify).
- **Transport:** HTTPS + mTLS for CI runner writes.
- **File:** Rekor/Tessera deployed via container on the VPS (infrastructure, not in MEE repo).

### Task 3: Forgejo Actions OIDC wiring (530a3b1)
- **Component:** Forgejo Actions issues OIDC tokens via `id-token: write` (already enabled line 12).
- **Config:** Fulcio's OIDC issuer config points to Forgejo's OAuth2 provider (`https://forge.deepsim.ai:8443/oauth2/`).
- **Audience:** set Fulcio audience claim to `fulcio`.
- **Scope:** This is the identity provider — no external OIDC issuer needed (Gitea 1.22 native OIDC).

### Task 4: Update release-sigstore.yml (540a4b1)
- **File:** `.github/workflows/release-sigstore.yml`
- **Change:** Add Fulcio keyless signing step (after anchor-embed, before bundle attachment) using
  `sigstore sign --issuer <fulcio-oidc> --root-ca <self-hosted-root>` so bundles carry the self-hosted
  Fulcio chain-of-trust.
- **Parallel:** Keep the existing keyless Sigstore path intact during migration.

### Task 5: Customer trust-bundle migration (550a5b1)
- **Change:** Distribute the self-hosted Fulcio root cert to customer verification config.
- **Path:** `sigstore verify github --trust-root <self-hosted-fulcio-root>` (new flag) OR keep old
  public-Fulcio trust path for v0.4.x releases (parallel for ≥12 months).
- **Doc:** Document in `HUB_CUSTOMER_GUIDE.md` + CHANGELOG.md.

### Task 6: Verification (560a6b1)
- **Test:** sign one release with self-hosted Fulcio; bundle verifiable against self-hosted root.
- **Parallel:** verify v0.4.5 (public Fulcio) still works during migration window.
- **Manual:** run `tools/verify_release.sh` on both paths.

---

## 4. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Root key compromise | High | HSM/TPM-backed root; intermediate key rotation; revoke + rotate via CRL to Rekor |
| Customer trust-bundle migration (breaking) | High | Parallel signing path for ≥12 months; documented migration window |
| Rekor/Tessera single point of failure | Medium | At least one public Rekor mirror |
| OIDC identity spoofing | Medium | Forgejo OIDC + mTLS to Fulcio; certificate-identity binding |
| Production signing change | High | Parallel path + CI self-check fail-fast; full rollback (disable Fulcio step) |

---

## 5. Rollback

- Disable the Fulcio signing step in `release-sigstore.yml` (revert to existing keyless Sigstore path).
- Self-hosted Fulcio/Rekor/Tessera remain deployed but unused; no impact on existing releases.
- Customer trust-bundle migration is opt-in (old public-Fulcio path preserved during migration).

---

## 6. Reviewer Scrutiny (G3) — PROPORTIONATE TO RISK

Reviewer MUST verify:
1. Fulcio CA root key is HSM/TPM-backed (or documented encryption + rotation for pilot).
2. Forgejo OIDC identity binding is correct (`id-token: write` → Fulcio certificate-identity).
3. Tessera Rekor is ARM64-compatible and log append/verify works.
4. Both signing paths coexist during migration; no customer breakage.
5. Customer trust-bundle migration path documented (parallel ≥12 months).
6. No scope creep — no mirror/signing/permission changes outside release-sigstore.yml + CHANGELOG.
7. Rollback path verified (disable Fulcio step → existing path intact).

---

## 7. Owner Decisions Needed

1. **Fulcio root key storage:** production HSM/TPM, or pilot (encrypted volume + rotation)?
2. **Migration window:** ≥12 months parallel (recommended) or shorter?
3. **Public Rekor mirror:** enable a second Rekor mirror for availability?
4. **Which release** gets the first Fulcio-signed artifact (next RC or a test release)?

---

*Plan complete. Awaiting CTO final approval (G4) + owner security sign-off before G2 deployment.*
