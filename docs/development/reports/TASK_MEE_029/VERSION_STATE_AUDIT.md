# VERSION STATE AUDIT — MEE v0.4.5

**Date:** 2026-10-26 (PDT)
**Context:** Owner notes local is v0.4.5 but Forgejo is still v0.4.4.

## Current State

| Location | Latest tag | Latest release | v0.4.5 present? |
|----------|-----------|----------------|-----------------|
| **Local** (master) | v0.4.5 (commit `5af1587`) | n/a (no Forgejo release) | ✅ tag exists |
| **GitHub** (`origin`) | v0.4.5 (commit `5af1587`) | v0.4.5 (published) | ✅ tag + release |
| **Forgejo** (`forgejo`) | **v0.4.4** | **v0.4.4** (2026-10-25) | ❌ missing |

## What This Means

- **v0.4.5 was released on GitHub** (tag + release + assets) but **never on Forgejo**.
- The Forgejo repo is one release behind: v0.4.4 is the latest tag and release.
- The local `dist/` directory contains v0.4.0 artifacts (stale from a prior build), not v0.4.5.
- `pyproject.toml` has `version = "0.4.5"` — the source is at v0.4.5.
- Three commits sit between v0.4.4 and v0.4.5:
  - `15dc500` docs: install-from-release, CONTRIBUTING, CODE_OF_CONDUCT
  - `d7a7c6b` fix: attach dist/ bundles + CI verify (TASK_MEE_022 G2-1.5)
  - `5af1587` fix: remove duplicate workflow (root cause of invalid sigs)

## Implication for MEE_029 Test

The owner asks: "can we use the real release v0.4.5?"

**Answer: Yes, but with care.**

The `release-sigstore.yml` workflow is triggered by `push: tags: ["v*"]`. Pushing the
existing `v0.4.5` tag to Forgejo would:

1. **Trigger the workflow** on Forgejo (build → sigstore sign → cosign sign → verify →
   create Forgejo release → upload assets)
2. **Create a new Forgejo release** for v0.4.5 (does NOT exist on Forgejo yet)
3. **Upload assets** to that new Forgejo release via the Forgejo API
4. **NOT overwrite** the GitHub v0.4.5 release (different platform, different API)
5. **NOT modify** the v0.4.5 tag or its commit (tags are immutable; the workflow only
   reads the tag to build from)

**Risk assessment:**
- ✅ No tag overwrite (v0.4.5 tag already exists; pushing it is a no-op on the ref)
- ✅ No GitHub release modification (workflow uses Forgejo API, not GitHub API)
- ⚠️ A **new Forgejo release** will be created (v0.4.5 on Forgejo) — this is the
  **intended effect** (catching up Forgejo to v0.4.5)
- ⚠️ The workflow will run **Sigstore keyless signing** (OIDC via `id-token: write`)
  — this requires the Forgejo OIDC provider to be configured. If it's not, that step
  will fail, but the **Cosign key-based step will still run** (it's independent)
- ⚠️ The workflow will run **`sigstore verify github`** in the CI self-check — this
  verifies against the **GitHub** Sigstore identity, which requires the GitHub Actions
  OIDC context. On Forgejo, `sigstore verify github` may fail if the identity doesn't
  match. The **Cosign verify** step is independent and should pass.

**Proposed approach:**

Option A: **Push v0.4.5 tag to Forgejo** — triggers the full pipeline. Creates the
missing Forgejo v0.4.5 release. The Sigstore keyless steps may partially fail (OIDC
identity mismatch on Forgejo), but the Cosign key-based steps should fully pass.

Option B: **Push a new tag v0.4.6** (bump version in `pyproject.toml` + CHANGELOG)
— clean release, no confusion with the existing GitHub v0.4.5.

Option C: **Use the cosign-probe workflow** (already proven working) as the CI
verification, and defer the full `release-sigstore.yml` run to when the Sigstore
keyless path is also validated on Forgejo.

**Recommendation:** Option A is safe if the owner is comfortable with a new Forgejo
v0.4.5 release being created. It does not touch GitHub. The Sigstore keyless steps
may fail on Forgejo (OIDC), but that's a pre-existing issue, not an MEE_029 regression.
The Cosign path (the MEE_029 deliverable) will fully sign + verify + upload.

---

*End of version state audit.*
