# TASK_MEE_025_A — Owner Decisions and Authorization

**Date:** 2026-10-25 ~21:51 PDT  
**Author:** Shouke Wei (gateway-owner)  

## Decision 1: POC Repository — APPROVED

Approve creation of private Forgejo repository `deepsim-hub-test-signing-poc`, subject to G0 sign-off completion.

### Conditions:
- Keep isolated from production MEE repositories and workflows
- Use synthetic artifacts and dedicated test credentials only
- Document access controls, ownership, retention, and cleanup procedures
- No GitHub mirroring authorized
- No official release publication authorized
- No production credential use authorized

## Decision 2: Signing Evaluation — SIMULATION FOLLOWED BY REAL OIDC VALIDATION

Proceed in two stages:

**Stage A (Simulation):** Self-signed certificates + manually distributed trust material to validate basic signing, verification, tamper detection, trust management, rotation/recovery, failure handling.

**Stage B (Real OIDC Validation):** Investigate and test actual OIDC identity flow intended for proposed architecture. Must verify deployed Forgejo version (17.0.0+gitea-1.22.0) capabilities rather than assuming OAuth2 support implies required workflow OIDC token support.

### Requirements:
- Use isolated POC repository and dedicated test workflow where feasible
- Validate issuer, audience, repository/workflow identity, certificate identity
- Test unauthorized-workflow rejection
- Test independent customer verification paths
- If native Forgejo OIDC integration is not feasible: document evidence, alternatives, trust implications, required infrastructure
- Do NOT claim production readiness from simulation results alone
- Do NOT modify production signing workflows or weaken authentication
- Any production infrastructure changes require separate authorization

## Decision 3: Timeline — CONFIRMED AS A PLANNING GOAL

14-calendar-day target measured from applicable authorization to begin the POC.
- Report blockers promptly
- Revise estimate if needed
- Do NOT bypass gates or security criteria to meet target
- Deliverable is reproducible, evidence-backed evaluation and recommendation, not production migration

---
*End of owner decisions for TASK_MEE_025_A.*
