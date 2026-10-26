# TASK_MEE_022 — CTO Plan Amendment (G1)

**Gate:** G1 — Plan Amendment (amends TASK_PLAN.md, not a new task)
**Date:** 2026-10-25
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)
**Task ID:** TASK_MEE_022
**Title:** MEE Hub Distribution — Publish to Forgejo Registry

## Trigger

The original plan's precondition ("signed v0.4.4 release exists on GitHub") was
verified **TRUE** on 2026-10-25 (see `CONTEXT_RECONCILIATION_REPORT.md` §2.2–2.3).
However, two genuine gaps were identified that block G2 execution:

1. **CI upload bug:** The `release-sigstore.yml` workflow signs all four artifacts
   (manifest, anchor, wheel, sdist) but the `softprops/action-gh-release` step
   attaches `*.sigstore.json` bundles via a glob that does NOT match the
   wheel/sdist bundles. Result: the v0.4.4 release has only the two auxiliary-file
   bundles; the wheel and sdist have **no attached Sigstore bundle**, so the
   customer-facing `verify_release.sh` can only report `signature: SKIPPED` for the
   wheel.

2. **Manifest bundle verification fails:** `sigstore verify github` against
   `MEE_RELEASE_MANIFEST.json` and its bundle returns "invalid file_or_digest" —
   the CLI cannot pair the manifest file with its bundle. Root cause: the manifest
   is generated *after* the signing step (or the signing step hashes a different
   byte sequence than the final file). The anchor bundle verifies cleanly, so the
   signing itself works; the manifest is the outlier.

## Decision

**Amend the plan to include a CI fix step (G2-1.5) before registry publishing.**
This touches `.github/workflows/release-sigstore.yml`, which is C1-protected.
The owner has authorized this amendment. No change to the signing architecture —
same workflow, same Fulcio keyless OIDC, same sigstore-python. Only the upload
step and the signing order are fixed.

## Amendment Details

### G2-1.5: CI Fix (new step, before G2-1)

**File:** `.github/workflows/release-sigstore.yml`

**Change 1 — Sign AFTER the final artifact state is stable:**

Current order:
```
build → generate anchor → embed anchor in wheel → compute manifest → sign ALL → upload
```

Problem: the manifest is computed, then signed. But the manifest's SHA-256 is
the *input* to the signing — so the signature covers the manifest bytes. That's
correct. The issue is the **upload glob**.

**Change 2 — Fix the upload glob to attach ALL bundles:**

Current:
```yaml
files: |
  dist/*.whl
  dist/*.tar.gz
  MEE_RELEASE_MANIFEST.json
  MEE_INTEGRITY_HASHES.txt
  *.sigstore.json
```

Problem: `*.sigstore.json` matches files in the **repo root** (CWD), but `sigstore
sign` writes bundles **next to the signed file** by default. So:
- `MEE_RELEASE_MANIFEST.json.sigstore.json` → repo root ✅ (matches `*.sigstore.json`)
- `MEE_INTEGRITY_HASHES.txt.sigstore.json` → repo root ✅ (matches `*.sigstore.json`)
- `dist/multimodal_emotion_engine-0.4.4-py3-none-any.whl.sigstore.json` → `dist/` ❌ (does NOT match)
- `dist/multimodal_emotion_engine-0.4.4.tar.gz.sigstore.json` → `dist/` ❌ (does NOT match)

**Fix:** Add `dist/*.sigstore.json` to the files list:
```yaml
files: |
  dist/*.whl
  dist/*.tar.gz
  dist/*.sigstore.json
  MEE_RELEASE_MANIFEST.json
  MEE_INTEGRITY_HASHES.txt
  MEE_RELEASE_MANIFEST.json.sigstore.json
  MEE_INTEGRITY_HASHES.txt.sigstore.json
```

**Change 3 — (Optional, if manifest bundle still fails verification) Sign the
manifest in a separate step AFTER the wheel is finalized, and verify the bundle
immediately in CI:**

Add a post-sign verification step:
```yaml
- name: Verify signatures (CI self-check)
  run: |
    sigstore verify github \
      --bundle MEE_RELEASE_MANIFEST.json.sigstore.json \
      --repository Deepsim-AI/multimodal-emotion-engine \
      --name release-sigstore-sign \
      MEE_RELEASE_MANIFEST.json
    sigstore verify github \
      --bundle MEE_INTEGRITY_HASHES.txt.sigstore.json \
      --repository Deepsim-AI/multimodal-emotion-engine \
      --name release-sigstore-sign \
      MEE_INTEGRITY_HASHES.txt
    sigstore verify github \
      --bundle dist/*.whl.sigstore.json \
      --repository Deepsim-AI/multimodal-emotion-engine \
      --name release-sigstore-sign \
      dist/*.whl
    sigstore verify github \
      --bundle dist/*.tar.gz.sigstore.json \
      --repository Deepsim-AI/multimodal-emotion-engine \
      --name release-sigstore-sign \
      dist/*.tar.gz
```

