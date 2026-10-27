# TASK_REQ — Rename Deepsim-AI Org to Deepsim

**Requester:** shouke.wei (gateway-owner)
**Date:** 2026-10-27
**Status:** PROPOSED
**Priority:** Medium (blocking for clean GitHub org URL)

---

## Problem

The current GitHub organization is named `Deepsim-AI`. The desired name is `Deepsim` (without the `-AI` suffix). However, the username `deepsim` is already taken by an old personal account (created 2016-08-10, 2 repos, no followers).

## Current State

| Account | Type | Created | Repos | Status |
|---------|------|---------|-------|--------|
| `Deepsim-AI` | Organization | 2024-07-08 | 3 (DS-EO, .github, multimodal-emotion-engine) | **Active** |
| `deepsim` | User | 2016-08-10 | 2 (repoTest3, skills-introduction-to-github) | **Dormant** (no followers, no activity) |
| `deepsim-ai-bot` | User (bot) | 2026-xx | 0 | **Active** (mirror sync, CI) |

## Options

### Option A: Rename the `deepsim` user, then rename the org

1. **Rename user `deepsim` → `deepsim-old`** (or any available name)
   - Go to https://github.com/deepsim/settings
   - Change username to `deepsim-old` (or `deepsim-2016`, etc.)
   - This frees the `deepsim` name
   - ⚠️ This requires access to the `deepsim` account credentials

2. **Create org `Deepsim`**
   - Go to https://github.com/orgs/plan
   - Create new org named `Deepsim`

3. **Migrate repos from `Deepsim-AI` → `Deepsim`**
   - Transfer `DS-EO`, `.github`, `multimodal-emotion-engine`
   - GitHub handles redirects automatically (old URLs continue to work)
   - Update CI configs, mirror allowlist, and any hardcoded URLs

4. **Delete or archive `Deepsim-AI`**

**Pros:** Clean, end state is `Deepsim/<repo>`
**Cons:** Requires access to the old `deepsim` account. Multi-step. Downtime risk during migration.

### Option B: Keep `Deepsim-AI`, rename to `Deepsim` in-place

GitHub **does allow renaming an organization** (one-time, free):
1. Go to https://github.com/organizations/Deepsim-AI/settings
2. Change the organization name from `Deepsim-AI` to `Deepsim`
3. GitHub creates automatic redirects from `Deepsim-AI` → `Deepsim`

**BUT:** This will fail if the `deepsim` username is still taken. GitHub enforces a global unique namespace for users + orgs.

**If the `deepsim` user is abandoned:**
1. Contact GitHub Support (https://github.com/contact) and request they release the `deepsim` username (it appears dormant since 2016)
2. OR: If you have access to the `deepsim` account, rename it first, then rename the org

**Pros:** Single-step rename. GitHub handles redirects automatically.
**Cons:** Depends on freeing the `deepsim` name.

### Option C: Keep `Deepsim-AI` as-is

Accept the current name. The `-AI` suffix is actually descriptive and not misleading.

**Pros:** Zero effort. No migration risk.
**Cons:** URL is `Deepsim-AI/<repo>` instead of `Deepsim/<repo>`.

### Option D: Create a new org `Deepsim-LLM` or another available name

Pick a different name that's available. E.g., `Deepsim-LLM`, `DeepsimAI`, `Deepsim-Labs`.

**Pros:** No migration of the old `deepsim` user needed.
**Cons:** Another migration. Name may not match desired branding.

---

## Recommendation

**Option B** (rename in-place) is the cleanest path, **if** you can free the `deepsim` username.

### Steps (if choosing Option B):

1. **Free the `deepsim` username:**
   - If you have the password: log in → Settings → Account → Change username → `deepsim-old`
   - If you don't have access: email GitHub Support at https://github.com/contact
     - Subject: "Request to release dormant username: deepsim"
     - Explain: Account created 2016, no activity, no followers, blocking org rename

2. **Rename the org:**
   - Go to https://github.com/organizations/Deepsim-AI/settings
   - Organization name → `Deepsim`
   - Confirm (irreversible, but redirects are permanent)

3. **Update infrastructure (automated, ~15 min):**
   - [ ] Update mirror allowlist: `/opt/mirror/allowlist.yaml` — destination URL
   - [ ] Update CI workflow: `release-sigstore.yml` — any hardcoded org references
   - [ ] Update `RELEASED.md` — GitHub mirror URL
   - [ ] Update `G2_COMPLETION_EVIDENCE.md` (MEE_029 + MEE_030) — repo URLs
   - [ ] Update Forgejo webhook (if configured)
   - [ ] Update any other config files referencing `Deepsim-AI`

4. **Verify:**
   - [ ] `git clone https://github.com/Deepsim/multimodal-emotion-engine.git` works
   - [ ] `git clone https://github.com/Deepsim-AI/multimodal-emotion-engine.git` still works (redirect)
   - [ ] CI pipeline runs green
   - [ ] Mirror sync works

---

## What I Can Do (Implementation)

Once you decide on an option and free the username (if needed), I can:
- Update all config files (allowlist, CI workflows, docs)
- Update the mirror sync script
- Run a test sync to verify
- Update all task evidence documents
- Commit and push to both Forgejo and GitHub

**I cannot do:**
- Rename the `deepsim` user (requires their credentials)
- Rename the org (requires org owner access in GitHub settings — the bot token may not have this permission)
- Contact GitHub Support (requires your email)

---

## Open Questions

1. Do you have access to the `deepsim` GitHub account (password / 2FA)?
2. Is the `deepsim` account yours or someone else's?
3. Do you want to proceed with Option B (rename), or prefer Option C (keep `Deepsim-AI`)?
4. If renaming: any preference for the old user's new name (`deepsim-old`? `deepsim-2016`? something else)?
