# G0_INTAKE_CHECKLIST — TASK_MEE_022: MEE Hub Distribution — Publish to Forgejo Registry

**Task ID (proposed, pending registry confirmation):** TASK_MEE_022
**Gate:** G0 — PM Intake (mechanical sign-off checklist)
**Date:** 2026-10-25
**Prepared by:** PM 📋 (ornith-1.5:35b), at gateway-owner explicit authorization
**Companion to:** `TASK_REQ_MEE_HUB_PUBLISH.md` (task request that drives this intake)

> **Purpose:** make the PM's G0 sign-off a mechanical, checkable step so the handoff to
> CTO (G1) is unambiguous. Each item below is either **verified now** (read-only) or
> **for the PM to confirm/sign**. Nothing here implements code or crosses a gate.
>
> This task's upstream is the Hub portal deployment (verified live at §7.5) — a **process
> establishment** (TASK_MEE_022 / `TASK_REQ_MEE_DSEO_PROCESS.md`) is a *parallel, separate*
> meta-request. This intake covers only the Hub **publish** work.

---

## 1. Task-ID & Registry Check

| # | Check | Result |
|---|-------|--------|
| 1.1 | Registry file located | `docs/development/reports/TASK_MEE_001/TASK_REGISTRY.md` ✅ |
| 1.2 | Registry table is current | ✅ Table lists MEE_020 as CLOSED (v0.4.0); IDs 021–034 marked unused |
| 1.3 | Filesystem ground truth (tasks in use) | `TASK_MEE_001`–`020`, `021_KEYGATE_ENCRYPTION_KEY`, `021_SIGSTORE_FIRST_RUN`, `022`, `023`, `035` ✅ |
| 1.4 | A standalone `TASK_MEE_021/` task dir exists? | ❌ **Absent** — `TASK_MEE_021_KEYGATE_ENCRYPTION_KEY/` and `TASK_MEE_021_SIGSTORE_FIRST_RUN/` are *sub-tasks / worknotes*, not a G0–G5 task; no plain `TASK_MEE_021/` exists ✅ |
| 1.5 | Repo-wide reference to `TASK_MEE_022` as an in-flight task | None (only the two 021 sub-folders + registry "unused" note) ✅ |
| 1.6 | **Proposed next ID** | **`TASK_MEE_022`** — available by convention (the two 021 folders are closure notes for prior tasks, not a fresh task) ✅ |
| 1.7 | PM refreshes registry table (add `TASK_MEE_022` row → `DRAFTED, awaiting CTO G1`) | ☐ **PM action** |
| 1.8 | Confirm ID not reused by another active task | ☐ **PM action — confirm with owner before G1** |

> **Note:** `TASK_MEE_022` is the next ID by convention. The two `TASK_MEE_021_*` folders already
> on disk are **not** a competing task — one closes the MEE_020 key-gate open item, the other is a
> Sigstore first-run worknote. Flag to owner at sign-off; if owner wants the Hub publish under a
> different ID (e.g., `TASK_MEE_025`), re-propose here before G1.

---

## 2. Intake Artifacts Present

| # | Artifact | Status |
|---|----------|--------|
| 2.1 | `TASK_REQ_MEE_HUB_PUBLISH.md` (task request) | ✅ written (deliverables, 12 acceptance tests, constraints, stop conditions) |
| 2.2 | `G0_INTAKE_CHECKLIST.md` (this file) | ✅ written (this phase) |
| 2.3 | `LOCK.md` | ☐ **PM action** (see §3) |
| 2.4 | `READY_FOR_CTO.md` (optional; MEE_019 skipped it — G1 proceeded from `CTO_PLAN.md`) | ☐ PM optional |
| 2.5 | All docs reviewed by PM/owner for correctness & completeness | ☐ **PM action** |

---

## 3. LOCK State

