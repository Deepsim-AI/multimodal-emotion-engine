# TASK REQUEST: MEE Hub Portal Update — "Available" Status

**Status:** PENDING — depends on TASK_REQ_MEE_HUB_PUBLISH completion
**Priority:** Medium
**Depends on:** MEE artifacts published to Hub registry (TASK_REQ_MEE_HUB_PUBLISH)

## Objective

Update the Hub portal (`hub-portal/index.html`) to reflect the new "Available"
status for all MEE distribution channels after publication is complete.

## Changes Required

### 1. Distribution channels table

| Channel | Before | After |
|---------|--------|-------|
| GitHub Releases (signed wheel) | ✅ Available | ✅ Available (unchanged) |
| Hub PyPI Registry | ⚠️ Coming Soon | ✅ Available |
| Hub OCI Registry | ⚠️ Coming Soon | ✅ Available |
| Hub Generic Packages | ⚠️ Coming Soon | ✅ Available |

### 2. Install guides

- **Python tab:** Change "Future method" → "Alternative method — Hub PyPI registry (Available)"
- **Docker tab:** Change "coming soon for MEE" → "Available"
- **Generic tab:** Change "coming soon for MEE" → "Available"
- Update all `coming soon` notes to reference the real artifacts

### 3. Product card badges

- Add badge: "Available on Hub" (green)
- Keep existing badges: v0.4.4, Python 3.10+, Jetson-Ready, Licensed

### 4. Verification section

- Add Hub-specific verification commands:
  - `pip install --index-url ... multimodal-emotion-engine`
  - `docker pull hub.deepsim.ai:8443/deepsim/mee:v0.4.4`
  - `curl ... /api/packages/deepsim/generic/mee/0.4.4/...`
- Keep GitHub-based `verify_release.sh` instructions

### 5. Licensing section

- No changes (already correct)

### 6. Engineering section

- Add link to MEE releases on Hub: `https://hub.deepsim.ai:8443/` (the portal itself)

## Acceptance

| # | Test | Expected |
|---|------|----------|
| 1 | Portal loads with "Available" badges | ✅ |
| 2 | All "Coming Soon" labels removed for MEE | ✅ |
| 3 | Install commands reference real Hub endpoints | ✅ |
| 4 | No broken links | ✅ |
| 5 | Portal still passes all previous acceptance tests | ✅ |

## Files to modify

- `hub-portal/index.html` (local + VPS `/opt/hub-portal/index.html`)

## Governance

This is a small UI update — PM can authorize directly, CTO review optional,
implementer makes the change, reviewer verifies, PM accepts.
