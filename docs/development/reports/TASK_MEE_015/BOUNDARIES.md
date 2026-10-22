# Boundaries — TASK_MEE_015: MEE License Integration (Gate C)

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Author:** CTO / Architect 🏗️  

---

## 1. In-Scope (Within G1–G5)

| Item | Status | Notes |
|---|---|---|
| `mee/licensing/` package (8 files) | ✅ In scope | New module per spec |
| EmotionEngine.process() license gate | ✅ In scope | Lazy-init + verify before inference |
| EmotionEngine.health() license block | ✅ In scope | Additive extension to existing method |
| `mee.api.license_status()` public API | ✅ In scope | Thin re-export wrapper |
| `mee-lic` CLI (activate/status/deactivate/verify) | ✅ In scope | argparse, stdlib only |
| pyproject.toml license + scripts updates | ✅ In scope | 3 lines changed |
| README.md license section update | ✅ In scope | 2 lines changed |
| LICENSE.txt canonicalization + LICENSE_1.0 retention | ✅ In scope | Owner already did the file swap; task formalizes references |
| Unit tests (device, trial, client, config) | ✅ In scope | ~6 test files |
| Integration tests (offline, CLI smoke, engine integration) | ✅ In scope | ~3 test files |
| E2E smoke test | ✅ In scope | Single standalone script |
| Version bump 0.1.0 → 0.2.0 | ✅ In scope | Final G5 deliverable |

## 2. Out of Scope (Explicitly Excluded)

| Item | Reason |
|---|---|
| Usage metering / API quota enforcement | Phase 2 — Keygate `/license/usage` endpoint exists but MEE does not use it yet |
| AI Companion licensing | Separate repo, separate task |
| Refund/cancellation policy | Keygate server-side only; no client code needed |
| White-label / resale | Not needed for initial MEE release |
| License key rotation UX | CTO did not mandate this in G1; out of scope |
| Trial key issuance via Keygate API | Owner accepted client-local trial (R8); no server-side trial license configured |
| Keygate server changes | Gate B complete; `RELEASE_KEY_ENCRYPTION_KEY` hardening done; no additional Keygate code needed |
| docs/ARCHITECTURE.md updates for licensing | PM handles in G5 per deliverables table; not CTO scope |
| Packaging/distribution (.whl, sdist) beyond pyproject.toml changes | Out of scope — packaging is a Phase 2+ concern |
| `mee/__init__.py` modifications (beyond what's needed for the package to work) | Minimal changes only; don't re-export licensing types from here |

## 3. Boundary Enforcement Rules

### Rule B1: No Cross-Repo Changes
Gates C work is scoped to `/home/deepsim/multimodal-emotion-engine/` ONLY. No changes to:
- `/home/deepsim/keygate_vps/` — Keygate server code
- `/home/deepsim/ai-companion-cognition/` — AI Companion project
- `/home/deepsim/AI_COMPANION_MEMORY_SYSTEM/` — Memory Foundation project

### Rule B2: Frozen Contracts (Section 4 of CORE_CONTRACTS.md)
The following files must have zero unapproved changes during G2. Any deviation must be documented and re-approved by the CTO before acceptance at G3/G4:
- All existing `mee/` package files not listed as modification targets in CTO Plan §3
- All existing `tests/` files not listed as test creation targets
- `pyproject.toml` changes limited to: license field, license-files field, and one new `[project.scripts]` entry

### Rule B3: No New Dependencies
G1 verified that `cryptography` and `requests` are both available as existing transitive/direct deps. G2 must not add any new package requirements to pyproject.toml beyond what's already listed.

### Rule B4: CLI Must Use Stdlib Only
The `mee-lic` CLI uses argparse (Python stdlib). No third-party argument parsing libraries.

### Rule B5: License Data Never Logged
Per R25: license keys, device IDs, and signed tokens must NEVER appear in any log output, traceback, or test capture. This is a hard boundary violation if breached.

---

## 4. Gate C Deliverables Summary

| Deliverable | Owner | Location |
|---|---|---|
| `mee/licensing/` package (8 files) | Implementer | `<repo>/mee/licensing/` |
| Engine integration (3 method modifications) | Implementer | `mee/api/engine.py` |
| `license_status()` public API | Implementer | `mee/api/license.py` + re-export |
| `mee-lic` CLI | Implementer | `mee/licensing/cli.py` + pyproject entry point |
| Unit tests (~6 files) | Implementer | `tests/test_licensing_*.py` |
| Integration/E2E tests (~3 files) | Implementer | `tests/test_engine_license_integration.py`, `tools/license_smoke_test.py` |
| CTO_PLAN.md | ✅ CTO (done this turn) | `docs/development/reports/TASK_MEE_015/CTO_PLAN.md` |
| COGNITION_ARCHITECTURE.md | ✅ CTO (done this turn) | `docs/development/reports/TASK_MEE_015/COGNITION_ARCHITECTURE.md` |
| CORE_CONTRACTS.md | ✅ CTO (done this turn) | `docs/development/reports/TASK_MEE_015/CORE_CONTRACTS.md` |
| BOUNDARIES.md | ✅ CTO (done this turn) | `docs/development/reports/TASK_MEE_015/BOUNDARIES.md` |

**G1 COMPLETE. All Gate G1 artifacts produced.**

## 5. CTO G1 Amendment References (Required by Owner)

The following items from the extensibility analysis must be implemented in G2:
- **Amendment A-G** in `CORE_CONTRACTS.md` §7 — all required before implementation
- Read `GATE_C_EXTENSIBILITY_ANALYSIS.md` in full before starting G2
- These amendments were added at the owner's request to ensure multi-tier license support

## 6. Post-G5 Tasks (Out of Scope for This Task)

| Item | Why Out of Scope | Who Handles |
|---|---|---|
| Create Developer plan in Keygate | Server-side admin action | Owner / Admin |
| Create Enterprise plan in Keygate | Server-side admin action | Owner / Admin |
| Create OEM license template in Keygate | Server-side admin action | Owner / Admin |
| Update AI Companion licensing to use Keygate | Separate repo, separate task | PM follows up separately |