| # | Check | Result / action |
|---|-------|-----------------|
| 3.1 | Any active LOCK on MEE tasks right now? | None active (MEE_020 LOCK RELEASED; G0s release before G1 handoff) ✅ |
| 3.2 | No conflicting in-flight task blocks this publish | ✅ (020 fully closed; key-gate encryption verified live-resolved at §7.6) |
| 3.3 | PM writes `LOCK.md` for this intake (status `RELEASED`, scope = G0 intake, artifacts list) | ☐ **PM action** (follow MEE_020 `LOCK.md` convention) |

> **Convention (from MEE_020):** LOCK is created at intake and **released before handoff to CTO**
> for G1. It scopes the intake phase only.

---

## 4. Baseline / No-Code-Change Proof (G0 must not modify code)

| # | Check | Result |
|---|-------|--------|
| 4.1 | Git working tree (at G0 drafting) | Only `?? docs/development/reports/TASK_MEE_022/`, `?? docs/development/reports/TASK_MEE_023/`, `?? docs/release-pipeline-analysis.md` untracked ✅ |
| 4.2 | No changes under `mee/`, `tests/`, `pyproject.toml`, `README.md`, `LICENSE.txt`, `.github/workflows/` | ✅ verified (`git status --short` clean for these at §1.4) |
| 4.3 | MEE source contract untouched (v0.4.4 baseline) | ✅ `git rev-parse HEAD` = `15dc500` (unmodified) |
| 4.4 | Current package version (baseline) | `0.4.4` (pyproject.toml) ✅ |
| 4.5 | HEAD baseline commit | `15dc500` (install-from-release docs, v0.4.4) ✅ |
| 4.6 | No production deployment / registry state changed (G0 = assessment only) | ✅ G0 reads registry state read-only (see §7) |

> This is the **auditable proof** that G0 did not cross into implementation or registry writes.

---

## 5. Constraints Captured (verify they're in `TASK_REQ_MEE_HUB_PUBLISH.md`)

| # | Constraint | Present? |
|---|-----------|----------|
| 5.1 | Do NOT modify GitHub Actions or Sigstore workflows | ✅ C1 |
| 5.2 | Do NOT change canonical release-signing process (GitHub Actions = origin) | ✅ C2 |
| 5.3 | Do NOT delete existing test packages from the registry | ✅ C3 |
| 5.4 | Do NOT publish unsigned artifacts — every artifact must have Sigstore signature | ✅ C4 |
| 5.5 | Do NOT fabricate checksums or verification results | ✅ C5 |
| 5.6 | Preserve GitHub Releases path as canonical signed-artifact origin | ✅ C6 |
| 5.7 | Do NOT expose MEE model weights in the registry (separate CDN) | ✅ C7 |
| 5.8 | Stop + report on build / Sigstore / Docker failure or any AC failure | ✅ "Stop conditions" ✅ |

---

## 6. CTO (G1) Decision Points — carried forward (do NOT decide at G0)

| # | Decision | Status at G0 |
|---|----------|--------------|
| 6.1 | How to produce v0.4.4 artifacts: local build vs GitHub Actions reuse (wheel + sdist) | ☐ CTO decides (G1) |
| 6.2 | OCI image: create Dockerfile (new deliverable); multi-arch Jetson ARM64 + x86_64? | ☐ CTO decides (G1) |
| 6.3 | "Generic" channel content: wheel+sdist tarball / platform binaries / SDK bundle | ☐ CTO decides (G1) |
| 6.4 | Sigstore reuse path: GitHub Actions-signed artifacts shipped to Forgejo vs self-sign on host | ☐ CTO decides (G1) |
| 6.5 | Extras strategy: publish all extras (`vision`, `voice`, `demo`) or base only | ☐ CTO confirms (G1) |
| 6.6 | Confirm model weights stay OUT of the registry (C7) | ☐ CTO confirms (G1) |

> G0 **proposes and assesses**; G1 **decides**. None of these is decided in this document.

---

