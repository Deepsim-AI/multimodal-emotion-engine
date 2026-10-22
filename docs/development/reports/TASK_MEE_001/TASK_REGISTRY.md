# MEE — DS-EO Task Registry (TASK_MEE_001 … TASK_MEE_011)

**Project:** Multimodal Emotion Engine (MEE)
**Source of Truth:** `multimodal-emotion-engine/MULTIMODAL_EMOTION_ENGINE_PROJECT_PLAN.md`
**Created:** 2026-09-19 (PM task breakdown)
**Per-convention artifacts** live under each task folder:
`multimodal-emotion-engine/docs/development/reports/<TASK_ID>/`

## Task Sequence & Dependency Chain

| Task ID | Title | Phase | Deps | Status |
|---------|-------|-------|------|--------|
| **TASK_MEE_001** | Project Setup & Architecture | 1 | — | Ready (planning) |
| **TASK_MEE_002** | Vision Emotion Model Evaluation | 2 | 001 | Ready |
| **TASK_MEE_003** | Voice Emotion Model Evaluation | 3 | 001 | Ready |
| **TASK_MEE_004** | Vision Emotion Engine | 4 | 001, 002 | Ready |
| **TASK_MEE_005** | Voice Emotion Engine | 5 | 001, 003 | Ready |
| **TASK_MEE_006** | Multimodal Emotion Fusion | 6 | 004, 005 | Ready |
| **TASK_MEE_007** | Temporal User State | 7 | 006 | Ready |
| **TASK_MEE_008** | Emotion Demonstration UI | 8 | 001, 004, 005, 006, 007 | Ready |
| **TASK_MEE_009** | End-to-End Validation | 9 | 004, 005, 006, 007 | Ready |
| **TASK_MEE_010** | Jetson AGX Orin Deployment | 10 | 009 | Ready |
| **TASK_MEE_011** | Packaging & Documentation | 11 | 010 | Ready |
| **TASK_MEE_012** | Vision Performance Benchmark | — | 011 | CLOSED (2026-09-23) |
| **TASK_MEE_013** | Detection Frequency Control | — | 012 | CLOSED (G4 APPROVED) |
| **TASK_MEE_014** | Remote Access / Demo Distribution | 6 | 010, 011 | CLOSED (Phase 6 complete) |
| **TASK_MEE_016** | CUDA Compatibility — RetinaFace Detection | — | 013 | CLOSED |
| **TASK_MEE_017** | Camera Toggle + Voice Emotion "No Data" Fix | — | 016 | CLOSED |
| **TASK_MEE_018** | Remote Demo Public Access (Tailscale Funnel) + Stability | — | 017 | CLOSED (superseded by 035) |
| **TASK_MEE_019** | License Plan Selection & Purchase UI | 8 | 015 | CLOSED (v0.3.0) |
| **TASK_MEE_020** | License Hardening & Signed Distribution | Post-019 | 015, 019 | DRAFTED, awaiting CTO G1 |
| **TASK_MEE_035** | Remote Demo Public Access Migration to Pangolin | — | 018 | CLOSED (supersedes 018) |

> Registry table is maintained by PM. Tasks 012/013/014 use a lighter gate footprint; IDs 021–034
> are currently unused. See per-task folders for detailed status.

```text
TASK_MEE_001
      │
      ├──────────────┐
      ▼              ▼
TASK_MEE_002    TASK_MEE_003
      │              │
      ▼              ▼
TASK_MEE_004    TASK_MEE_005
      │              │
      └──────┬───────┘
             ▼
       TASK_MEE_006
             │
             ▼
       TASK_MEE_007
             │
             ▼
       TASK_MEE_008
             │
             ▼
       TASK_MEE_009  (validation gate before Jetson)
             │
             ▼
       TASK_MEE_010
             │
             ▼
       TASK_MEE_011
```

## Workflow (per AGENTS.md)

1. **PM** — defines tasks + `TASK_REQUEST.md` (requirements, acceptance criteria, deps). *(this registry)*
2. **CTO** — writes the detailed `CTO_PLAN.md` per task (architecture, exact file/symbol/line-range guidance, model selection).
3. **Implementer** — builds the approved plan, produces `IMPLEMENTATION_REPORT.md`.
4. **Reviewer** — validates the single task directory, produces `REVIEW_REPORT.md`.
5. **CTO** — G4 final approval (`CTO_APPROVAL.md`).
6. **PM** — Post-G4 closure (PROJECT_STATUS / CHANGELOG / PM_CLOSED) + local git commit. Remote push only with explicit user confirmation of target repo + branch.

## Artifacts per task folder

Each `docs/development/reports/<TASK_ID>/` contains at minimum:
- `TASK_REQUEST.md` (PM — requirements)
- `CTO_PLAN.md` (CTO — plan + acceptance criteria)
- `IMPLEMENTATION_REPORT.md` (Implementer)
- `REVIEW_REPORT.md` (Reviewer)
- `CTO_APPROVAL.md` (CTO, at G4)
