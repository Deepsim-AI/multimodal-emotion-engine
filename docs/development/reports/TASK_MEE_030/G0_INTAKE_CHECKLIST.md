# G0_INTAKE_CHECKLIST - TASK_MEE_030: Enable One-Way Forgejo→GitHub Mirror

**Task ID:** TASK_MEE_030
**Gate:** G0 - PM Intake (mechanical sign-off checklist)
**Date:** 2026-10-26 (PDT)
**Prepared by:** PM 📋 (ornith-1.5:35b)
**Companion to:** TASK_MEE_026_B (one-way mirror mechanism spec, CLOSED G0–G5 2026-10-26)
**Parent authorization:*** *** *** Decision 2 (one-way mirroring APPROVED IN PRINCIPLE) + owner
trigger-scope clarification 2026-10-26.

> **Scope of this task:** This task *enables* the mirror mechanism specified in MEE_026_B. This is
> an *implementation* task — G2 here deploys config, credentials, and the webhook. This is the
> **first task** that authorizes production service changes for the mirror. It does NOT authorize any
> change outside the mirror mechanism (no signing changes, no repo permission changes, no publishing).

## 1. Task ID Verification

| Check | Result |
|-------|--------|
| TASK_MEE_030 available by convention | Next unused ID (028, 029, 035 taken) OK |
| No conflicting in-flight task | Confirmed - no TASK_MEE_030/ directory exists OK |

## 2. Intake Artifacts Present

| Artifact | Status |
|----------|--------|
| G0_INTAKE_CHECKLIST.md (this file) | written (G0) |
| LOCK.md | this file (PENDING until released) |

## 3. Parent Task Authorization

**TASK_MEE_026_B** (spec, CLOSED G5 2026-10-26) specified the one-way mirror mechanism. Owner has now
authorized **enabling** it (MEE_030). This task implements the mechanism — NOT a new design.

Per MEE_024 Decision 2:
- One-way: Forgejo (canonical) → GitHub (mirror). **Never GitHub→Forgejo.**
- **Public repos auto-mirror**; private/commercial repos require per-repo owner allowlist approval.
- MEE (`Deepsim-AI/multimodal-emotion-engine`) is public → qualifies for auto-mirror.

## 4. Constraints (authoritative)

| Constraint | Source |
|------------|--------|
| One-way ONLY (Forgejo → GitHub). GitHub push must be rejected by permission. | MEE_024 Decision 2 |
| Public repos auto-mirror; private/commercial require per-repo owner allowlist. | MEE_024 Decision 2 |
| Bot token scope: `repo` + `read:packages` only, never admin, never delete_repo. | MEE_026_B §4.2 |
| Bot token stored in Forgejo secrets (encrypted at rest), NOT in repo. | MEE_026_B §4.2 |
| No production service change outside the mirror mechanism. | Scope |
| Do NOT modify repository permissions beyond mirror requirement. | MEE_024 Decision 2 |
| Mirror must stay in sync (drift detection + alerting). | MEE_026_B §4.3 |

## 5. Baseline Verification (G0 read-only)

| Check | Result |
|-------|--------|
| Forgejo is canonical (hosts real PyPI packages, source of truth) | ✅ per MEE_024 |
| GitHub is currently a manual mirror (pushed alongside Forgejo) | ✅ current remote state |
| Existing org token at `/home/deepsim/Documents/shouke/workspace/bot_github_org_token.txt` (reference only) | ✅ exists — must NOT be repurposed |
| MEE repo is public (auto-mirror) | ✅ |

## 6. G0 Read-Only Questions for CTO (G1)

These must be answered in the CTO G1 plan (not decided here):
1. **Trigger granularity:** mirror full repo (`--mirror`) or release-only (`refs/tags/v*.*.*`)?
   MEE currently has both branch + tag pushes; a full mirror keeps branches in sync.
2. **Mirror runner deployment:** where does it run (scheduled job on VPS, Forgejo webhooks, or a
   lightweight webhook handler)? Actions lacks native OIDC — but OIDC is irrelevant for a plain
   `git push`.
3. **Failure alerting channel:** where do mirror failures alert (email, Slack, webhook log only)?
4. **Allowlist storage:** how is the private/repo allowlist enforced (Forgejo setting, or runner logic
   with a hardcoded allowlist)?

## 7. Critical Governance Note

This is the **first production-impact task** in the mirror lineage. G3 review scrutiny must be
proportionate to the risk of accidentally exposing a private repo to GitHub, or of the one-way
direction being violated. The CTO must ensure:
- The mirror runner **fails closed** on any scope violation.
- The GitHub mirror token **lacks write** to the canonical (Forgejo) repo.
- No private/commercial repo auto-mirrors without explicit owner allowlist approval.

---
*G0 process artifact — nothing implemented.*
