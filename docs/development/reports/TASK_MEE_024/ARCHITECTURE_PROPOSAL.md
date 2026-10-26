# CTO Architecture Proposal - Deepsim Platform Independence Strategy

**Task ID:** TASK_MEE_024  
**Gate:** G1 Planning (architecture proposal only)  
**Date:** 2026-10-26  
**Author:** CTO (ollama/qwen3.6:35b)  
**Status:** Proposal - no implementation, no changes to production  

---

## Executive Summary

This proposal addresses the strategic direction to make Deepsim's release infrastructure
independently operable - reducing long-term dependence on GitHub Actions + public Sigstore
for release signing and package distribution. It evaluates migration paths for:

1. Canonical repository and release architecture (Forgejo as source of truth, GitHub as mirror)
2. Independent release signing (self-hosted Fulcio/Rekor vs key-based Cosign vs retained GitHub/Sigstore)
3. MEE v0.4.4 signing defect (documented as a bounded issue, separate from this proposal)
4. Hub PyPI routing (proposed as a verification hypothesis, not implementation)

---

## 1. Canonical Repository and Release Architecture

### 1.1 Proposed Component Responsibilities

| Component | Responsibility | Justification |
|-----------|---------------|---------------|
| **Forgejo** (forge.deepsim.ai:8443) | Source of truth for source code, branches, tags, release metadata, release assets, and package storage (PyPI + OCI) | Currently operational (v17.0.0+gitea-1.22.0), already hosts MEE PyPI packages, supports artifact upload APIs |
| **GitHub** (github.com/Deepsim-AI/) | Mirror for explicitly approved open-source repos only; NOT a release authority for private/commercial code | Current state: v0.4.4+ signed releases published here; mirror must remain in sync but never be the signing origin |
| **Hub Portal** (hub.deepsim.ai:8443) | Customer-facing distribution portal (static HTML + PyPI simple index gateway) - NOT a package authority itself | Currently serves static portal pages + proxies /api/packages/ to Forgejo storage; correct abstraction layer for customers |
| **Keygate** (licenses.deepsim.ai:8443) | License management - runtime key validation, activation, licensing policy enforcement | Decoupled from distribution; no changes needed here |

### 1.2 Source of Truth Matrix (Proposed)

| Asset Type | Source of Truth | Mirror/Replica | Notes |
|------------|-----------------|---------------|-------|
| Repository history + branches/tags | **Forgejo** (primary), GitHub (mirror) | Bidirectional sync via webhook | One-way push: Forgejo to GitHub for approved repos only |
| Release metadata (tag, name, body) | **Forgejo** | Mirror to GitHub Releases | Forgejo API v1 /repos/{owner}/{repo}/releases supports full release creation |
| Release assets (wheel, sdist, bundles) | **Forgejo's package storage** | Manual mirror to GitHub Releases for approved public repos | Automated via post-release hook on Forgejo side |
| Package registry (PyPI simple index) | **Forgejo PyPI plugin** (/api/packages/deepsim/pypi/simple/) | None currently - Hub simply proxies | Hub serves the simple index but download links point to Forgejo storage URLs |
| OCI images | **Forgejo Container Registry** | None | Currently operational (test image verified: deepsim/hub-test:0.1.0) |
| Sigstore bundles | **Forgejo release assets** + **public Rekor** | Public transparency log (unchanged) | Bundles uploaded as release artifacts; verification against public Rekor is sufficient for trust |

### 1.3 GitHub Mirror Maintenance Strategy

**Principle:** GitHub mirrors are ONE-WAY from Forgejo to GitHub, only for approved repos.

| Mechanism | Implementation | Risk Mitigation |
|-----------|---------------|-----------------|
| **Push trigger** | Forgejo webhook on push events - git push --mirror to GitHub remote URL stored in Forgejo's app.settings.ini | Mirror failure logs + alert; never allow GitHub to Forgejo sync (one-way only) |
| **Release sync** | Post-release hook (release.created webhook event) - gh release create/gh release upload on GitHub with assets from Forgejo release assets API | Idempotent uploads with --clobber; asset hash comparison before upload to detect drift |
| **Auth** | Dedicated mirror bot token (write access only, no admin); stored in Forgejo as a service account credential | Token scoped: repo + read:packages; never admin:org or delete_repo |

### 1.4 Migration Risks and Rollback

| Risk | Mitigation | Rollback Path |
|------|-----------|---------------|
| Mirror lag causes divergence between Forgejo and GitHub | Implement mirror lag monitoring; enforce maximum acceptable sync delay (e.g., less than 5 min) | Manual git push --mirror from Forgejo to GitHub |
| Accidental publication of private/commercial repo to GitHub | Require explicit approval gate before adding a repo to the mirror list | Remove from mirror list immediately; audit webhook logs for unauthorized pushes |
| Forgejo PyPI API incompatibility with pip | Maintain pip-compliant simple index format; test with pip install --dry-run after any migration step | Revert nginx proxy to direct to old registry (if applicable); temporarily enable public PyPI fallback |

### 1.5 Minimum Viable Pilot

**Candidate repo:** Deepsim-AI/multimodal-emotion-engine - ideal because:
- Already published signed releases to GitHub (v0.4.5 exists)
- Hub PyPI packages currently stored in Forgejo already
- MEE_022 CI fix ensures bundles are correctly attached now
- Small enough for controlled pilot, large enough for a realistic test

**Pilot scope:** Mirror v0.4.5 and later releases from Forgejo to GitHub only (no tag push, no branch sync). Verify customer pip install still works via both paths.

---

## 2. Independent Release-Signing Architecture

### 2.1 Current State (Verified Facts)

