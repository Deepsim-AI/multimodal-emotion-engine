# TASK_MEE_022 — CTO PLAN (G1)

**Gate:** G1 — Planning
**Date:** 2026-10-25
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)

## Objective

Publish MEE v0.4.4 to Hub Forgejo registry across PyPI, OCI, and Generic channels with full integrity verification.

## Phase Summary & Artifacts

### Phase G2-1: Artifact Preparation (Implementer)

**Deliverables:**
1. Download Sigstore-signed wheel + sdist + .sigstore bundles from GitHub release
2. Generate/update `MEE_INTEGRITY_HASHES.txt` and `MEE_RELEASE_MANIFEST.json` for Hub
3. Create `Dockerfile.mee` in MEE repo root
4. Build multi-arch Docker image (arm64 + amd64) via `docker buildx`

**Exact work:**

| # | File/Action | Details |
|---|-------------|---------|
| 1 | GitHub release asset download | Download from GitHub API: wheel, sdist, `.sigstore.json` bundles, `MEE_RELEASE_MANIFEST.json` — use existing tag `v0.4.4` or create one if missing |
| 2 | Artifact integrity check | Run SHA-256 on downloaded artifacts; compare against published manifest. If mismatch → stop and report. |
| 3 | Create `Dockerfile.mee` | New file at `/home/deepsim/multimodal-emotion-engine/Dockerfile.mee` (~40 lines): python:3.12-slim base, pip install from wheel, add non-root user `dee`, HEALTHCHECK with `mee-lic status`, copy verify_release.sh |
| 4 | Build image via buildx | `docker buildx build --platform linux/amd64,linux/arm64 -t hub.deepsim.ai:8443/deepsim/mee:v0.4.4 -f Dockerfile.mee --push .` |

**Constraints:**
- Do NOT modify `.github/workflows/release.yml`, `release-sigstore.yml`, or any GitHub Actions file
- Do NOT run local `sigstore` signing — use GitHub-signed artifacts only
- Docker image MUST NOT include model weights

### Phase G2-2: Hub Registry Publishing (Implementer)

**Deliverables:**
5. Publish wheel + sdist to Hub PyPI registry
6. Push Docker image to Hub OCI registry
7. Publish generic tarball bundle to Hub Generic channel

**Exact work:**

| # | File/Action | Details |
|---|-------------|---------|
| 5 | PyPI upload (twine) | `twine upload --repository-url https://hub.deepsim.ai:8443/api/packages/deepsim/pypi/ dist/multimodal_emotion_engine-0.4.4*.whl dist/multimodal_emotion_engine-0.4.4.tar.gz` — verify with `.pypirc` credential file (create as non-committed `.gitignore`d secret) |
| 6 | Docker push | `docker push hub.deepsim.ai:8443/deepsim/mee:v0.4.4` — login first via `docker login hub.deepsim.ai:8443` with Forgejo PAT (non-committed) |
| 7 | Generic bundle | Create `mee-0.4.4.tar.gz` containing wheel, sdist, `CHECKSUMS.txt`, `MEE_RELEASE_MANIFEST.json`; upload via `curl -X PUT --data-binary @... https://hub.deepsim.ai:8443/api/packages/deepsim/generic/mee/0.4.4/mee-0.4.4.tar.gz` |

**Verification after each publish:**
- PyPI: `pip install --index-url https://hub.deepsim.ai:8443/pypi/simple/ multimodal-emotion-engine` (test in temp venv)
- OCI: `docker pull hub.deepsim.ai:8443/deepsim/mee:v0.4.4 && docker run --rm ... mee-lic status`
- Generic: `curl -o /tmp/mee-test.tar.gz https://hub.deepsim.ai:8443/.../mee-0.4.4.tar.gz && sha256sum -c CHECKSUMS.txt`

### Phase G2-3: Portal & Documentation (Implementer)

**Deliverables:**
8. Update Hub portal "Coming Soon" → "Available" for all three channels
9. Update `HUB_CUSTOMER_GUIDE.md`, `HUB_DEPLOYMENT_RECORD.md`, README install section

**Exact work:**

| # | File/Action | Details |
|---|-------------|---------|
| 8 | Portal update (Hub API or manual) | Use Hub portal admin API to update MEE product card status from "Coming Soon" to "Available", add `pip install`, `docker pull`, and `curl` commands |
| 9a | Update `docs/hub/HUB_CUSTOMER_GUIDE.md` (~20 line section for MEE install) | Include pip install from Hub, docker pull, generic tarball download with checksum verification |
| 9b | Update `docs/hub/HUB_DEPLOYMENT_RECORD.md` | Record publication timestamp, artifact hashes, verified endpoints, signing provenance |
| 9c | Update `README.md` install section | Add Hub registry as one of the installation options alongside PyPI and direct download |