## 7. Dependencies & Handoff (G0-read verified, not changed)

| # | Item | Status |
|------|------|--------|
| 7.1 | TASK_MEE_020 (License Hardening & Signed Distribution) | ✅ CLOSED (v0.4.0) |
| 7.2 | Hub portal deployed & live | ✅ `hub.deepsim.ai:8443` — 200 OK; currently marks MEE "Coming Soon" |
| 7.3 | MEE v0.4.4 source in local repo | ✅ `/home/deepsim/multimodal-emotion-engine/` (clean, `15dc500`) |
| 7.4 | MEE v0.4.4 signed wheel on GitHub (Sigstore) | ✅ present (private repo) |
| 7.5 | Release pipeline / Sigstore workflow | ✅ `.github/workflows/release.yml` + `release-sigstore.yml` + `tools/verify_release.sh` |
| 7.6 | `RELEASE_KEY_ENCRYPTION_KEY` key-gate hardening | ✅ **Verified live (2026-10-25):** key SET in `/opt/keygate/.env`, keygate `healthy`, `license key encryption: enabled`, backfill `encrypted: 2` — resolved, not a blocker |
| 7.7 | Hub PyPI / OCI / Generic registry endpoints | ⚠️ Forgejo reachable (200); MEE artifacts **not yet published** (generic 404) — to be written at G2/G4 |
| 7.8 | **Baseline for registry** | ⚠️ No MEE releases exist yet in the Hub registry — G2 publish is the "before" state, nothing to roll back |
| 7.9 | **Handoff to CTO (G1)** | ☐ **PM action — after §2.1–2.2 + §3.3 + §5.x signed** |

> **Important G0 note:** the local wheel is v0.4.0 only (unsigned). v0.4.4 build is a G2 deliverable —
> G0 does not build it. Do not let the stale local wheel look like the release artifact.

---

## 8. PM/Owner Sign-off

| # | Item | Signature / Date |
|------|------|------------------|
| 8.1 | Reviewed `TASK_REQ_MEE_HUB_PUBLISH.md` | ☐ Shouke Wei (gateway-owner / PM)  ☐ 2026-10-25 |
| 8.2 | Confirmed task ID `TASK_MEE_022` and registry reuse caveat (§1.6–1.8) | ☐ Shouke Wei (gateway-owner / PM)  ☐ 2026-10-25 |
| 8.3 | Confirmed **no code changed** (§4) and G0 baseline = `15dc500` | ☐ Shouke Wei (gateway-owner / PM)  ☐ 2026-10-25 |
| 8.4 | Confirmed key-gate hardening resolved live (§7.6) — not a blocker | ☐ Shouke Wei (gateway-owner / PM)  ☐ 2026-10-25 |
| 8.5 | Wrote + released `LOCK.md` (§3.3) | ☐ Shouke Wei (gateway-owner / PM)  ☐ 2026-10-25 |
| 8.6 | G0 → G1 handoff authorized (all ☐ items signed) | ☐ Shouke Wei (gateway-owner / PM)  ☐ 2026-10-25 |

---

## 9. Non-Goals Restated (so they are never silently absorbed)

- ❌ Modifying GitHub Actions / Sigstore release workflows (C1)
- ❌ Changing the canonical release-signing process (C2)
- ❌ Deleting existing Hub registry test packages (C3)
- ❌ Publishing unsigned artifacts (C4)
- ❌ Fabricating checksums / verification results (C5)
- ❌ Exposing MEE model weights in the registry (C7)
- ❌ Resolving the `RELEASE_KEY_ENCRYPTION_KEY` key-gate item here (already verified resolved — do not re-open)
- ❌ Establishing the DS-EO process (that is the separate TASK_MEE_022 meta-request)

---

*This checklist is a G0 process artifact only. It implements nothing, writes no registry state,
and does not bypass the G0/G1/G2 gates. Handoff to CTO (G1) occurs only after §8 sign-off.*