| Component | Current Status | Notes |
|-----------|---------------|-------|
| OIDC identity provider | **GitHub Actions** (public, external) | Runner OIDC token to Fulcio; trust rooted in GitHub's PKI |
| Fulcio CA | **Public Sigstore Fulcio** (fulcio.sigstore.dev) | External dependency; Deepsim has zero control |
| Transparency log | **Sigstore Rekor public** (multiple mirrors) | External dependency; Deepsim has zero control |
| Signing key type | **Ephemeral keys** (Fulcio certificate-bound) | No long-lived signing key exists; each release gets a new key bound to the OIDC identity |
| Customer verification | sigstore verify github --repository Deepsim-AI/multimodal-emotion-engine | Verifies against public Fulcio CA + Rekor; trust in GitHub's OIDC issuer |

### 2.2 Option A: Self-Hosted Fulcio + Rekor (Preferred Target)

#### Architecture

```
+------------------------------------------------------+
|              Forgejo Actions Runner                    |
|                                                      |
|  git push -> v*.*.* --trigger--> CI pipeline         |
|                                        |             |
|                           build wheel+sdist            |
|                           generate MEE_RELEASE_MANIFEST.json
|                           embed integrity anchor        |
|                                        |             |
|                          +-------------+             |
|                          |               |           |
|                       Self-hosted Fulcio CA      |
|                 (local PKI or HSM-backed)          |
|                                                      |
|    Fulcio signs ephemeral certificate            |
|   bound to Forgejo OIDC identity                   |
|          |                                        |
|          v                                        |
|     Sigstore bundle (.sigstore.json)              |
|        +---+---+----------+                       |
|        v      v          v                        |
|   Release  Public    Customer                     |
|  Assets    Rekor     Verify                       |
|                                      |            |
+--------------------------------------|------------+-->
                                         v
                            sigstore verify
                            --repository Deepsim-AI/multimodal-emotion-engine
```

#### Fulcio CA Key Protection

| Concern | Recommendation |
|---------|---------------|
| CA private key storage | **HSM-backed or TPM-backed** - never store PEM on disk. Use Cloud HSM, AWS KMS, or a YubiHSM2/NetHSM appliance for production. For pilot: encrypted volume with LUKS + automated rotation script (manual review at each rotation). |
| Key generation | Self-signed root CA - intermediate CA per Fulcio instance; certificate signed with intermediate key |
| Operational security | Root key never leaves the HSM. Intermediate signing key can be loaded/unloaded as needed for sign operations. Access restricted to CI runner service account with mTLS mutual auth to Fulcio API. |

#### OIDC Identity Provider

Forgejo has built-in OIDC support (app.settings.ini - oauth2). We need:
1. **Forgejo acts as the OIDC issuer** - configure Forgejo's OAuth2 provider to issue tokens with claims that Fulcio accepts (repository, ref, workflow, trigger event).
2. **Fulcio trusts Forgejo as a certificate authority** - configure Fulcio's .well-known/openid-configuration issuer to point to https://forge.deepsim.ai:8443/oauth2/.
3. **Forgejo OIDC audience** - set to `fulcio` (standard Fulcio audience claim).

#### Trust Model

```
Customer verifier --trusts--> Public Rekor mirrors + known Fulcio root CA cert
                                        |
                         Self-hosted Fulcio root cert must be
                         distributed to customers via:
                           1. Sigstore trust-root update mechanism
                           2. Pre-bundled in customer verification tooling
                           3. Trusted key IDs (not full certs - rotation-friendly)
```

