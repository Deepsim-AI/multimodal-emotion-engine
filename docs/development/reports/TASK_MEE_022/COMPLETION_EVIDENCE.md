# TASK_MEE_022 — Gate G1 Approval (CTO)

**Gate:** G1 — CTO Plan Approved
**Date:** 2026-10-25
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)
**Task ID:** TASK_MEE_022
**Title:** MEE Hub Distribution — Publish to Forgejo Registry

---

## Decision: APPROVE (G1)

The G0 intake is complete and artifacts are in order. The task request
(TASK_REQ_MEE_HUB_PUBLISH.md) provides clear deliverables, constraints,
and acceptance criteria. The architecture decision points (6.1-6.6)
have been resolved below:

### Resolved Decision Points

| ID | Decision | Resolution | Rationale |
|----|----------|------------|-----------|
| 6.1 | Build source | Reuse GitHub Actions release assets; do NOT build locally | Sigstore keyless signing requires OIDC — local build loses provenance |
| 6.2 | OCI image | Create `Dockerfile.mee` at repo root; multi-arch via buildx | Standard Python container pattern, non-root user, health check included |
| 6.3 | Generic channel | Wheel + sdist tarball bundle (Option A) | MEE is a Python package; no native binaries needed; C7 blocks weight inclusion |
| 6.4 | Sigstore reuse | Use GitHub-signed artifacts as-is with `.sigstore` bundles | No re-signing; preserves authentic Fulcio keyless provenance; satisfies C1/C2 |
| 6.5 | Extras | Publish all extras (`vision`, `voice`, `demo`) via single wheel | Wheel already encodes extras metadata in pyproject.toml |
| 6.6 | Model weights | Confirmed excluded from registry (C7) | Weights fetched at runtime from CDN; Docker image contains only inference code |

### Implementation Scope Summary

8 implementation steps across 3 phases:
1. Artifact preparation (download signed assets, create Dockerfile.mee, build multi-arch image)
2. Hub registry publishing (PyPI upload, OCI push, generic tarball bundle)
3. Portal & documentation updates (portal status change, HUB_CUSTOMER_GUIDE.md, HUB_DEPLOYMENT_RECORD.md, README.md)

### Constraints Verification

All 7 constraints from the task request are enforced in this plan:
- ✅ C1-C2: No GitHub Actions modification; GitHub remains canonical origin
- ✅ C3: Existing Forgejo test packages untouched
- ✅ C4: Original Sigstore bundles preserved (no re-signing)
- ✅ C5: Live checksum computation only
- ✅ C6: GitHub Releases documented as primary origin
- ✅ C7: Model weights excluded

### Pre-conditions to Verify Before Implementation

1. **GitHub v0.4.4 release exists** — The task req states it does, but HEAD `15dc500` 
   is from MEE_020 worknotes. Implementer MUST verify and report if the release/tag 
   doesn't exist (CTO blocker).
2. **Hub registry credentials available** — Forgejo PAT for PyPI/OCI/generic upload, 
   stored in `.gitignore`d config files.
3. **Docker buildx available** — Multi-arch build; fallback to arm64-only if unavailable.

### Gate Status

| Gate | Status |
|------|--------|
| G0 | ✅ Complete (PM intake artifacts present) |
| G1 | ✅ **Approved** |
| G2 | ☐ Pending (Implementation) |
| G3 | ☐ Pending (Reviewer) |
| G4 | ☐ Pending (CTO final approval) |
| G5 | ☐ Pending (PM — separate session) |

---

*End of CTO G1 approval for TASK_MEE_022.*
