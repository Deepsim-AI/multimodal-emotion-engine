# Gate C Specification — MEE License Integration

**Task ID:** TASK_MEE_015
**Author:** PM (intake agent)
**Date:** 2026-10-21 (16:5x PDT)
**Status:** PROPOSED — awaiting CTO G1 review
**Predecessor:** Keygate Gate B (completed 2026-10-21, including the `RELEASE_KEY_ENCRYPTION_KEY` hardening item)
**License change in flight:** `LICENSE.txt` (Deepsim Commercial Software License v1.1, October 2026) — the `mee-licensing` module in this task is the technical enforcement path for that license.

---

## 1. Background

Keygate v0.1.15 is deployed at `https://licenses.deepsim.ai:8443` with:

- Two products: **MEE** and **AI Companion**
- Two live plans (both `max_activations=3`):
  - MEE Pro → `price_1USnuOC0UMgquCywJEHP30Gw`
  - AI Companion Pro → `price_1USntOC0UMgquCywTEUzVx5V`
- Two active licenses (both encrypted at rest after the 2026-10-21 hardening):
  - `KG-V4ACZV6J-RT6D5Y95-RUWLQ2XL-98JJSH4C` (MEE, manual)
  - `KG-F42UK5KE-MVZYGU8R-S8EYY2M9-SFAE8GFR` (MEE, test-mode Stripe webhook)
- Ed25519 public key at `GET /api/v1/license/pubkey` (client-side offline verification)
- Stripe **live mode** active (real customer payments possible)

The MEE product has **no client-side license check yet** — `EmotionEngine.process()` runs unconditionally. Gate C adds the client-side license gate.

---

## 2. Objective

Add a `mee/licensing/` package that:

1. Activates MEE against a live Keygate instance on first run.
2. Periodically re-verifies the license (≤ 7-day cadence).
3. Works offline within token TTL (no hard lockout during outages).
4. Enforces a **14-day trial** on first run (no license key present), then hard-stops.
5. Reports a **stable device ID** so Keygate's server-side activation cap (`max_activations=3`) is the authority on device limits.
6. Exposes a clean public API (`mee.api.license_status`) and a CLI (`mee-lic`).

**Out of scope for this task:**
- Usage metering / API quota enforcement (Keygate `/license/usage`) — that is a Phase-2 concern for MEE Pro API.
- AI Companion licensing — separate follow-up task in its own repo.
- Refund/cancellation policy enforcement — Keygate server-side.
- White-label / resale — not needed for initial MEE release.
- License key rotation UX — CTO decides in G1.
- Trial key issuance flow — the trial is client-side generated, server-side only *records* it on first check-in if Keygate supports it; otherwise the trial is purely client-local. CTO decides.

---

## 3. Discrete Requirements (testable)

### 3.1 License client core

| # | Requirement | Acceptance evidence |
|---|---|---|
| R1 | `mee/licensing/client.py` provides `LicenseClient` with `activate(license_key, device_id)`, `verify()`, `status()`, `deactivate()` methods. | Unit tests with a stub HTTP server. |
| R2 | Config via env vars: `MEE_LICENSE_SERVER` (default `https://licenses.deepsim.ai:8443`), `MEE_LICENSE_KEY` (optional), `MEE_DEVICE_ID` (optional, defaults to auto-generated). | Config tests. |
| R3 | Local state persisted at `$MEE_HOME/licenses/{key_hash}.json` (default `$HOME/.config/mee-licensing/`). Contains: license key, device ID, last verified timestamp, cached ed25519 public key, cached signed token. | File-system tests. |
| R4 | On `verify()`: if cached token is valid and unexpired → return OK without network. If expired or missing → call `GET /api/v1/license/verify` with the license key; on success, cache the new signed token. | Stub-server tests. |
| R5 | On `verify()` failure (network error): fall back to cached ed25519 public key to validate the cached signed token. If the token is still within TTL → OK (offline mode). If token expired → trial/lockout per R9. | Offline-mode tests (network disabled). |
| R6 | `deactivate()` calls `POST /api/v1/license/deactivate` and removes the local state file. | Stub-server tests. |
| R7 | All HTTP calls use `requests` with a 5-second timeout. No retry storm — at most one retry per call, exponential backoff base 1s, max 2 retries. | Config + behavior tests. |

### 3.2 Trial and lockout (per owner decision)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R8 | On first run with no valid license: write a trial marker at `$MEE_HOME/licenses/.trial` containing `{first_seen: <ISO8601>, expires_at: first_seen + 14 days}`. | File-system tests. |
| R9 | If the trial has not expired and no valid license is present: allow `process()` calls, but log a warning on every call (rate-limited to once per 10 minutes). | Behavior tests. |
| R10 | If the trial has expired and no valid license is present: `EmotionEngine.process()` raises `LicenseExpiredError` (new exception class in `mee/licensing/errors.py`). `mee.api` continues to import cleanly; only `process()` fails. | Behavior tests. |
| R11 | A valid license (online or offline-within-TTL) bypasses the trial check. | Behavior tests. |

