# OWNER DECISIONS — TASK_MEE_030

**Date:** 2026-10-26 (PDT)
**Decided by:** gateway-owner
**Status:** Final decisions recorded. Deployment remains gated on G2/G4 reviews.

---

## 1. Trigger Granularity — BRANCHES + TAGS (approved in principle)

Mirror approved branches **and** tags from Forgejo to GitHub. Forgejo remains the sole
canonical source of truth.

**Constraints (owner-mandated):**

- Do **not** assume `git push --mirror` is safe by default. It can propagate ref
  deletions and force updates beyond a simple branch/tag update.
- Before deployment, **document**: exact ref policy, destination behavior, dry-run
  results, and protections against unexpected deletions or force updates.
- **Prefer explicitly scoped ref synchronization** over `--mirror`.
- If `--mirror` is retained, **demonstrate** how destructive changes are detected and
  safely blocked or escalated.
- GitHub Releases, release metadata, and downloadable assets must be treated
  **separately**. Git object mirroring does not by itself establish that these items
  are synchronized or verified.

## 2. Allowlist — DEFAULT DENY

Maintain an explicit allowlist **outside repository code**. No repository is eligible
for mirroring unless explicitly approved.

Each entry must identify:

| Field | Example (MEE) |
|-------|---------------|
| Canonical Forgejo repo | `deepsim/multimodal-emotion-engine` |
| GitHub destination | `Deepsim-AI/multimodal-emotion-engine` |
| Visibility | public |
| License / publication eligibility | (per repo) |
| Approving authority | gateway-owner |
| Approval date | 2026-10-26 |

**Rules:**

- Private, commercial, and internal repositories must **never** be mirrored automatically.
- **Fail closed** on missing or invalid allowlist entries, unexpected visibility
  changes, or inconsistent source/destination configuration.
- MEE is an initial allowlist candidate (intended to be public). Verify its current
  visibility and destination before enabling.

## 3. Alerting — EXISTING MONITORED CHANNEL

Identify the actual configured and monitored Deepsim operations channel **before**
deployment. Prefer an established operational email or incident-notification mechanism
with persistent logs.

Alert on:

- Mirror failures
- Drift
- Unexpected destination changes
- Authentication failures
- Allowlist failures
- Attempted destructive ref changes

If no suitable channel exists, submit a concrete proposal for approval. Do **not**
assume that a notification destination is configured.

## 4. Deployment Gated

These decisions do **not** authorize immediate production deployment. Required before
G2 deployment:

- Complete G2/G4 reviews
- Verify runner's least-privilege permissions
- Verify secret handling
- Verify webhook authentication
- Verify replay protection
- Verify concurrency controls
- Verify logging
- Verify retry behavior
- Verify rollback procedure

The runner must be:

- **Idempotent**
- Must **not** accept arbitrary repository names or destination URLs from an untrusted
  webhook payload
- Resolve repository identity against the **trusted allowlist**

## 5. MEE_029 — INVESTIGATE BEFORE TRIGGERING

Do **not** trigger the full `release-sigstore` workflow with a test tag yet.

First establish exactly what the workflow will do:

- Tag creation
- Release creation
- Asset upload
- Signing
- Verification
- Any production-side effects

Verify that the test can be isolated and **cannot** overwrite or confuse an official
release. If the current workflow cannot safely run as a non-production test, use a
dedicated test repository or a separate test workflow.

Do **not** move or reuse existing release tags or overwrite v0.4.5 assets.

Submit the proposed test plan and its expected side effects for review before execution.

## 6. Coordination

MEE_029 and MEE_030 are **independent workstreams**. Continue planning in parallel, but
keep their gates and acceptance evidence separate.

Record these decisions in the task files. Do **not** interpret approval of the design
direction as authorization to deploy the mirror runner or execute a release workflow.

---

*End of owner decisions.*