If any verification fails in CI, the workflow fails fast — no broken release.

### G2-1.6: Re-release v0.4.4 (or v0.4.5)

After the CI fix is committed and pushed:
- **Option A (preferred):** Bump version to `v0.4.5` (clean break, no tag reuse),
  push the new tag → workflow runs → new release with all 6+ bundles attached.
- **Option B:** Delete the v0.4.4 release, re-push the same tag → workflow re-runs.
  Risky (GitHub may cache the old release).

**Decision:** Option A (v0.4.5) — cleaner audit trail.

### G2-1.7: Verify new release

After the new release is published:
1. Download all assets via the GitHub asset API (same as v0.4.4)
2. Verify all SHA-256 hashes match the manifest
3. Verify ALL FOUR bundles with `sigstore verify github`
4. Run `verify_release.sh` on the wheel → expect `signature: PASS`
5. Record evidence in `TASK_MEE_022/G2_EVIDENCE.md`

### G2-2: Registry Publishing (unchanged from original plan)

Now unblocked:
- PyPI: `twine upload` with `deepsim` account password
- OCI: `docker push` with `deepsim` account password
- Generic: `curl -u deepsim:*** PUT`

### G2-3: Portal & Documentation (unchanged)

- Portal: "Coming Soon" → "Available"
- `HUB_CUSTOMER_GUIDE.md`: MEE install section
- `HUB_DEPLOYMENT_RECORD.md`: publication evidence
- `README.md`: Hub registry install option

## Acceptance Criteria (updated)

| AC # | Criterion | Verification Method | Expected |
|------|-----------|-------------------|----------|
| 1–4 | `pip install` base + 3 extras via Hub | temp venv test | ✅ installs |
| 5 | Docker pull via Hub OCI | `docker pull` | ✅ pulls |
| 6 | Docker run `mee-lic status` | `docker run --rm ...` | ✅ responds |
| 7 | Generic curl download | `curl + sha256sum` | ✅ 200, bytes match |
| 8 | **Sigstore verification of wheel** | `verify_release.sh` | ✅ **PASS (signature verified)** |
| 9 | All Forgejo endpoints functional | Health check | ✅ responsive |
| 10 | Portal shows "Available" | Hub portal UI/API | ✅ badge visible |
| 11 | Test packages still accessible | Search Forgejo | ✅ present |
| 12 | Docker image non-root, no weights | Image inspection | ✅ verified |

**New AC #8 detail:** The wheel MUST have an attached Sigstore bundle, and
`verify_release.sh` MUST report `signature: PASS` (not SKIPPED).

## Constraints (unchanged)

- C1: No modifications to `.github/workflows/` **except** the authorized amendment
- C2: GitHub Actions remains canonical release origin
- C3: Existing Forgejo test packages untouched
- C4: All artifacts carry original Sigstore bundles (now including wheel/sdist)
- C5: All checksums computed live, never fabricated
- C6: GitHub Releases path documented as primary signed-artifact origin
- C7: Model weights excluded from Docker image and all registry packages

## Stop Conditions (unchanged)

- v0.4.5 build/sign fails on GitHub → stop and report
- Docker build fails → stop (do NOT publish broken image)
- Any acceptance test fails → stop and report
- Forgejo API errors on publish → stop after retries, report
- Sigstore verification fails → stop and report

## Gate Status (updated)

| Gate | Status | Artifacts Required |
|------|--------|--------------------|
| G0 | ✅ (unchanged) | `G0_INTAKE_CHECKLIST.md`, `LOCK.md` |
| G1 | ✅ **Amended** (this file) | `TASK_PLAN.md` + this amendment |
| G2 | ☐ Pending | G2-1.5 CI fix → G2-1.6 re-release → G2-1.7 verify → G2-2 publish → G2-3 docs |
| G3 | ☐ Pending | `REVIEW_REPORT.md` |
| G4 | ☐ Pending | `CTO_APPROVAL.md` |
| G5 | ☐ Pending | `PROJECT_STATUS.md`, `CHANGELOG.md`, PM_CLOSED |

---

*End of CTO plan amendment for TASK_MEE_022.*
