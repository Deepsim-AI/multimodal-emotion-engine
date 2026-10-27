# OWNER_DECISIONS — TASK_MEE_030

**Date:** 2026-10-27
**Owner:** deepsim (gateway-owner)
**Status:** APPLIED

---

## Decision 1: Mirroring Trigger — Branches + Tags

**Owner decision:** Approved for branches and tags.

**Rationale:** `git push --mirror` is explicitly discouraged (dangerous due to ref deletion risks). Explicit ref synchronization is preferred.

**Implication:**
- The mirror sync will push branches and tags from Forgejo → GitHub
- A destructive-change detector must be implemented: if a remote ref deletion or force-push would alter the mirror, the sync must fail closed (block + alert)
- `--mirror` is NOT to be used; explicit `git push origin <ref>` per branch/tag is required

---

## Decision 2: Allowlist Policy — Default Deny

**Owner decision:** Default deny. An explicit allowlist is required outside repository code. No mirroring without explicit approval.

**Required allowlist entry fields:**
| Field | Description |
|-------|-------------|
| `repo` | Canonical repository identifier (owner/name) |
| `destination` | GitHub mirror URL |
| `visibility` | private (default) or public (requires explicit justification) |
| `license` | License compatibility check result |
| `approved_by` | Approving authority (name + role) |
| `approved_on` | ISO 8601 date |
| `review_due` | ISO 8601 date for next review |

**Implication:**
- The mirror config file lives outside the repository (e.g., `~/ds_eo/mirror_allowlist.yaml` or a dedicated config location)
- The sync script MUST refuse to run if the repo is not in the allowlist
- This is a fail-closed gate: no allowlist entry → no mirroring, period

---

## Decision 3: Alerting — Fail-Closed, Immediate

**Owner decision:** Fail-closed. Immediate alert on failure.

**Implication:**
- Any mirror sync failure (push rejection, network error, destructive change detection) must:
  1. Block the sync (do not partially apply)
  2. Alert the operator immediately (webhook/log/heartbeat)
- No silent failures. No retry-then-forget.

---

## Decision 4: Release Coordination — Do Not Overwrite Existing v0.4.5

**Owner decision:**
- Do not overwrite existing `v0.4.5` GitHub assets (if any exist from prior pushes)
- Test plan must be submitted for review before execution
- MEE_029 CI verification must complete before mirroring begins

**Implication:**
- MEE_029 CI pipeline must show green status (build → sign → verify → release) before MEE_030 G2
- The mirror sync must be read-only with respect to existing GitHub release assets
- A dry-run mode is required before the first real sync

---

## Decision 5: Independence — Separate Gates and Evidence

**Owner decision:** MEE_029 and MEE_030 are independent workstreams. Gates and evidence remain separate.

**Implication:**
- MEE_030 cannot reference MEE_029 evidence as its own
- MEE_030 must produce its own G2_COMPLETION_EVIDENCE.md
- MEE_029 completion is a prerequisite (sequencing) but NOT evidence substitution

---

## Applied To

- G1_PLAN/CTO_TASK_PLAN.md — scope updated per decisions
- G2 test plan to be drafted reflecting allowlist + fail-closed requirements
- RELEASED.md — mirror URL pending (GitHub not yet configured)