### Phase G3: Review (Reviewer)

**Scope:** Exactly one task directory — `docs/development/reports/TASK_MEE_022/`

1. Verify all acceptance tests (AC #1-12) pass and are recorded
2. Verify no constraints violated (C1-C7 from task req)
3. Verify Docker image passes security checks (non-root, no weights, health check works)
4. Produce `REVIEW_REPORT.md` with approve/reject recommendation

### Phase G4: CTO Approval

- Review Implementer's acceptance test results and verification evidence
- Confirm all constraints respected
- Issue `CTO_APPROVAL.md` with final decision
- Do NOT execute Post-G4 duties

### Phase G5: PM Completion (separate session)

- Update `PROJECT_STATUS.md`, `CHANGELOG.md`, send PM_CLOSED notification
- Commit approved work to Git, push to remote after user confirmation

---

## Acceptance Criteria (mapped from TASK_REQ)

| AC # | Criterion | Verification Method | Expected |
|------|-----------|-------------------|----------|
| 1 | `pip install` base via Hub | temp venv test | ✅ installs |
| 2 | `pip install [vision]` via Hub | temp venv test | ✅ installs |
| 3 | `pip install [voice]` via Hub | temp venv test | ✅ installs |
| 4 | `pip install [demo]` via Hub | temp venv test | ✅ installs |
| 5 | Docker pull via Hub OCI | `docker pull` | ✅ pulls |
| 6 | Docker run `mee-lic status` | `docker run --rm ...` | ✅ responds |
| 7 | Generic curl download | `curl + sha256sum` | ✅ 200, bytes match |
| 8 | Sigstore verification | `verify_release.sh` | ✅ PASS |
| 9 | All Forgejo endpoints functional | Health check endpoints | ✅ responsive |
| 10 | Portal shows "Available" | Hub portal UI/API | ✅ badge visible |
| 11 | Test packages still accessible | Search Forgejo packages | ✅ present |
| 12 | Docker image non-root, no weights | Image inspection + `ls` in container | ✅ verified |

---

## Stop Conditions (from TASK_REQ)

- v0.4.4 build/sign fails on GitHub → stop and report
- Docker build fails → stop (do NOT publish broken image)
- Any acceptance test fails → stop and report
- Forgejo API errors on publish → stop after retries, report
- Sigstore verification fails → stop and report

---

## Constraints Enforced

- **C1:** No modifications to `.github/workflows/` files
- **C2:** GitHub Actions remains canonical release origin
- **C3:** Existing Forgejo test packages untouched
- **C4:** All artifacts carry original Sigstore bundles (no re-signing)
- **C5:** All checksums computed live, never fabricated
- **C6:** GitHub Releases path documented as primary signed-artifact origin
- **C7:** Model weights excluded from Docker image and all registry packages

---

## Implementation Notes for Implementer

1. **Credential management:** Create `.gitignore`d files for Hub credentials (`~/.pypirc-hub`, `~/.hub-docker-config`). Never commit secrets.
2. **GitHub release existence:** If no v0.4.4 tag/RELEASE exists on GitHub yet, that's a pre-condition blocker — do NOT create the release; report to CTO first. The task req says "MEE wheel (GitHub) ✅ signed" but HEAD `15dc500` is from MEE_020 worknotes — verify release actually exists.
3. **Docker buildx:** If buildx not available, fall back to single-arch arm64-only build with explicit documentation of the limitation.
4. **Honest documentation:** Document any gaps (e.g., if GitHub release doesn't exist yet, if multi-arch build fails, etc.). No fabrication.

---

## Model Pressure Management

| Phase | Required Models | Always Unload |
|-------|-----------------|---------------|
| G2 implementation | qwen3.6:35b (CTO), qwen3.8:27b (Implementer) | ornith-1.5:35b, laguna-xs-2.1 |
| G3 review | laguna-xs-2.1, qwen3.6:35b, nomic-embed-text | qwen3.8:27b, ornith-1.5:35b |
| Idle | nomic-embed-text only | all large models |

---

## Gate Status

| Gate | Status | Artifacts Required |
|------|--------|--------------------|
| G0 | ✅ Signed (PM intake) | `G0_INTAKE_CHECKLIST.md`, `LOCK.md` (RELEASED) |
| G1 | ✅ **Approved** (this file) | This `TASK_PLAN.md` |
| G2 | ☐ Pending | Implementer completion report + acceptance test results |
| G3 | ☐ Pending | Reviewer `REVIEW_REPORT.md` |
| G4 | ☐ Pending | `CTO_APPROVAL.md` |
| G5 | ☐ Pending (separate session) | `PROJECT_STATUS.md`, `CHANGELOG.md`, PM_CLOSED |

---

*End of TASK_MEE_022 CTO PLAN (G1).*
