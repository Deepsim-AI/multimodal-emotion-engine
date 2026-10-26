# TASK_MEE_026_B — Forgejo→GitHub One-Way Mirror Mechanism Specification

**Task ID:** TASK_MEE_026_B
**Gate:** G2 — Specification authored (implementation of design)
**Date:** 2026-10-26 (PDT)
**Author:** CTO 🏗️ (qwen3.6:35b)
**Parent authorization:** TASK_MEE_024 Decision 2 ("APPROVED IN PRINCIPLE") + owner trigger-scope
clarification 2026-10-26.
**Scope:** **Specification deliverable only.** Zero code changes, zero config, zero production service
change, zero new credentials provisioned. This document specifies the mirror *mechanism*; enabling
it is a separate task requiring its own G0 intake and owner authorization.

---

## 1. Purpose

Establish a single, mechanism-first **one-way mirror** from Forgejo (canonical source of truth) to
GitHub (mirror-only). The mirror is **webhook-driven** and **tiered by repo class**:

| Repo class | Trigger | Control |
|------------|---------|---------|
| **Public / open-source** | Auto-mirror | Any push to Forgejo syncs to GitHub. No per-push approval. |
| **Private / commercial / internal** | Not mirrored by default | Owner allowlist approval **per repo** before mirroring. Backup is a valid reason but must be explicitly authorized. |

MEE (`Deepsim-AI/multimodal-emotion-engine`) is public → auto-mirrors. This is the only confirmed
public repo today. The spec is mechanism-first so it applies to whatever repo qualifies next.

---

## 2. Design — Component Responsibilities

Forgejo is canonical source of truth; GitHub is mirror-only. Mirror is a **single mechanism**, not
re-spun per repo. Each repo is tagged at Forgejo as `public` (auto-mirror) or `private` (allowlist).

| Component | Responsibility |
|-----------|---------------|
| **Forgejo** (forge.deepsim.ai:8443) | Canonical source of truth (code, branches, tags, releases, PyPI/OCI storage). Emits push webhook. |
| **GitHub** (github.com/Deepsim-AI/) | One-way mirror only. Never the signing authority or source of truth. |
| **Mirror webhook (Forgejo)** | On push events, triggers the mirror runner per the repo's public/private tag. |
| **Mirror runner** | `git push --mirror <github_mirror_url>` on authorized repos; skips allowlist-gated repos. |
| **Allowlist (Forgejo setting)** | List of private/commercial repo names permitted to mirror — owner-managed, never auto. |

---

## 3. Acceptance Criteria

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

## 4. Design Details

### 4.1 Webhook + Runner

Forgejo **push webhook** → mirror runner. The runner executes on a schedule or event trigger (not
Forgejo Actions, since Actions lacks native OIDC — though OIDC is irrelevant for a plain `git push`).

- **Forgejo webhook config:**
  - Event: `push` (tag + branch pushes, per tiered trigger).
  - Payload: `{ repo, ref, is_tag, repo_public }`.
  - Endpoint: mirror runner service (internal) or a thin webhook handler that invokes the runner.
- **Runner logic:**
  ```bash
  # Pseudocode — reference implementation, not shipped in this task
  for push in webhook.payload:
      if is_public(push.repo) and not allowlist_gated(push.repo):
          git push --mirror ${MIRROR_URL[push.repo]}   # repo + read:packages token
          record_checksum(push.repo, push.ref)          # audit
      else:
          log_skip(push.repo, push.ref, reason="allowlist-gated")
  ```
- **Tag-only vs branch:** For mirrors, mirror the full repo (`--mirror`) so branches/tags stay in
  sync. If GitHub mirror should be release-only (tags), scope the webhook to `is_tag` pushes and
  push only `refs/tags/v*.*.*`.
- **Conflict resolution:** Not applicable — one-way mirror never writes to Forgejo. If a GitHub push
  occurs, it is rejected by permission (mirror token lacks push to canonical).

### 4.2 Token

Dedicated mirror bot token, stored in Forgejo secrets (not in the repo):

| Property | Value |
|----------|-------|
| Scope | `repo` + `read:packages` only |
| Never | `admin`, `delete_repo`, write to canonical repo |
| Rotation | 12-month cycle, documented in credentials section |
| Storage | Forgejo → Settings → Secrets (encrypted at rest) |
| Reference | Existing org token (`/home/deepsim/Documents/shouke/workspace/bot_github_org_token.txt`) as scope guidance — **production token must be a new, separately scoped credential** |

The current org token is a reference for *scope*; it must not be repurposed. A dedicated mirror
credential is required per MEE_024 Decision 2.

### 4.3 Sync Verification + Audit

- **Post-mirror checksum comparison:** after `git push --mirror`, compare Forgejo release assets vs
  GitHub mirror assets (by tag) to detect drift.
  ```bash
  # Reference verification — not shipped in this task
  forge_assets=$(forge api /repos/{owner}/{repo}/releases | jq -r '.[].assets[].name')
  github_assets=$(gh release view {tag} --repo {mirror} -q '.assets[].name')
  diff <(echo "$forge_assets") <(echo "$github_assets")   # empty = in sync
  ```
- **Audit trail:** webhook logs (push events, mirror decisions, skip reasons) + sync verification
  checksums. Retain ≥ 90 days. Failures logged with repo, ref, timestamp, error.
- **Drift detection:** if a mirror is out of sync, alert (see 4.4) and offer manual re-sync.

### 4.4 Failure Handling

| Failure | Handling |
|---------|----------|
| Mirror runner down | Retry policy: 3 attempts, exponential backoff (5s, 25s). Alert after 3rd failure. |
| Network/403 | Alert to owner; manual fallback (`git push --mirror` from trusted host). |
| GitHub release asset drift | Alert; manual re-sync from Forgejo. |
| Allowlist token scope wrong | Fail closed — mirror skipped, alert to owner. Never broaden scope to "fix." |
| Forgejo webhook endpoint unreachable | Webhook delivery retries per Forgejo default (10 attempts); alert if exhausted. |

**Manual fallback** (documented, not automated):
```bash
# Trusted host only — reference, not shipped in this task
git push --mirror git@github.com:Deepsim-AI/multimodal-emotion-engine.git
```

---

## 5. Deliverable

This specification document. No code, no config, no production change.

## 6. Implementation (Separate Task — NOT authorized here)

Enabling the mirror requires a **separate task** with its own G0 intake and owner authorization. That
task must:
1. Create a dedicated mirror bot token (scope `repo` + `read:packages`).
2. Configure the Forgejo push webhook.
3. Deploy the mirror runner (scheduled or event-triggered).
4. Tag MEE as `public` (auto-mirror) in Forgejo settings.
5. Document the allowlist mechanism for private/commercial repos.
6. Run a mirror verification + audit (Section 4.3).

This task does NOT authorize enabling any mirror.

---

## 7. Reviewer Scrutiny (G3)

Reviewer MUST verify:
1. Direction is one-way (Forgejo → GitHub); no GitHub→Forgejo path exists.
2. Tiered trigger is correct (public auto, private allowlist-gated).
3. Token scope is minimal (`repo` + `read:packages`, never admin).
4. Fail-closed on allowlist scope issues.
5. MEE is public → auto-mirrors; no private repo auto-mirrors.

---

*End of specification. G2 deliverable complete. Awaiting G3 review + G4 CTO approval.*
