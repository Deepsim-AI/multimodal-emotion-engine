# G1 TASK PLAN — TASK_MEE_030: Enable One-Way Forgejo→GitHub Mirror

**Task ID:** TASK_MEE_030
**Gate:** G1 — CTO Plan (implementation of MEE_026_B spec)
**Date:** 2026-10-26 (PDT)
**Author:** CTO 🏗️ (qwen3.6:35b)
**Parent:** TASK_MEE_026_B (spec, CLOSED G5) + MEE_024 Decision 2 (one-way mirroring approved)
**Scope:** Implementation task. Deploys the mirror mechanism: config, credentials, webhook.
**Risk:** **FIRST production-impact task** in the mirror lineage — highest governance scrutiny.

---

## 1. Objective

Enable the one-way Forgejo→GitHub mirror specified in MEE_026_B: a Forgejo **push webhook** drives a
mirror runner that `git push --mirror`s to GitHub, gated by repo classification (public auto-mirror;
private/commercial allowlist-gated). MEE (public) auto-mirrors.

**This task authorizes only the mirror mechanism.** No signing changes, no repo permission changes
beyond the mirror, no publishing.

---

## 2. Acceptance Criteria

| # | AC | Verification |
|---|----|--------------|
| 1 | Forgejo push webhook configured (push event) | Forgejo webhook settings show active webhook |
| 2 | Mirror runner executes `git push --mirror` on authorized repos | Manual test of runner |
| 3 | MEE (public) auto-mirrors; private/commercial do NOT without allowlist | Test: push to MEE mirrors; simulate private repo → skipped |
| 4 | Bot token scope `repo` + `read:packages`, never admin | Forgejo secret/credential scope check |
| 5 | One-way enforced: GitHub mirror token lacks write to canonical | Verify token cannot push to Forgejo |
| 6 | Failure alerting + drift detection in place | Simulate failure → alert fires |
| 7 | Git history preserved (mirror is full `--mirror`, not shallow) | Verify `git log` on mirror matches Forgejo |

---

## 3. Implementation Plan (exact guidance)

### Task 1: Bot token creation (310a4b1)
- **Credential:** New dedicated mirror bot token, scope `repo` + `read:packages`, never admin.
- **Storage:** Forgejo → Settings → Secrets (encrypted at rest). **NOT** in the repo.
- **Note:** The existing org token (`/home/deepsim/Documents/shouke/workspace/bot_github_org_token.txt`)
  is a **reference only** — must NOT be repurposed. Create a new, separately scoped token.

### Task 2: Mirror runner (deploy) (320a6b1)
- **Location:** Mirror runner deploys on the VPS (forge.deepsim.ai) as a scheduled job or an
  event-triggered webhook handler.
- **Behavior:**
  ```bash
  # Reference implementation — not shipped in repo
  # On Forgejo push webhook:
  for repo in authorized_public_repos:
      git push --mirror git@github.com:Deepsim-AI/{repo}.git  # with bot token
      record_checksum(repo, ref)  # audit
  ```
- **Fail-closed:** on any scope violation, mirror skipped + alert. Never broaden token scope to "fix."
- **File:** runner script at a documented path on the VPS (e.g., `/opt/mirror/mirror_runner.sh`),
  **not** in the MEE repo (it's infrastructure, not MEE code).

### Task 3: Forgejo push webhook (deploy) (330a7b1)
- **Location:** Forgejo repo settings → Webhooks → MEE repo.
- **Config:** push event → mirror runner endpoint.
- **Payload:** `{ repo, ref, is_tag, repo_public }`.

### Task 4: MEE classified as public (340a8b1)
- **Action:** MEE (`Deepsim-AI/multimodal-emotion-engine`) tagged `public` in Forgejo settings → auto-mirror.
- **No private/commercial repo auto-mirrors** without explicit owner allowlist approval (per-repo).

### Task 5: Drift detection + alerting (350a9b1)
- **Action:** Post-mirror checksum comparison (Forgejo release assets vs GitHub mirror by tag).
- **Alerting:** mirror failures alert via chosen channel (email/webhook log/Slack).
- **Audit:** webhook logs + checksums retained ≥ 90 days.

### Task 6: Verification (360a10b1)
- **Manual test:** push a tag to Forgejo → verify GitHub mirror updates within SLA.
- **One-way check:** verify GitHub mirror token cannot push to Forgejo.
- **Isolation:** confirm no private/commercial repo auto-mirrored.

---

## 4. Risk Assessment

- **HIGH:** Accidental exposure of a private/commercial repo to GitHub via auto-mirror.
  Mitigation: fail-closed allowlist gating; public/private tag check; per-repo owner allowlist.
- **HIGH:** One-way direction violation (GitHub→Forgejo). Mitigation: GitHub mirror token lacks write
  to canonical; runner only pushes Forgejo→GitHub.
- **MEDIUM:** Runner down / network failure. Mitigation: retry policy, alerting, manual fallback.
- **MEDIUM:** Mirror drift. Mitigation: post-mirror checksum comparison + alert.

---

## 5. Rollback

- Disable the Forgejo webhook (revert to manual push).
- Delete the mirror bot token.
- Runner script can be removed from the VPS.
- MEE remains fully operable on Forgejo; GitHub mirror simply stops updating.

---

## 6. Reviewer Scrutiny (G3) — PROPORTIONATE TO RISK

Reviewer MUST verify:
1. **One-way enforced** — GitHub mirror token lacks write to Forgejo; no GitHub→Forgejo path.
2. **Fail-closed** — any scope violation skips mirror + alerts; never broadens token scope.
3. **Token scope minimal** — `repo` + `read:packages`, never admin/delete_repo.
4. **Private/commercial auto-mirror blocked** — no repo mirrors without explicit allowlist.
5. **Git history preserved** — full mirror, not shallow.
6. **Failure alerting + drift detection** operational.
7. **No scope creep** — no signing/permission/publishing changes outside the mirror.

---

## 7. Owner Decisions Needed (for this task / future)

1. **Trigger granularity:** full mirror (branches + tags) vs release-only (tags). MEE currently has
   both; full mirror keeps branches in sync.
2. **Allowlist policy:** how private/commercial repos are added to the allowlist (owner decision per
   repo). **This is the owner's call** — the mirror runner enforces it, but the owner defines it.
3. **Alerting channel:** where mirror failures alert (email, Slack, webhook log only).

---

*Plan complete. Awaiting CTO final approval (G4) + owner security sign-off before G2 deployment.*
