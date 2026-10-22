# G0_INTAKE_CHECKLIST — TASK_MEE_020: MEE License Hardening & Signed Distribution

**Task ID (proposed, pending registry confirmation):** TASK_MEE_020
**Gate:** G0 — PM Intake (mechanical sign-off checklist)
**Date:** 2026-10-22
**Prepared by:** Implementer (G2), at owner request — for PM/owner review + signature
**Companion to:** `TASK_REQUEST.md`, `THREAT_MODEL.md`

> **Purpose:** make the PM's G0 sign-off a mechanical, checkable step so the handoff to
> CTO (G1) is unambiguous. Each item below is either **verified now** (read-only) or
> **for the PM to confirm/sign**. Nothing here implements code or crosses a gate.

---

## 1. Task-ID & Registry Check

| # | Check | Result |
|---|-------|--------|
| 1.1 | Registry file located | `docs/development/reports/TASK_MEE_001/TASK_REGISTRY.md` ✅ |
| 1.2 | Registry table is current | ⚠️ **STALE — table ends at 011**; 012–035 not reflected |
| 1.3 | Filesystem ground truth (tasks in use) | 016 (CUDA), 017 (Camera), 018 (RemoteDemo), 019 (License UI), 035 (Pangolin) ✅ |
| 1.4 | Any `02x` task ID exists? | **No** — `find`/`ls` confirm zero `TASK_MEE_02*` dirs ✅ |
| 1.5 | Repo-wide reference to `TASK_MEE_020` | None pre-existing ✅ |
| 1.6 | **Proposed next ID** | **`TASK_MEE_020`** (lowest unused in sequence) ✅ |
| 1.7 | PM refreshes registry table (add 012–035 rows + new 020 row → `DRAFTED, awaiting CTO G1`) | ☐ **PM action** |
| 1.8 | PM creates `TASK_REGISTRY.md` row for 020 (title, phase, deps, status) | ☐ **PM action** |

> **Note:** 020 is available **by absence**, not by the stale table. Do not rely on the table
> alone — the filesystem (1.3–1.5) is the source of truth used here.

---

## 2. Intake Artifacts Present

