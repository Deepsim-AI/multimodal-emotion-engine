# TASK REQUEST: MEE Hub Distribution — Publish to Forgejo Registry

**Status:** PENDING — awaiting PM intake → CTO plan → implementation → review → acceptance
**Priority:** High
**Depends on:** Hub portal deployed (✅ complete), MEE v0.4.4 source in local repo

## Objective

Publish MEE v0.4.4 to the Hub registry (`hub.deepsim.ai:8443`) across all three
distribution channels, with full integrity verification and honest documentation.

## Current State

| Item | Status |
|------|--------|
| MEE source (local) | ✅ v0.4.4 at `/home/deepsim/multimodal-emotion-engine/` |
| MEE wheel (local) | ⚠️ v0.4.0 only (108 KB, unsigned) — v0.4.4 wheel NOT built |
| MEE wheel (GitHub) | ✅ v0.4.4 signed wheel on private GitHub repo (Sigstore) |
| MEE in Hub PyPI | ❌ Not published |
| MEE in Hub OCI | ❌ Not published |
| MEE in Hub generic | ❌ Not published |
| Dockerfile | ❌ Does not exist in MEE repo |
| Release workflow | ✅ `.github/workflows/release.yml` (builds wheel + sdist, signs with Sigstore) |
| Verify script | ✅ `tools/verify_release.sh` (SHA-256 + Sigstore) |

## Deliverables

### 1. Build MEE v0.4.4 artifacts

- Build wheel + sdist from the v0.4.4 source (local or via GitHub Actions)
- Generate integrity anchor (`MEE_INTEGRITY_HASHES.txt`)
- Compute SHA-256 manifest (`MEE_RELEASE_MANIFEST.json`)
- Sign with Sigstore (Fulcio keyless) — **reuse existing `release.yml` workflow**
- **Do NOT modify** the existing GitHub Actions or Sigstore workflow

### 2. Publish to Hub PyPI registry

- Upload `multimodal_emotion_engine-0.4.4-py3-none-any.whl` to
  `https://hub.deepsim.ai:8443/api/packages/deepsim/pypi/`
- Upload sdist (`multimodal_emotion_engine-0.4.4.tar.gz`)
- Verify: `pip install --index-url https://hub.deepsim.ai:8443/... multimodal-emotion-engine`
- Verify: `pip install --index-url ... multimodal-emotion-engine[vision]`
- Verify: `pip install --index-url ... multimodal-emotion-engine[voice]`

### 3. Build and publish MEE Docker/OCI image

- **Create** a Dockerfile in the MEE repo (new deliverable)
- Requirements:
  - Python 3.10+ base (match `requires-python = ">=3.10"`)
  - Install MEE wheel from the build step
  - Include optional extras as separate image tags or build args
  - Health check endpoint
  - Non-root user
  - Layer caching for dependencies
- Build multi-arch image if practical (Jetson ARM64 + x86_64)
- Push to `https://hub.deepsim.ai:8443/deepsim/mee:v0.4.4`
- Verify: `docker pull hub.deepsim.ai:8443/deepsim/mee:v0.4.4`
- Verify: `docker run --rm hub.deepsim.ai:8443/deepsim/mee:v0.4.4 mee-lic status`

### 4. Publish MEE generic binaries/SDKs

- Determine what "generic binary" means for MEE:
  - Option A: Pre-built wheel + sdist as a tarball bundle
  - Option B: Platform-specific binaries (Jetson, x86_64)
  - Option C: SDK bundle (wheel + model weights + docs)
- Decision needed from CTO — which artifacts make sense for the generic channel
- Upload to `https://hub.deepsim.ai:8443/api/packages/deepsim/generic/mee/0.4.4/`
- Include `CHECKSUMS.txt` and `MEE_RELEASE_MANIFEST.json`
- Verify: `curl` download + `sha256sum -c`

### 5. Update portal

- Change "Coming Soon" → "Available" for all three channels
- Update install instructions with real `pip install`, `docker pull`, `curl` commands
- Add MEE-specific verification instructions
- Update product card with "Available on Hub" badge

### 6. Documentation

- Update `HUB_CUSTOMER_GUIDE.md` with MEE-specific install instructions
- Update `HUB_DEPLOYMENT_RECORD.md` with MEE publication evidence
- Update MEE `README.md` install section to include Hub registry option
- Document the complete artifact provenance chain (build → sign → publish → verify)

### 7. Acceptance tests

| # | Test | Expected |
|---|------|----------|
| 1 | `pip install multimodal-emotion-engine` via Hub | ✅ 200, installs |
| 2 | `pip install multimodal-emotion-engine[vision]` via Hub | ✅ 200, installs |
| 3 | `pip install multimodal-emotion-engine[voice]` via Hub | ✅ 200, installs |
| 4 | `pip install multimodal-emotion-engine[demo]` via Hub | ✅ 200, installs |
| 5 | `docker pull hub.deepsim.ai:8443/deepsim/mee:v0.4.4` | ✅ pulls |
| 6 | `docker run ... mee-lic status` | ✅ responds |
| 7 | `curl` generic download | ✅ 200, correct bytes |
| 8 | `sha256sum -c CHECKSUMS.txt` | ✅ all match |
| 9 | `verify_release.sh` (Sigstore) | ✅ PASS |
| 10 | Forge regression (all endpoints) | ✅ |
| 11 | Portal shows "Available" for all channels | ✅ |
| 12 | Test packages (disposable) still accessible | ✅ |

## Constraints

- **Do NOT modify** GitHub Actions or Sigstore workflows
- **Do NOT change** the canonical release-signing process (GitHub Actions remains origin)
- **Do NOT delete** existing test packages from the registry
- **Do NOT publish** unsigned artifacts — every artifact must have Sigstore signature
- **Do NOT fabricate** checksums or verification results
- **Preserve** the GitHub Releases path as the canonical signed artifact origin
- **Do NOT expose** MEE model weights in the registry (separate CDN distribution)

## Stop conditions

- If the v0.4.4 build fails, stop and report
- If Sigstore signing fails, stop and report
- If Docker build fails, stop and report (do NOT publish a broken image)
- If any acceptance test fails, stop and report

## Governance

PM intake → CTO plan → Implementer execution → Independent Reviewer → PM acceptance
