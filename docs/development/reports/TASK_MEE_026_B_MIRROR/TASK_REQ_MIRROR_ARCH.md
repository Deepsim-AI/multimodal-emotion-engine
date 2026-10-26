# TASK REQUEST: MEE Mirroring — Forgejo to GitHub Repository Mirroring Architecture

**Task ID:** Pending (proposed: TASK_MEE_026 or similar per DS-EO convention)  
**Status:** PENDING — awaiting PM intake  
**Priority:** Medium  
**Depends on:** TASK_MEE_024 decision 2 (one-way mirroring approved in principle)  

## Objective

Design and specify the Forgejo-to-GitHub one-way mirror architecture for explicitly approved
Deepsim repositories, including eligibility criteria, publication controls, synchronization
behavior, credential management, failure handling, and audit evidence.

## Context

Per TASK_MEE_024 decision 2, the owner approves the principle of one-way mirroring from Forgejo
to GitHub but does NOT authorize enabling mirroring under this decision alone. This task produces
the architecture specification and controls; a separate task will implement it.

The MEE repo (Deepsim-AI/multimodal-emotion-engine) is already published to GitHub via TASK_MEE_022
G5 closeout commits. The mirror bot token at `/home/deepsim/Documents/shouke/workspace/bot_github_org_token.txt`
serves as a reference but production mirroring requires its own scoped credential and governance.

## Deliverables

1. **Repository eligibility document** — criteria for which repos qualify (open-source, approved list)
2. **Publication control specification** — manual approval gate per repo or automated whitelist design
3. **Synchronization behavior design** — push-only, conflict resolution, lag monitoring thresholds
4. **Credential architecture** — mirror bot token scope, storage in Forgejo secrets, rotation procedure
5. **Failure handling design** — alerting, retry policy, manual fallback procedures
6. **Audit evidence format** — webhook log entries, sync verification checksum comparison procedure
7. **Private/commercial repo exclusion mechanism** — explicit controls preventing accidental publication

## Acceptance Criteria

- [ ] AC-1: Repository eligibility criteria documented and approved by owner
- [ ] AC-2: Mirror bot token scope defined (repo + read:packages only, no admin/delete)
- [ ] AC-3: Synchronization verification procedure confirms matching checksums between Forgejo and GitHub
- [ ] AC-4: Audit log format defined for all sync events (success/failure)
- [ ] AC-5: Private/commercial repo exclusion mechanism design documented and validated
- [ ] AC-6: Architecture document submitted for separate implementation task approval

## Constraints

- This task is architecture specification only — no code changes, no configuration, no production deployment
- Do NOT modify any repository permissions or mirroring settings under this task alone
- Private/commercial/internal repositories must remain excluded unless explicitly approved per eligibility criteria
- All work based on verified facts (Forgejo v17.0.0+gitea-1.22.0 API capabilities, not assumptions)

## Governance

PM intake → CTO plan → Architecture specification → Reviewer → CTO approval

---
*End of TASK_REQ for Mirror Architecture specification.*
