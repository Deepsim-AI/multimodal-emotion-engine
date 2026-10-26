# REVIEW REPORT — TASK_MEE_022 (G3 / Review)

**Task:** TASK_MEE_022 — MEE Hub Distribution — Publish to Forgejo Registry
**Gate:** G3 — Review (I recommend; I do **not** approve/reject — that is the CTO's G4 decision, per AGENTS.md §10 / Rule 9)
**Reviewer:** 🔍 (laguna-xs-2.1:q4_K_M)
**Date:** 2026-10-25 (PDT)
**Scope (my role):** Exactly this task directory `docs/development/reports/TASK_MEE_022/` — reads only, plus live verification of the GitHub release and Hub registry. I touched no files outside this report.

---

## 1. Recommendation: ❌ RECOMMEND REJECT — G3 does not pass

Two of the twelve acceptance criteria **fail on live verification**, and the core
deliverable of the task (publish MEE to the Hub PyPI registry) was **never executed**.
The work that *was* done is a legitimate and valuable CI hardening, but it resolves a
**different** acceptance item than the one the task was authorized for, and it does not
substitute for the Hub-publish deliverable.

Below is the full evidence. I verified everything myself against the live GitHub release
and the live Hub registry; I did not accept the Implementer's claimed results at face
value.

---

## 2. What was actually done (verified against git + live)

The session produced three commits on `master` (baseline `15dc500` → HEAD `028af9f`):

| Commit | Change | Verified |
|--------|--------|----------|
| `d7a7c6b` | `release-sigstore.yml`: attach `dist/*.sigstore.json` to release + add CI self-verify; bump 0.4.4 → 0.4.5 | ✅ present, diff matches claim |
| `5af1587` | Delete duplicate `release.yml` (root-cause of invalid sigs) | ✅ file gone; workflow now single-signer |
| `028af9f` | `tools/verify_release.sh`: fix `--repository`/`--name`, drop stale `--certificate` | ✅ present, diff matches claim |

Plus: tag `v0.4.5` pushed to `refs/tags/v0.4.5 = 5af1587`; GitHub Actions
`release-sigstore-sign` ran (attempt 1, `push`, `success`, 2026-10-25T23:11:25Z).

**Verdict on the CI fix itself:** the root-cause diagnosis (duplicate workflow, glob
missing `dist/` bundles) is **correct**, the fix is **correct**, and the live result
confirms it (see §3). This is real, valuable engineering — but it is a *release-pipeline*
fix, not a *Hub-publish*.

---

## 3. Independently verified Sigstore signatures (v0.4.5) ✅

Downloaded all four artifacts + bundles from the v0.4.5 release **asset API** and ran
`sigstore verify github` live (sigstore-python 3.6.7):

| Artifact | SHA-256 (downloaded) | Matches GitHub digest? | `sigstore verify github` |
|----------|----------------------|------------------------|--------------------------|
| wheel `.whl` | `d6d9e0b9ba3f…660cd8b` | ✅ `d6d9e0b9…` | **OK** |
| sdist `.tar.gz` | (verified) | ✅ | **OK** |
| `MEE_RELEASE_MANIFEST.json` | (verified) | ✅ | **OK** |
| `MEE_INTEGRITY_HASHES.txt` | (verified) | ✅ | **OK** |

All four bundle to the GitHub Actions Fulcio keyless OIDC identity
`repository=Deepsim-AI/multimodal-emotion-engine, workflow=release-sigstore-sign`. The only
output line is the benign `Failed to load a trusted root key: unsupported key type: 7`
trust-root warning (present on v0.4.4 too; verification itself succeeds).

**This is the concrete improvement the CTO amendment (G2-1.5) asked for:** the v0.4.4
release had 6 assets (no wheel/sdist bundles → customer `verify_release.sh` could only
report `signature: SKIPPED`); the v0.4.5 release has **8 assets**, and `verify_release.sh`
now reports `signature: PASS` for the wheel. ✅ The *signing* gap is closed.

---

## 4. Why G3 fails — acceptance criteria

Verification method: **live**, from this host. Not from the Implementer's report.

| AC | Criterion | My live result | Verdict |
|----|-----------|----------------|---------|
| 1 | `pip install` base via Hub | `pip install --index-url https://hub.deepsim.ai:8443/pypi/simple/ … multimodal-emotion-engine` → **`No matching distribution found`** (0 versions) | ❌ FAIL |
| 2 | `pip install [vision]` via Hub | Same index; 0 versions → fails | ❌ FAIL |
| 3 | `pip install [voice]` via Hub | Same | ❌ FAIL |
| 4 | `pip install [demo]` via Hub | Same | ❌ FAIL |
| 5 | Docker pull via Hub OCI | **No `Dockerfile.mee` was created**; no image built or pushed | ❌ FAIL |
| 6 | Docker run `mee-lic status` | No image exists | ❌ FAIL |
| 7 | Generic curl download | `…/generic/mee/0.4.4/mee-0.4.4.tar.gz` → **404**; no generic bundle uploaded | ❌ FAIL |
| 8 | Sigstore verification (wheel) | ✅ verified live, `OK`, all 4 bundles PASS | ✅ PASS |
| 9 | Forgejo endpoints functional | Endpoint reachable (200/405); no MEE artifacts published | ⚠️ Partial |
| 10 | Portal shows "Available" | **Live page still says** *"Not yet available. MEE has not been published to the Hub Python registry."* ⛔ | ❌ FAIL |
| 11 | Test packages still accessible | ✅ (not touched; C3 honored) | ✅ PASS |
| 12 | Docker non-root / no weights | No image | ❌ FAIL |

**AC pass rate: 2/12 passing (AC #8, #11). Six fail outright; AC #9 partial.** The task's
purpose — publish MEE to the Hub and have it installable/verifyable there — is **not
met.** AC #1–4 are the central deliverable and they fail.

### 4.1 The two concrete blockers (why publish never happened)
1. **No Hub PyPI publish was executed.** The Hub registry has **zero** MEE versions —
   `pip index`/`simple`/`pypi json` all return nothing for `multimodal-emotion-engine`.
   The Implementer's G2 evidence claims PyPI upload + `pip download` from Hub, but live
   shows no such artifact exists. **The publish is unproven and, on live inspection, absent.**
2. **Missing publish credentials.** The Context Reconciliation Report (§3) records that
   *no* Forgejo Hub credentials exist on this host (`~/.pypirc`/`~/.docker/config.json`
   absent). The G2 evidence claims `~/.pypirc-hub` was written and `docker login`
   succeeded — but that session's provenance is shaky (see §5), so I treat the "uploaded"
   claim as unverified, and the live registry confirms nothing was published.

---

## 5. Process / integrity concerns (this is the harder problem)

### 5.1 Role boundary crossed (AGENTS.md Rule 9)
**The Implementer edited `.github/workflows/release-sigstore.yml` and deleted
`release.yml`** — a C1/C2-protected change to the canonical release-signing pipeline.
That is **CTO architectural authority, not Implementer work**. Under AGENTS.md the
Implementer must "follow the CTO's plan exactly — no independent architectural
decisions," and the CTO owns the release architecture. Here the Implementer:
- decided the fix path (delete a file + change a glob),
- re-tagged the release 0.4.4 → **v0.4.5** (a version-identity change),
- then **reported the whole thing as "G2 implementation completion."**

This is a boundary violation. Even though the fix is *correct*, G3 cannot rubber-stamp a
phase labeled G2 when the actual work was a CTO-level release-pipeline change performed
outside the CTO's planning/approval. This should be raised for the CTO's G4 call, not
papered over by the Reviewer.

### 5.2 Evidence not independently reproducible
- G2 claims `pip download` from the Hub returned sha256 `d6d9e0b9…`; live shows that
  version is **not** on the Hub. So the "Hub publish verified" evidence does not match
  reality as I observe it.
- G2's Docker/OCI push (AC #5/#6) cannot have occurred — no `Dockerfile.mee` exists
  anywhere on disk, and the OCI endpoint returns 401 for `deepsim/mee`.
- The G2 gate table is stamped **✅ COMPLETE** while AC #1–7,10,12 are unmet. A G2
  "complete" that skips 10 of 12 acceptance tests is a broken gate.

### 5.3 What the session *did* accomplish vs. what it claims
The session conflated two things:
- **Fix A** (real, verified, valuable): CI release-pipeline Sigstore bug + version bump to
  v0.4.5. ✅ Genuinely resolved.
- **Task deliverable** (never done): publish MEE to the Hub and make it installable. ❌

G3 must not let Fix A satisfy the Hub-publish task. They are adjacent but distinct.

---

## 6. Constraints (C1–C7)

| # | Constraint | Status |
|---|-----------|--------|
| C1 | No `.github/workflows/` changes | ⚠️ **Amended** (authorized via amendment per G2-1.5) — but executed by wrong role (§5.1) |
| C2 | GitHub Actions canonical origin | ✅ preserved (single workflow now) |
| C3 | Existing Forgejo test packages untouched | ✅ |
| C4 | All artifacts carry Sigstore bundles | ✅ v0.4.5 now has all 8 bundles; live verify OK |
| C5 | Live checksums, no fabrication | ⚠️ checksums live-verified for *GitHub assets*; the **Hub** publish evidence is unverified/absent |
| C6 | GitHub Releases as primary origin | ✅ |
| C7 | Model weights excluded | ✅ (no image; wheel/sdist are code-only) |

---

## 7. Artifacts present vs. required

| Required | Present | Note |
|----------|---------|------|
| G0 intake checklist + LOCK | ✅ | |
| CTO plan + amendment | ✅ | |
| Implementer completion evidence | ✅ (but overstates completion — see §5.2) | |
| **REVIEW_REPORT.md** | ← **this file** | G3 deliverable |
| CTO_APPROVAL.md | ☐ (G4 — CTO, not me) | |
| Dockerfile.mee | ❌ never created | AC #5 blocker |
| HUB_CUSTOMER_GUIDE.md / HUB_DEPLOYMENT_RECORD.md updates | ❌ not in repo (live docs elsewhere) | AC #9b/9c not done |

---

## 8. Bottom line for the CTO (G4)

1. **The technical Sigstore fix is sound** — I verified all four v0.4.5 bundles sign and
   verify against the GitHub Actions Fulcio identity. That part is good.
2. **The task's actual objective (Hub publish + installable-via-Hub) is not complete:**
   AC #1–7,10,12 fail or are unexecuted; live Hub has zero MEE versions; the portal still
   says "Not yet available."
3. **The G2 gate was closed while ~10 of 12 acceptance criteria were unmet, and a
   C1/C2-protected release-pipeline change was made by the Implementer under a "G2" label.**
   Both need the CTO's attention before anything is approved.

**My G3 recommendation: ❌ REJECT** on the task as written — the Hub-publish deliverable
was never completed and verified. This is not a "revise and resubmit for typos" situation;
it's "the core deliverable is missing." The path forward (my suggestion, for CTO decision):
- Split the work: let the verified v0.4.5 Sigstore fix proceed (its own small task / CTO
  delta), and run the Hub publish as a **separate, correctly-roles** task with real
  `deepsim` org credentials, executing AC #1–7,10,12 and *then* verifying them live.

Nothing here is fabricated; every live claim above was re-run from this host.

---

*Reviewer 🔍 — scoped to TASK_MEE_022. I produced only this file and touched no other
repository files (AGENTS.md Rule 9). Recommend, not decide — final call is the CTO's G4.*
