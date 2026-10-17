# G4 Approval — TASK_MEE_035: Remote Demo Public Access Migration to Pangolin

**Task ID:** TASK_MEE_035
**Gate:** G4 — CTO Final Approval
**Date:** 2026-10-16
**Approved By:** CTO 🏗️

---

## Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Public WS `/healthz` 200 | ✅ PASS | `curl -sk https://meews.deepsim.ai:8443/healthz` → `200 {"status":"ok"}` |
| WS handshake (101) via real client | ✅ PASS | `websockets.connect("wss://meews.deepsim.ai:8443/")` → CONNECT OK |
| Auth gate intact (no open endpoint) | ✅ PASS | probe token → `{"type":"error","code":"bad_token"}` |
| Served page carries new default | ✅ PASS | `grep MEE_WS_PUBLIC` → `wss://meews.deepsim.ai:8443/` |
| No stale Funnel default in `index.html` | ✅ PASS | `grep 'urlEl.value = .*tail0d394d'` → none |
| JS syntax | ✅ PASS | `node --check` on inline script |
| Shell syntax | ✅ PASS | `bash -n` start.sh / watchdog.sh |
| Docs list Pangolin primary, Funnel legacy | ✅ PASS | ACCESS / DEPLOYMENT / SECURITY reviewed |
| CHANGELOG entry | ✅ PASS | `[Unreleased]` TASK_MEE_035 entry |
| Committed + pushed to `origin/master` | ✅ PASS | `3ef40ed..72f383c`; working tree clean |

## CTO Decision

**✅ APPROVED — TASK_MEE_035: G4 PASS**

The public-access failure was correctly root-caused to a Pangolin control-plane
target misconfiguration (`meews` target `method` HTTPS→HTTP) and fixed there; the
repository changes are confined to the client default URL, the two operator
scripts, and the remotedemo documentation — precisely the in-scope surface. The
live path is verified end-to-end (health + handshake + auth gate), no regressions
were introduced, and the work is committed and pushed. All acceptance criteria met.