### 3.3 Engine integration

| # | Requirement | Acceptance evidence |
|---|---|---|
| R12 | `EmotionEngine.__init__` does **not** perform any license check (lazy). `process()` calls `LicenseClient.verify()` before inference; on failure → raise `LicenseExpiredError`. | Behavior tests. |
| R13 | `EmotionEngine.health()` adds a `license: {status, remaining_days | null, offline: bool}` block. | Behavior tests. |
| R14 | `mee.api` re-exports `license_status()` → thin wrapper over `LicenseClient.status()`. | Behavior tests. |
| R15 | New exception `LicenseExpiredError` in `mee.licensing.errors`; documented in `docs/ARCHITECTURE.md`. | Code + docs. |

### 3.4 Device ID

| # | Requirement | Acceptance evidence |
|---|---|---|
| R16 | `MEE_DEVICE_ID` env var takes precedence. Otherwise auto-generate a stable ID: `sha256(machine_id + boot_uuid)` → first 16 hex chars, persisted at `$MEE_HOME/device_id`. | File-system tests. |
| R17 | `device_id` is sent in the `activate()` and `verify()` requests (Keygate `device_id` field or `X-Device-ID` header — CTO decides from Keygate 0.1.15 API docs). | Stub-server tests. |
| R18 | The same machine reports the same device ID across restarts. | File-system tests (delete `/tmp`, keep `$MEE_HOME`). |

### 3.5 CLI

| # | Requirement | Acceptance evidence |
|---|---|---|
| R19 | `mee-lic activate <key>` — activates, prints license status. | CLI tests. |
| R20 | `mee-lic status` — prints status (licensed/trial/expired, remaining days, device ID, last verified). | CLI tests. |
| R21 | `mee-lic deactivate` — deactivates. | CLI tests. |
| R22 | `mee-lic verify` — forces a network verify. | CLI tests. |
| R23 | `pyproject.toml` declares `mee-lic = "mee.licensing.cli:main"` entry point. | `pip install -e .` + `mee-lic --help` smoke test. |

### 3.6 Observability

| # | Requirement | Acceptance evidence |
|---|---|---|
| R24 | All license events (activate, verify OK, verify fail, offline fallback, trial start, trial expiry) logged via `logging` at appropriate levels. | Code review. |
| R25 | No license key, device ID, or signed token ever logged. | Code review + log-scraping test. |

### 3.7 License file alignment

| # | Requirement | Acceptance evidence |
|---|---|---|
| R26 | `LICENSE.txt` (v1.1) is the canonical license. `LICENSE_1.0` is retained for reference. `pyproject.toml` `license` field updated to `{text = "See LICENSE.txt"}` (proprietary — not an SPDX identifier). | `pyproject.toml` diff. |
| R27 | `README.md` and `docs/` reference `LICENSE.txt` as the license of record. | `grep -r "LICENSE_1.0" docs/` returns 0 hits (except the reference line). |

---

## 4. Architecture (high-level, CTO to refine in G1)

```
mee/
├── api/
│   ├── engine.py          # EmotionEngine — process() calls LicenseClient.verify()
│   └── __init__.py        # re-export license_status()
├── licensing/             # NEW
│   ├── __init__.py
│   ├── client.py          # LicenseClient (activate/verify/status/deactivate)
│   ├── config.py          # LicensingConfig (env vars, defaults)
│   ├── device.py          # stable device ID generation + persistence
│   ├── errors.py          # LicenseExpiredError, LicenseClientError
│   ├── offline.py         # ed25519 token verification (cached pubkey)
│   ├── trial.py           # trial marker read/write
│   └── cli.py             # mee-lic entry point
└── ...
```

**No new external dependencies.** `requests` is already a MEE dependency. ed25519 verification can use `cryptography` (already a transitive dep of `speechbrain`/`mediapipe` — verify in G1) or a pure-Python fallback.

---

## 5. Integration points (exact files/symbols — for CTO R-SI-2 guidance)

| File | Symbol | Action |
|---|---|---|
| `mee/api/engine.py` | `EmotionEngine.__init__` (line ~127) | Add optional `license_client` param (default None → lazy-init from config). |
| `mee/api/engine.py` | `EmotionEngine.process` (line ~216) | Call `self._license_check()` before inference. |
| `mee/api/engine.py` | `EmotionEngine.health` (line ~339) | Add `license` block. |
| `mee/api/__init__.py` | `__all__` | Re-export `license_status`. |
| `pyproject.toml` | `[project.scripts]` | Add `mee-lic = "mee.licensing.cli:main"`. |
| `pyproject.toml` | `[project] license` | Change from `Apache-2.0` to `See LICENSE.txt`. |
| `README.md` | License section | Point to `LICENSE.txt`. |