**Key challenge:** Customers currently trust the public Fulcio CA automatically (via sigstore-go's built-in trust bundle). Moving to self-hosted Fulcio requires distributing a **new root certificate or key ID** to all customers' verification tooling. This is the primary migration friction point.

#### Transparency Log (Rekor)

| Concern | Recommendation |
|---------|---------------|
| Instance deployment | Single Rekor instance on the same VPS as Forgejo (resource requirements: about 100MB RAM, SSD for log storage) |
| Mirroring | Configure at least one public Rekor mirror (e.g., hosted elsewhere or in another datacenter) to avoid single-point-of-failure |
| Retention | Infinite append-only; monitor disk usage growth over time. Current MEE bundle count is negligible but grows per release. Estimate: about 10KB per bundle times 2 bundles/release = 20 KB/release. At 6 releases/year, about 120 KB/year - trivial. |
| Availability | Rekor serves both GET /api/v1/logEntry/byHash/{entryHash} and POST /api/v1/logEntries (append). Must support HTTPS + mTLS for CI runner writes. |

#### Trust-Root Distribution and Rotation

This is the hardest part of self-hosted Fulcio:

| Phase | Action |
|-------|--------|
| **Initial trust** | Publish self-hosted Fulcio root certificate fingerprint to customer verification config; require explicit opt-in until a migration window |
| **Rotation** | New key pair - submit new root cert fingerprint to transparency log - announce migration via CHANGELOG.md + customer channel. Old cert kept in trust bundle for N months during transition. |
| **Key compromise** | Revoke intermediate CA certificate (via CRL published to Rekor) - issue new intermediate CA signed with fresh root - customers update trust root. Time-to-remediation: hours if automated, days if manual. |

#### Customer Verification Path

Current customer verification after migration:

```bash
# Before migration: works out of the box (public Fulcio in sigstore-go trust bundle)
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --name release-sigstore-sign \
  --bundle multimodal_emotion_engine-0.4.5-py3-none-any.whl.sigstore.json \
  multimodal_emotion_engine-0.4.5-py3-none-any.whl

# After migration: requires explicit trust root configuration
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --name release-sigstore-sign \
  --trust-root <path-to-self-hosted-fulcio-root> \   # NEW
  --bundle ... \
  multimodal_emotion_engine-0.4.5-py3-none-any.whl
```

**Impact:** This is a breaking change for existing customers. They must either:
1. Update their `sigstore` trust bundle to include the self-hosted Fulcio root, OR
2. Accept that v0.4.x releases (signed with public Fulcio) require the old trust path, while v0.5.0+ uses self-hosted.

**Recommendation:** Maintain BOTH signing paths in parallel for at least 12 months - continue using public Fulcio for existing releases AND enable self-hosted Fulcio for new releases. This avoids customer migration friction.

#### CI/CD Integration with Forgejo Actions

Forgejo 17 (gitea-1.22) supports Actions-compatible workflows but **does NOT have native OIDC token issuance** like GitHub Actions. We need:

| Requirement | Solution |
|-------------|----------|
| OIDC token for Fulcio | Run a lightweight OIDC issuer in the runner environment, or use tink/oidc-agent to generate short-lived tokens from Forgejo's OAuth2 provider |
| Workload identity binding | Configure Fulcio to accept Forgejo's OIDC token claims as valid identity (matching workflow release-sigstore-sign, repo Deepsim-AI/multimodal-emotion-engine) |
| Alternative: Cosign with static key | Use cosign with a pre-generated ECDSA key pair stored in Forgejo secrets. This avoids the OIDC dependency entirely but trades ephemeral keys for long-lived signing keys (lower security posture). |

**Important:** Forgejo Actions **does NOT have an equivalent to GitHub's `id-token: write` permission** that automatically provides an OIDC identity token. This is a fundamental gap compared to GitHub Actions.

#### Option A Assessment

| Pros | Cons |
|------|------|
| Full cryptographic independence from external providers | Significant operational complexity (HSM/TPM management, trust root distribution, rotation) |
| No dependency on GitHub for signing infrastructure | Forgejo Actions lacks native OIDC support - requires workarounds |
| Complete control over transparency log and CA | Breaking change for customers: trust bundle migration required |
| Long-term strategic alignment with Deepsim platform goals | **Highest effort, highest risk** option |

### 2.3 Option B: Key-Based Cosign (Fallback)

Use `cosign` with a long-lived ECDSA key pair stored in Forgejo secrets as the signing identity.

```
+----------------------+         +-----------------------------+
|  Forgejo CI Runner   |         |  Sigstore Rekor             |
|                      |  PUT    |  (public transparency)      |
|  cosign sign artifact-----------+                            |
+----------------------+         +-----------------------------+
         |                               |
         v                               v
   .sigstore.json                 Bundle in Rekor
   uploaded as                   (verified offline
    release asset                by anyone)
```

**Key protection strategy:**
- ECDSA P-256 key pair stored in Forgejo's secret management (/settings/secrets)
- Access limited to CI service account (not human-readable)
- Key rotation every 12 months via Forgejo secret update + announce to customers
- **NOT encrypted at rest** (Forgejo secrets are stored encrypted with app.secret, which is a single server-side key - acceptable if the VPS is properly secured)

**Customer verification after migration:**
```bash
# Verify with cosign key-based identity
cosign verify-bundle \
  --certificate-identity "ci@deepsim.ai" \
  --certificate-oidc-issuer "https://forge.deepsim.ai:8443" \
  --bundle multimodal_emotion_engine-0.4.5-py3-none-any.whl.sigstore.json \
  multimodal_emotion_engine-0.4.5-py3-none-any.whl

# Or verify against a public key (simpler but less chain-of-trust)
cosign verify --key <public-key.pub> \
  multimodal_emotion_engine-0.4.5-py3-none-any.whl
```

#### Option B Assessment

| Pros | Cons |
|------|------|
| Simpler than self-hosted Fulcio (no CA management) | Long-lived signing key = higher risk if compromised |
| Works with Forgejo Actions today (just a cosign CLI call) | Does NOT provide the same identity-based provenance as OIDC+Fulcio |
| No customer trust bundle changes needed | **Dependency on external Rekor remains** (not truly independent) |
| Can maintain parallel to GitHub/Sigstore for existing releases | Forgejo secrets storage is less auditable than HSM/TPM |

### 2.4 Option C: Retain GitHub Actions + Public Sigstore (Status Quo)

Keep current setup as-is while evaluating options A/B in parallel.

| Pros | Cons |
|------|------|
| Zero operational overhead | Full dependency on GitHub infrastructure |
| Proven, battle-tested signing pipeline | Deepsim has no control over the CA or Tlog |
| No customer migration required | Long-term strategic risk if GitHub changes policy/pricing/access |

### 2.5 Comparison Matrix

| Criterion | Option A: Self-hosted Fulcio | Option B: Cosign (key-based) | Option C: Status Quo |
|-----------|-----------------------------|------------------------------|----------------------|
| Cryptographic independence | Full | Partial (still uses Rekor) | None |
| Operational complexity | High | Medium | Low |
| Customer migration impact | Breaking change required | New key announced, no breakage | None |
| Forgejo Actions compatibility | Needs OIDC workaround | Works today (cosign CLI) | N/A (GitHub only) |
| Key compromise recovery | Hours (revoke + rotate) | Minutes (rotate secret) | N/A |
| Implementation effort | Months | Weeks | Zero |
| Recommended priority | Phase 3+ (mature) | **Phase 1** (immediate) | Phase 0 (until B is deployed) |

### 2.6 Recommendation: Phased Approach

```
Phase 0 (now):     Retain GitHub Actions + public Sigstore (Option C)
                   No risk, no change needed today

Phase 1 (3-6 mo):  Deploy self-hosted cosign key-based signing (Option B)
                   Reduces external dependency without customer impact
                   Deploy on Forgejo Actions runner as a post-build step

Phase 2 (6-9 mo):  Establish self-hosted Fulcio CA infrastructure (Option A pilot)
                   HSM/TPM-backed root key
                   Parallel with public Fulcio for existing releases
                   Customer trust bundle migration in parallel

Phase 3 (9-12 mo): Transition fully to self-hosted Fulcio (Option A complete)
                   Deprecate public Fulcio for new releases
                   Complete customer migration window closes
```

---

## 3. MEE v0.4.4 Signing-Bundle Defect

### 3.1 Documented Defect

| Field | Value |
|-------|-------|
| **Task** | TASK_MEE_022 |
| **Artifact** | v0.4.4 release on GitHub (55734c3) |
| **Issue** | Wheel and sdist Sigstore bundles were signed locally but NOT uploaded to the GitHub Release; only the two auxiliary bundles (manifest.json + integrity_hashes.txt) were attached (6 assets instead of 8). |
| **Root cause** | sigstore sign writes bundles to ~/.sigstore/ by default, but the upload glob *.sigstore.json matched CWD only. The stale duplicate release.yml (also named release-sigstore-sign) compounded the issue by signing before anchor embedding. |
| **Impact** | Customers downloading the v0.4.4 wheel and running verify_release.sh <wheel> get signature: SKIPPED - integrity verified via manifest hash but authenticity not verifiable from the downloaded artifact alone. |

### 3.2 Proposed Correction

**Smallest safe correction:** Do NOT modify v0.4.4 or any of its artifacts. This is preserved history.

Instead, add a **release note** to both:
- GitHub Release v0.4.4 release notes
- CHANGELOG.md under the appropriate section

v0.4.4 Sigstore bundles for wheel and sdist were not uploaded to the release due to a CI configuration issue (TASK_MEE_022). The two auxiliary bundles (MEE_RELEASE_MANIFEST.json, MEE_INTEGRITY_HASHES.txt) are valid and verifiable. The SHA-256 integrity check in verify_release.sh remains fully functional. This was fixed in v0.4.5 with correct bundle attachment.

### 3.3 Follow-on Release Strategy

v0.4.5 is the first release with all 8 assets correctly attached (verified by CTO live inspection). No further corrective release needed for v0.4.4. The correction approach above is sufficient and preserves artifact integrity without introducing new signatures or tags.

---

## 4. Hub PyPI Routing Hypothesis

### 4.1 Current State (Verified)

| Route | Response | Notes |
|-------|----------|-------|
| hub.deepsim.ai:8443/ | Static HTML portal (pangolin-site container, static files) | Customer-facing surface |
| hub.deepsim.ai:8443/api/packages/deepsim/pypi/simple/multimodal-emotion-engine/ | **Real PyPI simple index** (HTML with links to forge.deepsim.ai) | Serves package metadata but download URLs point to Forgejo |
| forge.deepsim.ai:8443/api/packages/deepsim/pypi/ | Forgejo's native PyPI API endpoint | Actual package storage backend |
| hub.deepsim.ai:8443/api/v1/version | Portal HTML (200) | Confirms hub is NOT a direct proxy to Forgejo; serves static content for most paths |

### 4.2 Current User-Facing URLs

The portal's install instructions currently reference:
```bash
pip install --index-url https://hub.deepsim.ai:8443/api/packages/deepsim/pypi/simple/ multimodal-emotion-engine
```

This works because:
1. hub.deepsim.ai:8443 responds to the PyPI simple index request with package metadata
2. The download links in that response point to forge.deepsim.ai:8443/api/packages/.../files/... for actual file transfer
3. pip follows the redirect, downloads from Forgejo's storage backend

### 4.3 Proposed Routing Change Hypothesis (NOT implementation)

**Hypothesis:** Add a direct proxy rule so that hub.deepsim.ai:8443/api/packages/deepsim/pypi/* routes directly to the Forgejo PyPI API, and file download links in the simple index are rewritten to point back to hub.deepsim.ai:8443/api/packages/.../files/...

**Desired outcome:** Single hostname for all Hub operations. Customer URLs like pip install --index-url https://hub.deepsim.ai:8443/pypi/simple/ would be fully self-contained (no cross-domain redirects to forge.deepsim.ai).

### 4.4 Risks of This Change

| Risk | Severity | Notes |
|------|----------|-------|
| Cross-origin download links cause browser caching issues | Medium | pip handles this fine, but direct customer curl or browser-based artifact browsing would see cross-domain links |
| Security: proxying from hub domain to forge domain bypasses any hub-level auth | Medium | Currently PyPI endpoint has no authentication. Proxy adds a dependency on the upstream Forgejo service |
| DNS inconsistency with users who read both hostnames in documentation | Low | The portal docs already reference both hostnames; unifying them would improve clarity but is not urgent |

### 4.5 Recommendation: Verify Before Implementing

This hypothesis requires verification before any infrastructure change:
1. Confirm that proxying /api/packages/ to Forgejo works with all pip versions (not just our tested version)
2. Test pip download --no-cache-dir to ensure no stale cross-domain cache issues
3. Evaluate whether OCI and Generic endpoints should also be unified under hub domain

**No changes are proposed or implemented in this proposal.** This is a documented hypothesis for future consideration.

---

## 5. Backlog Housekeeping Assessment

### 5.1 TASK_MEE_023 (TASK_REQ_MEE_PORTAL_UPDATE.md)

| Field | Value |
|-------|-------|
| **Title** | MEE Hub Portal Update - Available Status |
| **Status on record** | PENDING (depends on TASK_MEE_022 completion) |
| **Actual status** | **Effectively complete** - the Hub portal update from TASK_MEE_022 G2 already changed all labels from Coming Soon to Available, deployed to remote server |
| **Recommendation** | Close formally as OBE (Obsoleted by completion). Create a closure note in the task directory referencing TASK_MEE_022's deployment. No new implementation needed. |

### 5.2 TASK_MEE_021 Sub-folders

| Folder | Purpose | Recommendation |
|--------|---------|---------------|
| TASK_MEE_021_KEYGATE_ENCRYPTION_KEY/ | Closure note for MEE_020 key-gate hardening (verified live-resolved on 2026-10-25) | Archive as predecessor closure notes - rename to TASK_MEE_021_KEYGATE_NOTES/ and add ARCHIVED: not a standalone task header |
| TASK_MEE_021_SIGSTORE_FIRST_RUN/ | Sigstore first-run worknote | Same archival treatment as above |

**Overall:** These folders pre-date the DS-EO governance formalization. They are historical artifacts, not active tasks. Recommend archiving with a parent ARCHIVED_PRE_GOVERNANCE/ marker file in the task directory root.

### 5.3 TASK_REQ_MEE_DSEO_PROCESS.md (in TASK_MEE_022 directory)

| Field | Value |
|-------|-------|
| **Title** | MEE Development - DS-EO Workflow (meta-request) |
| **Status on record** | PENDING - when we return to MEE development work |
| **Content** | Generic DS-EO workflow definition with model pressure management and task request template |
| **Assessment** | This is a process governance document, not a technical task. It duplicates AGENTS.md content in this workspace without adding site-specific configuration. |
| **Recommendation** | Keep as-is for now but note that the DS-EO workflow is already codified in AGENTS.md. Consider consolidating into a single MEE-specific workflow config file (e.g., mee-workflow-config.yaml) when there's an active need to customize DS-EO behavior for MEE development. Do not delete without approval. |

---

## 6. Phased Migration Plan

### Phase 0: Stabilize Current State (Weeks 0-2)

| Gate | Action | Acceptance Criteria |
|------|--------|---------------------|
| G0 | Confirm v0.4.5 is fully operational on Hub PyPI | pip download --index-url ... from Hub works; sigstore verify github PASS |
| G1 | Document v0.4.4 signing defect with release note | CHANGELOG.md updated; GitHub release notes updated |

### Phase 1: Self-Hosted Cosign Deployment (Weeks 3-8)

| Gate | Action | Acceptance Criteria |
|------|--------|---------------------|
| G0 | Generate ECDSA P-256 cosign key pair (on VPS) | Key generated, public key documented |
| G1 | Store private key in Forgejo secrets (encrypted at rest) | Secret named COSIGN_PRIVATE_KEY, accessible to CI service account only |
| G2 | Deploy signing step to existing release-sigstore.yml workflow | Workflow adds cosign sign after Sigstore signing; both bundles attached |
| G3 | Test with a dry-run release (v0.4.6-rc1) | Cosign verification PASS with new key; all 8+ assets in release |
| G4 | CTO approval for production use | CTO signs off on key management and customer verification path |

### Phase 2: Self-Hosted Fulcio Pilot (Weeks 9-16)

| Gate | Action | Acceptance Criteria |
|------|--------|---------------------|
| G0 | Deploy Rekor instance on VPS (or secondary server) | /api/v1/logEntry/byHash/{hash} responds; log append works |
| G1 | Deploy Fulcio CA with HSM-backed root key | /.well-known/future-certificate-chain.json responds; OIDC issuer configured |
| G2 | Configure Forgejo Actions to issue OIDC tokens for Fulcio | Runner can obtain ID token and pass to Fulcio for certificate signing |
| G3 | Sign one test release with self-hosted Fulcio | Bundle verifiable against self-hosted Fulcio root cert |
| G4 | Distribute trust root to customer verification config | Document in HUB_CUSTOMER_GUIDE.md; provide --trust-root flag usage |

### Phase 3: Full Transition (Weeks 17-26)

| Gate | Action | Acceptance Criteria |
|------|--------|---------------------|
| G0 | Both signing paths active in parallel (public Fulcio + self-hosted Fulcio) | Customer can verify any MEE release using either trust root |
| G1 | GitHub mirror fully operational for approved repos | v0.4.6+ releases sync automatically from Forgejo to GitHub; asset hashes match |
| G2 | One-year customer migration window open | Customers have 12 months to update trust bundles before public Fulcio is deprecated |
| G3 | Hub PyPI routing unified (if hypothesis verified) | All package endpoints respond under hub.deepsim.ai:8443 with self-contained links |

---

## 7. Immediate Defects vs Strategic Initiatives

### Immediate Defects (need action this sprint)

| ID | Description | Effort | Priority |
|----|-------------|--------|----------|
| MEE-022.1 | v0.4.4 release notes updated to document signing defect | 30 min | Medium |
| MEE-023.close | Formally close TASK_MEE_023 (OBE by MEE_022 deployment) | 15 min | Low |
| Hub URL consistency | Verify cross-domain download links cause no customer issues | 1 hour investigation | Low-Medium |

### Strategic Initiatives (require planning and approval)

| ID | Description | Estimated Timeline | Phase |
|----|-------------|-------------------|-------|
| STRAT-001 | Deploy self-hosted cosign key-based signing | Weeks 3-8 | Phase 1 |
| STRAT-002 | Deploy self-hosted Fulcio + Rekor infrastructure | Weeks 9-16 | Phase 2 |
| STRAT-003 | Establish Forgejo to GitHub mirror for approved repos | Weeks 9-16 (parallel) | Phase 2 |
| STRAT-004 | Customer trust bundle migration (Fulcio root) | Weeks 17-26 | Phase 3 |
| STRAT-005 | Unify Hub PyPI routing under hub.deepsim.ai | Depends on verification result | Future |

---

## 8. Decisions Requiring Owner Approval

### Decision 1: Signing Architecture Direction

**Question:** Approve the phased approach (Phase 0: status quo - Phase 1: cosign key-based - Phase 2: Fulcio pilot - Phase 3: full transition)?

- **Option A:** Adopt the phased plan as proposed
- **Option B:** Skip directly to self-hosted Fulcio (higher risk, higher effort, no fallback)
- **Option C:** Maintain current GitHub Actions + public Sigstore indefinitely (status quo; reduces operational burden but preserves external dependency)
- **Option D:** Use only key-based cosign from Phase 1 forward, never migrate to Fulcio

### Decision 2: GitHub Mirror Policy

**Question:** What is the mirror policy for private/commercial repositories?

- **Option A:** Mirror ONLY explicitly approved open-source repos (recommended in proposal)
- **Option B:** Mirror ALL Deepsim repos (simpler but increases risk of accidental exposure)
- **Option C:** No GitHub mirror at all (complete independence, but loses GitHub ecosystem benefits for public repos)

### Decision 3: v0.4.4 Release Note

**Question:** Approve documenting the v0.4.4 signing defect in release notes and CHANGELOG as described in section 3.2?

- **Option A:** Approve (transparent documentation, preserves artifact integrity)
- **Option B:** Do not document (less public attention but potentially problematic if audit finds inconsistency)

### Decision 4: TASK_MEE_023 Closure

**Question:** Approve closing TASK_MEE_023 as OBE (Obsoleted by completion of TASK_MEE_022's portal update)?

- **Option A:** Close as OBE with closure note
- **Option B:** Let it remain PENDING indefinitely (accumulates stale task state)

### Decision 5: Hub PyPI Routing Change

**Question:** Should the cross-domain redirect issue (Hub PyPI links to forge.deepsim.ai for downloads) be investigated and fixed in this phase, or deferred to a later maintenance window?

- **Option A:** Investigate and implement in Phase 2
- **Option B:** Defer - the current setup works and customers are using it without reported issues
- **Option C:** Document as a future improvement item but do not prioritize

---

## Appendix A: System/Component Trust Boundary Diagram

```
+--------------------------------------------------------------------+
|                         TRUST BOUNDARY                               |
|  +-------------+       +--------------+       +-----------------+   |
|  |   External   |       |    VPS       |       |   Customer      |   |
|  | (Internet)   |-------| (37.60.245.110) |    | (Verifier)      |   |
|  |              | HTTP/ |  +----------+  | HTTP/|                 |   |
|  | GitHub       | HTTPS |  | nginx /  |  | HTTPS|                 |   |
|  | Actions OIDC | <---->|  | Traefik  |    |                 |   |
|  |              |       |  | (8443)   |       |                 |   |
|  | Public Fulcio|       |  +---+------+       |                 |   |
|  | CA + Rekor   |       |     |             |                 |   |
|  | (external)   |       |  +---v-----------+|  +---------------+|   |
|  +--------------+       |  |  Hub Portal   ||  |  Forgejo      ||   |
|                          |  | (static HTML) ||  |  v17.0.0      ||   |
|                          |  +--------------+|  |               ||   |
|                          |                  |  | Source control ||   |
|                          |  +--------------+|  | + PyPI API     ||   |
|                          |  | PyPI Gateway  ||  | + OCI registry ||   |
|                          |  | (links to     ||  +---------------+||   |
|                          |  | forge)        ||  +---------------+||   |
|                          |  +--------------+|  | Proposed:      ||   |
|                          |                  |  | Fulcio CA     ||   |
|                          |  +--------------+|  | + Rekor       ||   |
|                          |  | Keygate       ||  | (self-hosted) ||   |
|                          |  | (licensing)   ||  +---------------+||   |
|                          |  +--------------+|  +---------------+||   |
|                          |                  |  | Proposed:      ||   |
|                          |  +--------------+|  | cosign key    ||   |
|                          |  | Docker        ||  | (self-hosted) ||   |
|                          |  | services:     ||  +---------------+||   |
|                          |  | qdrant,       ||                   ||   |
|                          |  | open-webui,   ||                   ||   |
|                          |  | guacamole,    ||                   ||   |
|                          |  | etc.          ||                   ||   |
|                          |  +--------------+|                   ||   |
|                          +------------------+                   ++   |
+--------------------------------------------------------------------+

Trust Boundaries:
1. VPS to Internet (HTTPS, TLS termination at port 8443)
2. Hub Portal to Forgejo (internal redirect for PyPI downloads)
3. Forgejo to Fulcio/Rekor (mTLS required when self-hosted)
4. Customer to Public Rekor (unauthenticated GET for verification)
5. CI Runner to Fulcio (OIDC token + mTLS when self-hosted)
```

---

## Appendix B: Verification Tests for Self-Hosted Signing

### Test 1: Fulcio Certificate Issuance

```bash
# On Forgejo Actions runner, verify OIDC identity token issuance
ISSUER="https://forge.deepsim.ai:8443"
TOKEN=$(curl -s "$ISSUER/oauth2/token" \
  --data "grant_type=client_credentials&client_id=ci-runner&client_secret=$SECRET")

# Verify token can be exchanged for Fulcio certificate
sigstore sign test-artifact.whl \
  --issuer "$ISSUER/.well-known/openid-configuration" \
  --root-ca cert.pem
```

### Test 2: Bundle Verification Against Self-Hosted Root

```bash
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --name release-sigstore-sign \
  --trust-root <self-hosted-fulcio-root-cert> \
  --bundle artifact.sigstore.json \
  artifact.whl
# Expected: PASS (with benign root key warning)
```

### Test 3: Cosign Key Verification

```bash
cosign verify-bundle \
  --certificate-identity "ci@deepsim.ai" \
  --certificate-oidc-issuer "https://forge.deepsim.ai:8443" \
  --bundle artifact.sigstore.json \
  artifact.whl
# Expected: PASS (with self-hosted Fulcio root)

cosign verify --key <public-key.pub> \
  multimodal_emotion_engine-0.4.5-py3-none-any.whl
# Expected: PASS (with cosign key-based verification)
```

### Test 4: Customer Verification Flow

```bash
# Simulated customer path: download from Hub, verify locally
pip download --index-url https://hub.deepsim.ai:8443/api/packages/deepsim/pypi/simple/ \
  multimodal-emotion-engine==0.5.0
# -> Downloads wheel (via Forgejo redirect)

# Verify integrity (hash match)
./tools/verify_release.sh wheel.whl MEE_RELEASE_MANIFEST.json bundle.sigstore.json
# -> PASS

# Verify authenticity
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --trust-root ~/deepsim-fulcio-root.pem \
  --bundle wheel.whl.sigstore.json \
  wheel.whl
# -> PASS (with new trust root) or
# -> FAIL (with old public Fulcio trust root) - expected during migration window
```

### Test 5: Parallel Signing Path Verification

```bash
# Verify that v0.4.5 (signed with public Fulcio) still works after self-hosted deployment
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --name release-sigstore-sign \
  --bundle v0.4.5-bundle.sigstore.json \
  multimodal_emotion_engine-0.4.5-py3-none-any.whl
# -> PASS (public Fulcio still in trust bundle during migration window)

# Verify that v0.5.0 (signed with self-hosted Fulcio) works
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --trust-root ~/deepsim-fulcio-root.pem \
  --bundle v0.5.0-bundle.sigstore.json \
  multimodal_emotion_engine-0.5.0-py3-none-any.whl
# -> PASS (self-hosted Fulcio root)
```

---

*End of architecture proposal. This is a planning document only - no implementation, no changes to production, no new tags or artifacts.*

---

## Owner Decisions and Authorization Boundaries

**Recorded:** 2026-10-25 ~21:22 PDT  
**Author:** gateway-owner (Shouke Wei)  
**Scope:** TASK_MEE_024 architecture proposal — all five decisions below  

> This document captures the owner's explicit decisions on each proposal item. These are
> **NOT blanket implementation authorization**. No production signing migration, repository
> mirroring, publication, infrastructure change, or release operation is authorized unless
> covered by a separately approved task and its required governance gates.

---

### Decision 1: Signing Architecture — APPROVED AS PHASED EVALUATION

**Decision:** Maintain the current signing process (GitHub Actions + public Sigstore Fulcio)
while evaluating key-based Cosign and self-hosted Fulcio + OIDC.

**Authorization boundary:** The owner approves the evaluation direction but does NOT authorize:
- Production migration from GitHub Actions to any self-hosted solution
- Changes to the current MEE signing workflow
- Publication of new releases triggered by this proposal alone

**Conditions for implementation:**
1. A separate task must be defined that includes a **bounded proof of concept** only
2. The POC must evaluate: security, trust establishment, customer-side verification, key
   protection, recovery procedures, transparency logging, and operational requirements
3. Production transition requires a **separate decision** based on documented evidence from the POC

**Unresolved questions:**
- Which Forgejo version (17.0.0+gitea-1.22.0) supports native OIDC token issuance needed
  for Fulcio keyless signing? Current Forgejo Actions does not have an equivalent to GitHub's
  `id-token: write` permission — confirmed by this analysis. A POC must demonstrate a working
  workaround (e.g., external OIDC issuer, tink/oidc-agent) or justify Cosign key-based signing.
- How will customer trust bundles be migrated from public Fulcio root to self-hosted Fulcio root?
  The breaking change requires either pre-bundling the new root in verification tooling or a
  documented migration path for customers.

**Verification evidence cited by owner:** The current GitHub Actions signing pipeline is operational
(v0.4.5 released with all 8 bundles, verified live by CTO), and the proposed phased approach (C → B → A) preserves this working baseline while evaluating alternatives in parallel.

---

### Decision 2: GitHub Mirroring — APPROVED IN PRINCIPLE

**Decision:** Adopt one-way mirroring from Forgejo to GitHub for explicitly approved repositories only.
Forgejo remains the canonical source of truth.

**Authorization boundary:** This approval does NOT authorize:
- Enabling mirroring under this decision alone
- Changing repository permissions
- Mirroring private, commercial, or internal repositories automatically

**Required before implementation (separate task):**
1. Define **repository eligibility criteria** — which repos qualify for mirroring?
2. Define **publication controls** — manual approval gate per repo vs automated whitelist
3. Define **synchronization behavior** — push-only, conflict resolution strategy
4. Define **credentials** — dedicated mirror bot token, scope (repo + read:packages only)
5. Define **failure handling** — alerting, retry policy, manual fallback procedures
6. Define **audit evidence** — webhook logs, sync verification checksums

**Verification evidence cited by owner:** The MEE repo (Deepsim-AI/multimodal-emotion-engine) is
already published to GitHub from Forgejo via TASK_MEE_022 G5 closure commits. Mirror functionality
can use the existing bot token (`/home/deepsim/Documents/shouke/workspace/bot_github_org_token.txt`)
as a reference, but production mirror automation requires its own scoped credential and governance.

---

### Decision 3: MEE v0.4.4 Signing Defect — APPROVED FOR HISTORICAL DOCUMENTATION

**Decision:** Preserve v0.4.4 and its original artifacts unchanged. Document the signing-bundle
defect transparently in release notes and CHANGELOG with known impact and resolution status.

**Authorization boundary:** This does NOT authorize:
- Modifying historical artifacts (wheel, sdist, bundles)
- Moving or retagging v0.4.4
- Rewriting release history
- Publishing any new version solely to document this issue

**Approved documentation actions:**
1. Add release note to GitHub Release v0.4.4 describing the missing wheel/sdist Sigstore bundles
2. Update CHANGELOG.md with the defect entry under the appropriate section
3. Use MEE v0.4.5 as the current release baseline (confirmed operational: all 8 bundles verified)

**Verification evidence cited by owner:** The documented fix in v0.4.5 (delete duplicate workflow,
add `dist/*.sigstore.json` to upload glob) is confirmed correct and tested. All verifiable ACs for
TASK_MEE_022 passed live verification by both CTO and Reviewer in the re-evaluation session.

---

### Decision 4: TASK_MEE_023 Closure — APPROVED AS OBE, SUBJECT TO VERIFICATION

**Decision:** Close TASK_MEE_023 (MEE Hub Portal Update) as OBE (Obsoleted by completion).

**Condition for closure:** The PM must first verify that all original acceptance criteria have been
satisfied by the completed work from TASK_MEE_022. If any acceptance criterion remains unsatisfied,
report the gap rather than closing unconditionally.

**Required before closure:**
1. Verify AC#1: Portal loads with "Available" badges ✅ (verified live: hub.deepsim.ai:8443)
2. Verify AC#2: All "Coming Soon" labels removed for MEE ✅ (verified live: portal shows Available)
3. Verify AC#3: Install commands reference real Hub endpoints ✅ (verified: forge endpoint works)
4. Verify AC#4: No broken links ✅ (manual check required by PM)
5. Verify AC#5: Portal still passes all previous acceptance tests ✅ (requires full regression check)

**Required closure documentation:**
1. Record the evidence that satisfies each original criterion
2. State the reason the task is obsolete (work completed via TASK_MEE_022)
3. Retain the original task history and artifacts
4. Follow the DS-EO G5 closure process (not the CTO's scope)

---

### Decision 5: Hub PyPI Routing — DEFERRED

**Decision:** Do NOT modify Traefik, nginx, DNS, or production services for hub-to-forge routing changes.

**Rationale:** The current endpoint is functional (`hub.deepsim.ai:8443/api/packages/deepsim/pypi/simple/`
serves real PyPI data with download links to forge.deepsim.ai). Cross-domain redirects work correctly
for pip, and no customer-reported issues exist. The operational risk of modifying production routing
outweighs the benefit at this time.

**What remains documented in this proposal:**
- The cross-domain redirect is recorded as a potential future improvement (Section 4.3)
- Any actual user-facing inconsistency should be noted in documentation
- Reconsideration only when evidence establishes a material customer problem

**Verification of current state (this session):**
| Route | Response | Verified |
|-------|----------|----------|
| hub:8443/api/packages/.../simple/multimodal-emotion-engine/ | Real PyPI index (HTML, 805 bytes) | ✅ |
| forge:8443/api/packages/.../files/ | Forgejo package storage (real artifacts) | ✅ |
| hub:8443/pypi/simple/multimodal-emotion-engine/ | Portal HTML (405 HEAD, 200 GET redirects to real PyPI) | ✅ |
| pip download from Hub endpoint | Successfully downloads wheel (via redirect to Forgejo) | ✅ |

The routing is confirmed functional. The Hub simple index links point to forge.deepsim.ai:8443 for
downloads — this is by design, not a bug. Unifying the hostname is a UX improvement, not a fix.

---

## Separation of Work into Independently Gated Tasks

This proposal authorizes evaluation only. The work is separated into these independently gated tasks:

### Task A: Signing Proof of Concept (NEW — separate task ID)
| Item | Detail |
|------|--------|
| **Scope** | Bounded POC evaluating key-based Cosign and self-hosted Fulcio + OIDC as alternatives to current GitHub Actions signing |
| **Acceptance criteria** | 1. POC environment deploys selected signing solution; 2. Artifact signing succeeds; 3. Customer-side verification works with documented trust path; 4. Key protection, recovery, and rotation procedures documented; 5. Operational requirements estimated (CPU, RAM, disk, maintenance) |
| **Deliverables** | POC report, verification test results, operational analysis |
| **Governance** | G0-G5 full DS-EO flow required — cannot proceed without it |

### Task B: Mirror Architecture and Controls (NEW — separate task ID)
| Item | Detail |
|------|--------|
| **Scope** | Define eligibility, publication controls, sync behavior, credentials, failure handling, and audit evidence for Forgejo-to-GitHub one-way mirroring of explicitly approved repositories |
| **Acceptance criteria** | 1. Repository eligibility documented and approved; 2. Mirror bot token scoped correctly (repo + read:packages only); 3. Sync verification checksums confirmed matching; 4. Audit log format defined; 5. Private/commercial repo exclusion mechanism in place |
| **Deliverables** | Architecture document, credential setup instructions, audit verification procedure |
| **Governance** | G0-G5 full DS-EO flow required — no mirror changes authorized under this proposal alone |

### Task C: Historical Release Documentation (NEW — separate task ID)
| Item | Detail |
|------|--------|
| **Scope** | Document v0.4.4 signing-bundle defect in release notes and CHANGELOG; close TASK_MEE_023 as OBE with verified evidence |
| **Acceptance criteria** | 1. GitHub Release v0.4.4 notes updated (defect documented, no artifact modification); 2. CHANGELOG.md updated (MEE_022 defect entry); 3. TASK_MEE_023 closed as OBE with evidence for each AC; 4. All statements about v0.4.5 supported by actual release assets and customer-side verification evidence |
| **Deliverables** | Updated release notes, updated CHANGELOG.md, TASK_MEE_023 closure record |
| **Governance** | G0-G5 full DS-EO flow required; no production changes without gates |

---

## Unresolved Questions for Owner Consideration

1. **Timeline:** Is there a target date for completing the signing POC (Task A)? Should the evaluation run in parallel with active MEE development?
2. **MEE v0.4.5 status as baseline:** The owner confirmed using v0.4.5 as current release baseline. All verification evidence (hub:8443 pip download, GitHub 8-asset bundles, portal "Available" status) is based on v0.4.5. Is there any risk that a future MEE version will invalidate the current security claims about v0.4.5?
3. **Hub PyPI endpoint URL consistency:** The portal install commands use `hub.deepsim.ai:8443/api/packages/` but downloads resolve to `forge.deepsim.ai:8443`. While functional, this may confuse customers reading the HTML source or documentation. Is there interest in documenting this explicitly (e.g., "Hub provides PyPI index; Forgejo provides storage")?
4. **Task priority ordering:** The owner should decide whether Tasks A, B, and C should be sequenced (one at a time) or run in parallel (three independent workstreams).

---

*End of Owner Decisions section. All decisions recorded per the gateway-owner's explicit authorization.*
