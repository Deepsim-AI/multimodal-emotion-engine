# TASK_REQUEST — TASK_MEE_021: Sigstore Signing Pipeline — First Live Execution

**Task ID:** TASK_MEE_021  
**Gate:** G0 — PM Intake  
**Phase:** Post-020 release pipeline activation  
**Date:** 2026-10-22  
**Requested By:** Gateway Owner (Shouke Wei)  
**Depends On:** TASK_MEE_020 (License Hardening & Signed Distribution, CLOSED, v0.4.0)

> **Governance note (Rule 9):** This G0 intake is a mechanical check-list step
> and does not implement code or bypass any gates. No implementation has occurred.

---

## 1. Problem Statement

TASK_MEE_020 delivered:
- A committed Sigstore signing workflow (`.github/workflows/release.yml`)
- An integrity anchor generation tool (`tools/generate_integrity_anchor.py`)
- A customer verification script (`tools/verify_release.sh`)
- All required docs (`docs/licensing/offline.md`, `docs/licensing/privacy.md`)

**Gap:** The Sigstore workflow has **never been executed on a tag**. The pipeline was written in G2 and never proven end-to-end. Without a first live run, we have:
1. No actual signed artifacts to verify — the customer verify path is untested
2. No primary anchor manifest (MEE_RELEASE_MANIFEST.json) produced by the pipeline
3. No proof that `sigstore-python` + GitHub OIDC works in CI on this repo
4. No wheel with embedded integrity anchor (`MEE_INTEGRITY_HASHES.txt` in `.dist-info/`)

This is a **release engineering task**, not a code change task. It is:
- Fully bounded (one tag push, one workflow execution, manual verification)
- Low risk (no prod deployment changes)
- High value (proves signed distribution AC1–AC2 of MEE_020 are actually met)

---

## 2. Scope (4 workstreams)

### 2.1 Pre-flight: Verify CI OIDC readiness
- Confirm GitHub Actions has the `id-token: write` permission granted for workload identity
- Ensure no branch protection or organization policy blocks workflow runs
- Document any required org-level OIDC trust setup

### 2.2 Trigger first release
- Tag v0.4.1 (minor patch; not a feature bump — just enables signing)
- Push tag to trigger `release-sigstore-sign` workflow on `push: tags: "v*"`
- Monitor workflow for completion (expected: ~5–8 minutes)

### 2.3 Verify signed artifacts
- Download release artifacts from the created GitHub release
- Run `tools/verify_release.sh <wheel>` to verify signature + hash
- Confirm MEE_RELEASE_MANIFEST.json exists with correct SHA-256 digests
- Confirm each artifact has a `.sigstore/` bundle alongside it

### 2.4 Document the verification path
- Add a "Verifying Releases" section to README.md or `docs/installation.md`
- Include the one-liner customers use: `./tools/verify_release.sh <wheel>`
- Note that verification is optional but recommended

---

## 3. Non-Goals

- **Not** changing Keygate, license logic, or any licensing code (released in MEE_020)
- **Not** setting up a second signing scheme (Sigstore was already chosen by CTO)
- **Not** changing the project version to v0.5.x — this is infrastructure activation
- **Not** enabling Sigstore for non-release contexts (CI dev builds stay unsigned)

---

## 4. Constraints (binding)

| # | Constraint |
|---|-----------|
| C1 | No code changes outside `.github/`, `tools/`, `docs/` — this is pipeline + docs only |
| C2 | Version must remain v0.4.0+ (pyproject.toml unchanged, or bump patch to 0.4.1 if needed by convention) |
| C3 | Do not enable production releases until the first run is verified |
| C4 | No new secrets or credentials — Sigstore keyless via OIDC has no credential setup |
| C5 | The workflow must be idempotent — re-running on a tag should produce the same outputs |

---

## 5. Measurable Acceptance Criteria (draft — refined in G1)

| # | AC | How verified |
|---|----|--------------|
| AC1 | Tag v0.4.1 is created and pushed to GitHub, triggering the workflow | Git tag present + GitHub Actions run visible |
| AC2 | Workflow completes successfully (all steps green) | GitHub Actions UI — no failures |
| AC3 | Signed wheel exists in release with `.sigstore/` bundle alongside it | `ls dist/*.sigstore/` on download, or release assets listing |
| AC4 | `MEE_RELEASE_MANIFEST.json` present with SHA-256 digests for all artifacts | File exists, contains valid JSON with `artifacts` array |
| AC5 | `tools/verify_release.sh <wheel>` returns exit code 0 (PASS) | Manual run post-download — clear PASS output |
| AC6 | Wheel contains embedded `MEE_INTEGRITY_HASHES.txt` in `.dist-info/` | Unpack wheel → verify file exists in `<pkg>.dist-info/` |
| AC7 | README.md or installation docs include a "Verifying Releases" section | File content confirmed (grep for "Verify" / "sigstore") |
| AC8 | No regression: `pytest tests/` still passes after any doc changes | Test suite green |

---

## 6. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| GitHub OIDC not configured (org blocks id-token) | High | Check org settings first; if blocked, request owner to enable Workload Identity Federation |
| Workflow fails on first run (unknown CI env issue) | Medium | Read logs, fix iteratively — this is a dry-run by definition |
| sigstore-python version incompatibility with runner Python 3.11 | Low | Workflow pins `"sigstore>=2.1,<3"`; test locally if needed |
| Release publish blocks (branch protection / permissions) | Low | Workflow already has `contents: write` and `id-token: write` in YAML |

---

## 7. Handoff

**Status:** G0 intake **drafted**. Awaiting PM review + signature, then handoff to **CTO (G1)** for architecture review + decision on versioning convention (0.4.1 patch vs keep v0.4.0 tag).

**No implementation, code modification, or gate bypass has occurred.** G0/G1/G2 gates must proceed normally.

---

*Drafted 2026-10-22 by Gateway Owner at owner request.*