---

## 6. Acceptance criteria (Gate C)

1. All 27 discrete requirements (R1–R27) pass their listed acceptance evidence.
2. End-to-end smoke:
   - `pip install -e .` on a clean venv → `mee-lic status` → "trial" (first run).
   - `mee-lic activate KG-...` (real MEE license from Keygate) → `mee-lic status` → "licensed, active".
   - `EmotionEngine().process(frame, audio)` → works.
   - Kill network → `EmotionEngine().process(frame, audio)` → still works within token TTL (offline mode).
   - Wait for token TTL (or mock time) → `process()` → `LicenseExpiredError`.
   - `mee-lic deactivate` → `process()` → `LicenseExpiredError`.
3. `pytest -q` → all existing tests (106+) pass, no regressions.
4. No license key, device ID, or token appears in any log, traceback, or test output (verified by grep + a test that scrapes captured logs).
5. `LICENSE.txt` is the license of record; `pyproject.toml` and `README.md` reference it.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Keygate API endpoint paths differ from spec (0.1.15) | CTO verifies against `ghcr.io/tabloy/keygate:0.1.15` docs in G1 before Implementer starts. |
| ed25519 token format mismatch | CTO verifies against a real signed token from the live Keygate instance in G1. |
| Trial marker tampered by user | Documented as best-effort (user can delete `$MEE_HOME`). Hard stop is not a DRM mechanism — it is a courtesy gate. Commercial enforcement is via Keygate activation cap + Stripe. |
| Offline mode abused (never go online) | Token TTL is server-set (7 days). After TTL, offline verify fails → trial/lockout. Documented. |
| Device ID spoofing | Same as trial — best-effort. Server-side activation cap is the real limit. |
| `cryptography` not available on Jetson | G1 verifies; fallback to pure-Python ed25519 (e.g., `pynacl` or a 50-line pure-Python impl) if needed. |
| License key leaked in logs | R25 test + code review. |

---

## 8. What the CTO must do in G1

1. Read this spec + `KEYGATE_GATE_B_REPORT.md` + `KEYGATE_PREDEPLOYMENT_AUDIT.md`.
2. Verify Keygate 0.1.15 API endpoints (activate, verify, deactivate, pubkey) against the live instance at `https://licenses.deepsim.ai:8443`.
3. Verify the ed25519 signed-token format (capture a real token from `GET /api/v1/license/verify` with a valid license key).
4. Decide: trial key issuance (client-local vs server-recorded), device ID transmission format, token TTL policy, retry policy.
5. Produce `CTO_PLAN.md` with:
   - Exact file/symbol/line-range guidance for every change (R-SI-2).
   - Task breakdown (Implementer sessions, ≤ 3 model-pressure windows).
   - Test strategy (unit + integration + E2E smoke).
   - Acceptance criteria derived from §6.
6. Do **not** write implementation code (CTO is read-only by policy).

---

## 9. Deliverables

| Deliverable | Owner | Location |
|---|---|---|
| `mee/licensing/` package | Implementer | `<repo>/mee/licensing/` |
| `EmotionEngine` integration | Implementer | `mee/api/engine.py` |
| `mee-lic` CLI | Implementer | `mee/licensing/cli.py` + `pyproject.toml` |
| Unit + integration tests | Implementer | `tests/test_licensing_*.py` |
| E2E smoke script | Implementer | `tools/license_smoke.sh` (optional) |
| `CTO_PLAN.md` | CTO | `docs/development/reports/TASK_MEE_015/` |
| `REVIEW_REPORT.md` | Reviewer | `docs/development/reports/TASK_MEE_015/` |
| `CTO_APPROVAL.md` + `TASK_COMPLETION_AUDIT.md` | CTO | `docs/development/reports/TASK_MEE_015/` |
| `CLOSED.md` + `PM_CLOSED.md` | PM | `docs/development/reports/TASK_MEE_015/` |
| `PROJECT_STATUS.md` update (Phase 7 → COMPLETE) | PM | `<repo>/PROJECT_STATUS.md` |
| `CHANGELOG.md` update (v0.2.0 — Licensing) | PM | `<repo>/CHANGELOG.md` |

---

## 10. Version bump

`pyproject.toml` `version`: **0.1.0 → 0.2.0** (minor — new licensing capability, no breaking API changes to existing `EmotionEngine.process` contract for licensed users).

---

## 11. Governance

- Follows DS-EO workflow: G0 (PM intake, this doc) → G1 (CTO plan) → G2 (Implementer) → G3 (Reviewer) → G4 (CTO approval) → G5 (PM closure).
- CTO is read-only; Implementer is full-repo; Reviewer is read+write-only-REVIEW_REPORT.
- No cross-task assumption of completion.
- All artifacts land in `docs/development/reports/TASK_MEE_015/`.
