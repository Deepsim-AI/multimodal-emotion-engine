# Review Report — TASK_MEE_035

**Task ID:** TASK_MEE_035
**Gate:** G3 — Independent Review
**Date:** 2026-10-16
**Reviewed By:** Senior Code Reviewer 🔍

---

## Scope

Review is limited to the TASK_MEE_035 deliverables: the client default-URL change,
the two operator shell scripts, and the three remotedemo docs + CHANGELOG entry.
The control-plane fix (Pangolin `meews` target `method`) is out of repo scope and
was verified against the control-plane DB, not the working tree.

## Findings

| # | Area | Observation | Severity |
|---|------|-------------|----------|
| 1 | `index.html` default | Default WS URL is now `wss://meews.deepsim.ai:8443/`; no `tail0d394d` default remains. Manual entry and localhost branches preserved. | ✅ |
| 2 | `index.html` correctness | Inline JS passes `node --check`; no syntax regressions. | ✅ |
| 3 | `start.sh` | Funnel removed from default path (legacy-only); 3-step start; idempotent; live `/healthz` check added. `bash -n` clean. | ✅ |
| 4 | `watchdog.sh` | Header clarifies Pangolin vs Funnel role; behaviour unchanged (keeps local 8910 alive). `bash -n` clean. | ✅ |
| 5 | Docs consistency | ACCESS / DEPLOYMENT / SECURITY all list Pangolin as primary and Funnel as deprecated/legacy. No contradictory Funnel-as-primary statements remain. | ✅ |
| 6 | CHANGELOG | TASK_MEE_035 entry present under `[Unreleased]`, accurate to the diff. | ✅ |
| 7 | Live path | `meews.deepsim.ai:8443/healthz` → 200; WS connect OK; auth gate (`bad_token`) intact. | ✅ |

## Minor / informational (no action required)

- **Self-signed page cert** on `mee.deepsim.ai:8443` still requires the browser to
  accept a certificate warning. This is expected for the prototype and is now
  documented in ACCESS.md; replacing it with a public-CA cert is a separate,
  out-of-scope task.
- **Funnel still installed** on the Jetson as a legacy fallback. Not started by
  default; safe to leave. If Pangolin is retired entirely, the Funnel process
  (`tailscale funnel 8910`) can be stopped and the legacy doc notes removed.
- **7 MediaPipe tests (MEE_016)** fail in this environment due to a broken
  `import matplotlib` (system matplotlib vs numpy 2.2.6). This is a pre-existing
  **environment** dependency clash, **not** a MEE_035 regression; the 30 other
  vision/health tests pass. Fix is env-side (e.g. `pip install --upgrade matplotlib`),
  not a repo change.

## Recommendation

**RECOMMEND APPROVAL.** The implementation is minimal, correct, and verified
end-to-end. The root cause was correctly identified as a control-plane target
misconfiguration (`method` HTTPS→http) and fixed there; the repo changes are
limited to client defaults, operator tooling, and documentation — exactly the
scope defined in the plan. No regressions observed.
