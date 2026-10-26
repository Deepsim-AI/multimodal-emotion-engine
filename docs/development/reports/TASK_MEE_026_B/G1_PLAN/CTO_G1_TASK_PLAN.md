# G1 TASK PLAN — TASK_MEE_026_B: One-Way Forgejo→GitHub Mirror Mechanism

**Task ID:** TASK_MEE_026_B
**Gate:** G1 — CTO Plan (specification only; no implementation)
**Date:** 2026-10-26 (PDT)
**Author:** CTO 🏗️ (qwen3.6:35b)
**Parent authorization:** TASK_MEE_024 Decision 2 ("APPROVED IN PRINCIPLE") + owner trigger-scope clarification 2026-10-26.
**Scope:** Specification deliverable. **Zero code changes, zero config, zero production service change, zero new credentials provisioned.** This plan is a design doc.

---

## 1. What This Task Delivers

A single **one-way mirror mechanism** spec: Forgejo (canonical) → GitHub (mirror), webhook-driven
`git push --mirror`, with a **tiered trigger**:

| Repo class | Trigger | Control |
|------------|---------|---------|
| Public / open-source | Auto-mirror | Any push to Forgejo syncs to GitHub. No per-push approval. |
| Private / commercial / internal | Not mirrored by default | Owner allowlist approval **per repo** before mirroring. Backup is a valid reason but must be explicitly authorized. |

**MEE (`Deepsim-AI/multimodal-emotion-engine`) is public → auto-mirrors.** This is the only confirmed
public repo today (Forgejo has no other mirrorable repos). The spec is mechanism-first so it applies
to whatever repo qualifies next.

---

## 2. Design — Component Responsibilities

Forgejo is canonical source of truth; GitHub is mirror-only. Mirror is a **single mechanism**, not
re-spun per repo. Each repo is tagged at Forgejo as `public` (auto-mirror) or `private` (allowlist).

| Component | Responsibility |
|-----------|---------------|
| **Forgejo** (forge.deepsim.ai:8443) | Canonical source of truth (code, branches, tags, releases, PyPI/OCI storage). Emits webhook. |
| **GitHub** (github.com/Deepsim-AI/) | One-way mirror only. Never the signing authority or source of truth. |
| **Mirror webhook (Forgejo)** | On push events, triggers the mirror runner per the repo's public/private tag. |
| **Mirror runner** | `git push --mirror <github_mirror_url>` on authorized repos; skips allowlist-gated repos. |
| **Allowlist (Forgejo setting)** | List of private/commercial repo names permitted to mirror — owner-managed, never auto. |

---

## 3. Acceptance Criteria (for the spec)

| # | AC | Verification method |
|---|----|---------------------|
| 1 | Mirror direction documented: Forgejo → GitHub, one-way only | Spec states one-way; no GitHub→Forgejo path in design |
| 2 | Public repos auto-mirror; private/commercial require per-repo owner allowlist | Tiered trigger table + allowlist gate in spec |
| 3 | Mechanism specified: webhook event + `git push --mirror` | Design section on webhook + runner |
| 4 | Bot token scope defined: repo + read:packages only, never admin | Credentials section |
| 5 | Sync verification + audit defined (checksums, webhook logs) | Audit section |
| 6 | Failure handling defined (alerting, retry, manual fallback) | Failure section |
| 7 | Private/commercial exclusion mechanism documented | Allowlist + tag mechanism in spec |

---

## 4. Design Details (to be written in the spec deliverable)

### 4.1 Webhook + Runner
- Forgejo **push webhook** → mirror runner (runs inside the runner or a scheduled job, not Forgejo Actions since Actions lacks native OIDC — note but don't require OIDC for a plain git push).
- Runner reads the pushed repo's `public`/`private` tag; mirrors only `public`.

### 4.2 Token
- Dedicated mirror bot token, scope **repo + read:packages**, never admin, never delete_repo.
- Stored in Forgejo secrets, not in the repo.

### 4.3 Sync verification + audit
- Post-mirror checksum comparison between Forgejo release assets and GitHub mirror (detect drift).
- Webhook logs + sync verification checksums for audit trail.

### 4.4 Failure handling
- Retry policy, alerting on repeated failures, manual fallback (`git push --mirror` from a trusted host).

---

## 5. Deliverable

A single specification document `TASK_MEE_026_B_MIRROR_ARCH_SPEC.md` at repo root (`docs/development/reports/TASK_MEE_026_B/`), covering sections 4.1–4.4. No code, no config, no production change.

## 6. Guardrails

- AGENTS.md Rule 9: spec-only; no implementation, no creds, no prod service.
- R-SI-2: spec is a document, not a code plan — no file/symbol/line-range edits required.
- Implementation of this mechanism is a **separate task** requiring its own G0 intake and owner authorization. This task does NOT authorize enabling any mirror.

---
*Plan complete. Awaiting CTO final approval (G4) once the spec is written and reviewed (G3).*