| # | Artifact | Status |
|---|----------|--------|
| 2.1 | `TASK_REQUEST.md` (problem, scope, non-goals, 8 constraints, 8 ACs, options, 6 CTO decisions) | ✅ written |
| 2.2 | `THREAT_MODEL.md` (adversaries, assets, boundaries, T1–T12, will/won't, cost matrix, fail-safe, tests, sign-off) | ✅ written |
| 2.3 | `G0_INTAKE_CHECKLIST.md` (this file) | ✅ written |
| 2.4 | `LOCK.md` | ☐ **PM action** (see §3) |
| 2.5 | `READY_FOR_CTO.md` (optional; MEE_019 skipped it — G1 proceeded from `CTO_PLAN.md`) | ☐ PM optional |
| 2.6 | All three docs reviewed by PM/owner for correctness & completeness | ☐ **PM action** |

---

## 3. LOCK State

| # | Check | Result / action |
|---|-------|-----------------|
| 3.1 | Any active LOCK on MEE tasks right now? | None active (MEE_015 LOCK RELEASED; MEE_019 LOCK empty/absent after closure) ✅ |
| 3.2 | No conflicting in-flight task blocks 020 | ✅ (019 fully closed, G0–G5) |
| 3.3 | PM writes `LOCK.md` for 020 (status `RELEASED`, scope = G0 intake, artifacts list) | ☐ **PM action** (follow MEE_015 `LOCK.md` convention) |

> **Convention (from MEE_015):** LOCK is created at intake and **released before handoff to CTO**
> for G1. It scopes the intake phase only.

---

## 4. Baseline / No-Code-Change Proof (G0 must not modify code)

| # | Check | Result |
|---|-------|--------|
| 4.1 | Git working tree (at G0 drafting) | Only `?? docs/development/reports/TASK_MEE_020/` untracked ✅ |
| 4.2 | No changes under `mee/`, `tests/`, `pyproject.toml`, `README.md`, `LICENSE.txt` | ✅ verified (`git status` empty for these) |
| 4.3 | `mee/licensing/` contract untouched (C1) | ✅ 0-line diff |
| 4.4 | Current package version (baseline for the "unchanged" AC) | `0.3.0` (pyproject) |
| 4.5 | HEAD baseline commit | `f077ea3` (MEE_019 G5 closure) |
| 4.6 | No production deployment touched (C5) | ✅ G0 = design/assessment only |

> This is the **auditable proof** that G0 did not cross into implementation.

---

## 5. Constraints Captured (verify they're in `TASK_REQUEST.md`)

| # | Constraint | Present? |
|---|-----------|----------|
| 5.1 | C1 — preserve licensing contract / public API | ✅ |
| 5.2 | C2 — fail safe, never allow inference on enforcement failure | ✅ |
| 5.3 | C3 — do not promise complete anti-tamper | ✅ |
| 5.4 | C4 — no aggressive obfuscation / TPM / hardware binding by default | ✅ |
| 5.5 | C5 — no production changes during G0 | ✅ |
| 5.6 | C6 — `RELEASE_KEY_ENCRYPTION_KEY` stays a **separate** task | ✅ |
| 5.7 | C7 — no hidden telemetry / data collection | ✅ |
| 5.8 | C8 — preserve reasonable offline operation (Jetson/field) | ✅ |
| 5.9 | C9 — integrity anchor not beside-code-only | ✅ |

---

## 6. CTO (G1) Decision Points — carried forward (do NOT decide at G0)

| # | Decision | Status at G0 |
|---|----------|--------------|
| 6.1 | Compiled enforcement (Cython gate+shim) warranted? | ☐ CTO decides (G1) |
| 6.2 | Signing scheme (Sigstore vs GPG/age) | ☐ CTO decides (G1) |
| 6.3 | Integrity anchoring (manifest vs wheel-metadata vs Keygate-anchored) | ☐ CTO decides (G1) |
| 6.4 | Fail-safe enforcement point + block-on-error behavior | ☐ CTO confirms (G1) |
| 6.5 | Offline grace window (`exp`) adequacy + documentation | ☐ CTO confirms (G1) |
| 6.6 | Confirm `RELEASE_KEY_ENCRYPTION_KEY` remains separate (C6) | ☐ CTO confirms (G1) |

> G0 **proposes and assesses**; G1 **decides**. None of these is decided in this document.

---

## 7. Dependencies & Handoff

| # | Item | Status |
|---|------|--------|
| 7.1 | TASK_MEE_015 (License Integration) | ✅ CLOSED |
| 7.2 | TASK_MEE_019 (License UI) | ✅ CLOSED (v0.3.0) |
| 7.3 | Packaging baseline (`pyproject.toml` v0.3.0) | ✅ present |
| 7.4 | Release pipeline / CI | ✅ present (to be extended in G2 if G1 approves) |
| 7.5 | Keygate server (activate/verify/deactivate) | ✅ live |
| 7.6 | `RELEASE_KEY_ENCRYPTION_KEY` server-side | ⚠️ **OUT OF SCOPE — separate task (C6)** |
| 7.7 | **Handoff to CTO (G1)** | ☐ **PM action — after 2.1–2.3 + 3.3 + 5.x signed** |

---

## 8. PM/Owner Sign-off

| # | Item | Signature / Date |
|---|------|------------------|
| 8.1 | Reviewed `TASK_REQUEST.md` | ✅ Shouke Wei (gateway-owner / PM)  2026-10-22 |
| 8.2 | Reviewed `THREAT_MODEL.md` (incl. §12 residual-risk acceptance) | ✅ Shouke Wei (gateway-owner / PM)  2026-10-22 |
| 8.3 | Confirmed task ID `TASK_MEE_020` and refreshed registry (1.7–1.8) | ✅ Shouke Wei (gateway-owner / PM)  2026-10-22 |
| 8.4 | Wrote + released `LOCK.md` (3.3) | ✅ Shouke Wei (gateway-owner / PM)  2026-10-22 |
| 8.5 | Confirmed **no code changed** (4.1–4.6) and G0 → G1 handoff authorized | ✅ Shouke Wei (gateway-owner / PM)  2026-10-22 |

---

## 9. Non-Goals Restated (so they are never silently absorbed)

- ❌ Complete / "unbreakable" anti-tamper (C3)
- ❌ TPM / Secure-Enclave / hardware binding (C4)
- ❌ Aggressive obfuscation by default (C4)
- ❌ Production changes during G0 (C5)
- ❌ Resolving `RELEASE_KEY_ENCRYPTION_KEY` (C6)
- ❌ Hidden telemetry (C7)
- ❌ Beside-code-only integrity digest (C9)

---

*This checklist is a G0 process artifact only. It implements nothing and does not bypass the
G0/G1/G2 gates. Handoff to CTO (G1) occurs only after §8 sign-off.*
