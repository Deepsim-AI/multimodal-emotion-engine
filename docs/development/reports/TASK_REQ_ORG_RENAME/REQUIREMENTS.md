# TASK_REQ — Forgejo Organization Setup

**Requester:** shouke.wei (gateway-owner)
**Date:** 2026-10-27
**Status:** PROPOSED
**Priority:** Medium

---

## Problem

Forgejo currently has **no organization** — all repos live under the `deepsim` user namespace (user ID 1, the first user created at instance setup). The goal is to create a `Deepsim` organization on Forgejo for clean project URLs (`Deepsim/multimodal-emotion-engine` instead of `deepsim/multimodal-emotion-engine`).

**Blocker:** Forgejo enforces a global unique namespace (users + orgs). The user `deepsim` (ID 1) exists, so creating an org named `Deepsim` fails with:
```
422: user already exists [name: Deepsim]
```

**GitHub is NOT affected** — `Deepsim-AI` org stays as-is.

## Current Forgejo State

| Item | Value |
|------|-------|
| Forgejo version | 17.0.0 (gitea-1.22.0) |
| Host | `forge.deepsim.ai:8443` |
| User `deepsim` | ID 1, admin=False, first user |
| Organizations | **None** |
| Repos | `deepsim/ci-test`, `deepsim/multimodal-emotion-engine`, `deepsim/runner-test` |

## Options

### Option A: Rename `deepsim` user → create `Deepsim` org → transfer repos

1. **Rename user** `deepsim` → `deepsim-admin` (or any available name)
   - Forgejo web UI: User Settings → Account → Username
   - Or API: `PATCH /user` with `{"username": "deepsim-admin"}`
   - ⚠️ This changes ALL existing repo URLs from `deepsim/*` to `deepsim-admin/*`
   - ⚠️ Git remotes pointing to `deepsim/*` will break until updated

2. **Create org** `Deepsim`
   - Forgejo web UI or API: `POST /orgs` with `{"username": "Deepsim"}`

3. **Transfer repos** from `deepsim-admin/*` → `Deepsim/*`
   - Forgejo supports repo transfer via web UI (Repo Settings → Transfer)
   - Or API: `POST /repos/{owner}/{repo}` with transfer params
   - GitHub-style redirects: Forgejo creates 301 redirects for transferred repos

4. **Update all references:**
   - [ ] Git remotes on all developer machines
   - [ ] Mirror allowlist: `/opt/mirror/allowlist.yaml` — `repo:` field
   - [ ] CI configs referencing `deepsim/multimodal-emotion-engine`
   - [ ] `RELEASED.md` and task docs

**Pros:** Clean end state: `Deepsim/<repo>`
**Cons:** Multi-step. Repo URL changes break existing clones/remotes. User rename is visible to all users.

### Option B: Create org with a non-conflicting name

Pick an org name that doesn't collide with the `deepsim` user:

| Candidate | Conflicts? | Notes |
|-----------|-----------|-------|
| `Deepsim-AI` | ❌ No | Matches GitHub org name. Consistent branding. |
| `DeepsimAI` | ❌ No | No hyphen. |
| `Deepsim-Labs` | ❌ No | Lab-style branding. |
| `Deepsim-Org` | ❌ No | Generic. |
| `Deepsim-AI-Org` | ❌ No | Explicit. |

Steps:
1. Create org (e.g., `Deepsim-AI`)
2. Transfer repos from `deepsim/*` → `Deepsim-AI/*`
3. Update references (same checklist as Option A)

**Pros:** No user rename needed. Simpler.
**Cons:** Name may not match desired branding. Still requires repo transfer.

### Option C: Keep current setup (`deepsim` user namespace)

Accept that repos live under `deepsim/<repo>`. The `deepsim` name is actually the brand name — `deepsim/multimodal-emotion-engine` reads naturally.

**Pros:** Zero effort. No URL changes. No redirects needed.
**Cons:** No org-level features (org settings, team management, org-level access control).

---

## Recommendation

**Option B with `Deepsim-AI`** — matches the GitHub org name, no conflicts, clean transfer.

If the goal is specifically the name `Deepsim` (without suffix), then **Option A** is required, accepting the repo URL change.

## What I Can Do (Implementation)

Once you pick an option, I can:
- Create the org via API
- Transfer repos via API (or guide through web UI)
- Update mirror allowlist, CI configs, docs
- Run a test mirror sync to verify
- Update all task evidence documents

**I cannot do:**
- Rename the `deepsim` user without your confirmation (it's user ID 1, the primary account)
- Make the decision for you (branding call)

## Open Questions

1. What org name do you want? (`Deepsim`? `Deepsim-AI`? other?)
2. If `Deepsim`: are you OK renaming the `deepsim` user to `deepsim-admin` (or another name)?
3. Should I proceed with repo transfer, or do you want to handle it manually?
