# TASK REQUEST: MEE Development — DS-EO Workflow

**Status:** PENDING — this is a meta-request for the DS-EO process itself
**Priority:** Per MEE roadmap
**Trigger:** When we return to MEE development work

## Objective

Establish the DS-EO engineering workflow for ongoing MEE development. This is
not a single task but a process definition that governs how all future MEE
work flows through the engineering organization.

## DS-EO Process (per AGENTS.md)

```
┌─────────────────────────────────────────────────────────────────┐
│  DS-EO Engineering Organization                                 │
│                                                                 │
│  PM 📋 (ornith-1.5:35b)                                        │
│  ├── Intake: detect need, request CTO task creation             │
│  ├── Coordinate lifecycle between all phases                    │
│  ├── Verify artifact integrity                                  │
│  ├── Execute Post-G4 completion checklist                       │
│  └── Commit approved work to Git                                │
│                                                                 │
│  CTO 🏗️ (qwen3.6:35b)                                          │
│  ├── Architecture review                                        │
│  ├── Task planning (acceptance criteria from specs)             │
│  ├── Create TASK directories (TASK_<YYYYMMDD>_<NNN>)            │
│  ├── Review Implementer output + Reviewer findings             │
│  └── Final approve/reject (G4)                                  │
│                                                                 │
│  Implementer 💻 (qwen3.8:27b)                                   │
│  ├── Execute approved plan exactly                              │
│  ├── Working code + tests + documentation                       │
│  ├── Report test results + deviations                           │
│  └── Deliver implementation report to Reviewer                  │
│                                                                 │
│  Reviewer 🔍 (laguna-xs-2.1:q4_K_M)                             │
│  ├── Verify against CTO plan + specs                            │
│  ├── Code quality, test coverage, regression impact             │
│  └── Produce REVIEW_REPORT.md (recommend, not approve)          │
└─────────────────────────────────────────────────────────────────┘
```

## Gate Sequence

```
G0: PM intake → task request accepted
G1: CTO plan → TASK_PLAN.md with acceptance criteria
G2: Implementer → code + tests + IMPLEMENTATION_REPORT.md
G3: Reviewer → REVIEW_REPORT.md (recommend approve/reject)
G4: CTO approval → CTO_APPROVAL.md (final decision)
G5: PM completion → PROJECT_STATUS.md, CHANGELOG.md, PM_CLOSED
```

## MEE-Specific Considerations

1. **License hardening (MEE_020)** — already complete (v0.4.0+)
2. **Sigstore signing** — already complete (v0.4.1-v0.4.4)
3. **Hub distribution** — in progress (TASK_REQ_MEE_HUB_PUBLISH)
4. **Future MEE work** — all new features, bug fixes, and improvements
   must follow this process

## Model Pressure Management

Per AGENTS.md §3.5:
- Max 3 large models loaded simultaneously
- Unload idle models between phases
- `ollama rm` NEVER without explicit user permission
- If compaction fails → write COMPACTION_FAILURE.md, request fresh session

## Task Request Template

Each MEE development task should be submitted as:

```markdown
# TASK REQUEST: <title>

**Status:** PENDING
**Priority:** High | Medium | Low
**Objective:** <one sentence>

## Context
<what prompted this, what's the current state>

## Deliverables
1. <specific deliverable>
2. <specific deliverable>

## Acceptance Criteria
- [ ] <criterion 1>
- [ ] <criterion 2>

## Constraints
- <constraint 1>
- <constraint 2>

## Governance
PM intake → CTO plan → Implementer → Reviewer → PM acceptance
```

## Governance

This meta-task is authorized by the gateway owner. PM should confirm
intake when the first MEE development task is ready for the DS-EO pipeline.
