# LOCK - TASK_MEE_030

**Status**: PENDING (G0 intake lock)
**Locked at**: 2026-10-26 (PDT)
**Scope**: G0-G2 phase for enabling the one-way Forgejo→GitHub mirror mechanism (MEE_026_B spec)

## Artifacts

| File | Status |
|------|--------|
| G0_INTAKE_CHECKLIST.md | Written (G0) |
| LOCK.md | This file (PENDING until released) |

## Scope note

**First implementation task in the mirror lineage.** Deploys config, credentials, and the Forgejo
push webhook that drives the one-way mirror. Production-impact — highest governance scrutiny.
One-way ONLY (Forgejo → GitHub); public repos auto-mirror; private/commercial require per-repo
owner allowlist. Fails closed on any scope violation.
