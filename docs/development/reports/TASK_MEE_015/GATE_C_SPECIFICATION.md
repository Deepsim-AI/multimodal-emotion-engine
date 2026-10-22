# Gate C Specification — MEE License Integration

**Task ID:** TASK_MEE_015
**Author:** PM (intake agent)
**Date:** 2026-10-21 (16:5x PDT)
**Status:** AMENDED — APPROVED for G2 implementation (owner approval 2026-10-21)
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

---

## 3.8 Extended Requirements (Amendments — G2 Approval Conditions)

These amendments replace or extend the original R1–R27 requirements and are **mandatory** for G2 implementation. They implement the extensibility requirements from the owner's G2 approval decision.

### 3.8.1 VerificationResult (amends R1, R5)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R28 | `VerificationResult` dataclass in `mee/licensing/results.py`: fields — `valid` (bool), `license_status` (str | None), `plan_id` (str | None), `plan_name` (str | None), `features` (dict | None), `offline` (bool), `last_verified_at` (float \| None). | Unit tests constructing and inspecting all fields. |
| R29 | `LicenseClient.verify()` returns `VerificationResult` (not bare bool). The `license_status`, `plan_id`, `plan_name`, and `features` fields are populated from Keygate's `/verify` response `data` field. If the server returns an unknown/unmapped status string, it is passed through literally (forward-compatible). | Stub-server test: send known statuses (`active`, `suspended`, `revoked`, unknown string "custom_status") and verify result values. |
| R30 | `LicenseClient.status()` returns a dict with fields: `status`, `plan_id`, `plan_name`, `remaining_days`, `offline`, `features`. Status values map Keygate lifecycle states as follows: `active`→"licensed", `trialing`→"trialing", `past_due`→"expired", `canceled`→"expired", `expired`→"expired", `suspended`→"degraded", `revoked`→"degraded"; all other strings are used as-is. | Behavior test: stub Keygate returns each lifecycle status; verify correct mapping. |

### 3.8.2 TrialConfig (amends R8, R9, R10)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R31 | `TrialConfig` class in `mee/licensing/config.py`: field `trial_days: int = 14`, method `get_trial_days(plan_name \| None, features \| None) → int`. Resolution precedence: (1) Keygate plan feature `trial_period_days` if present and parseable as int; (2) env var `MEE_TRIAL_DAYS`; (3) default `14`. | Tests for all three resolution paths with stub data. |
| R32 | `TrialConfig.can_trial(features \| None) → bool`: returns False if Keygate plan feature `trial_enabled` is explicitly False; otherwise True. Documented as the mechanism by which Enterprise/OEM plans can disable trials entirely. | Tests: trial_enabled=True (or absent) → True; trial_enabled=False → False. |
| R33 | Trial marker cannot be reset or extended once set. If `.trial` already exists, `write_trial_marker()` is a **no-op** (does not update first_seen or expires_at). The only way to create a new trial is to delete the existing `.trial` file. | File-system test: write marker → modify it → verify is_trial_expired uses original expires_at; attempt second write → confirm original values unchanged. |
| R34 | Trial marker format: `{first_seen: <ISO8601>, expires_at: <ISO8601>}` (NOT unix timestamps). The ISO8601 format prevents timezone ambiguity. `remaining_trial_days()` returns ceil of fractional days remaining. | File-system test: write and parse ISO8601 values; verify calculation at boundary conditions. |

### 3.8.3 Feature-Based Behavior (amends R1, R4, R5)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R35 | **No plan_name matching.** No code in the MEE licensing package shall use `plan_name` in any conditional logic. All behavioral decisions are driven by the Keygate `features` map or env vars. | Code review + grep: no `if.*plan_name` or `match.*plan_name` patterns in `mee/licensing/`. |
| R36 | **Unknown features are ignored.** If a Keygate plan includes feature keys not known to the MEE client, they are silently preserved in the `features` dict but do not trigger errors, crashes, or implicit capability grants. | Test: stub server returns `{"unknown_feature_xyz": {"enabled": true}}`; verify client stores and ignores it without error. |
| R37 | **Missing entitlements default to disabled.** If a known feature key is absent from the Keygate response, the effective value is "disabled" (false / zero / not available). The feature map must NOT be used to infer capabilities that were not explicitly granted by the server. | Test: known key absent → defaults to disabled; test explicit True/False values. |

### 3.8.4 Activation Limit Handling (amends R1)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R38 | `ActivationLimitError` in `mee/licensing/errors.py`: subclass of `LicenseClientError`, with attribute `limit_hit: bool = True`. Message includes device limit info and referral to Keygate portal. | Test: stub server returns ACTIVATION_LIMIT error → verify exception raised and caught correctly. |
| R39 | `LicenseClient.activate()` handles the `ACTIVATION_LIMIT` error code from Keygate by raising `ActivationLimitError`. Other errors propagate normally. On success, caches token + features + public key as per existing spec. | Stub-server test: activate triggers ACTIVATION_LIMIT → exception; success path tested in R1. |

### 3.8.5 Lifecycle State Distinction (amends R4, R5)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R40 | `EmotionEngine.health()["license"]` reports `status` values: "licensed" (active), "trialing", "expired" (past_due/canceled/expired), "degraded" (suspended/revoked). The status MUST reflect the last verified state from Keygate, not a local assumption. | Behavior test: set each lifecycle state via stub → verify health() status. |
| R41 | Temporary network failures during `verify()` are distinguished from license expiration: if offline token is valid (iat + exp >= now), `process()` continues normally even when the server is unreachable. If offline token is absent or expired, `LicenseExpiredError` is raised only AFTER checking trial status (trial marker takes precedence over "no server response"). | Test: kill network during verify → cached token valid → process works; cached token absent + trial active → process works with warning; cached token absent + trial expired → LicenseExpiredError. |
| R42 | `LicenseClient.verify()` returns `VerificationResult` with `valid=False` and appropriate `license_status` when the Keygate server reports a license that is suspended or revoked (not just "expired"). The client MUST NOT treat suspended/revoked licenses as valid. | Test: stub server returns status="suspended" → result.valid=False; same for "revoked". |

### 3.8.6 Ed25519 Verification & Dependency Availability

| # | Requirement | Acceptance evidence |
|---|---|---|
| R43 | `mee/licensing/offline.py` uses `cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey.from_public_bytes()` for verification. If this import fails (package not available), the client raises `ImportError("ed25519 verification unavailable — install cryptography package")`. **No silent fallback.** | Test: verify import succeeds on test host; test graceful error if cryptography removed from path. |
| R44 | Base64url decoding uses `base64.urlsafe_b64decode()` with no padding (`+` → `-`, `/` → `_`, no trailing `=`). The signed data is the **raw base64url-encoded payload string**, not the decoded JSON. | Test: encode known test vector through both directions; verify roundtrip matches Keygate's format spec. |
| R45 | Before G2 implementation begins, the Implementer MUST run `python3 -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey; print('OK')"` and confirm success. This is a pre-flight gate, not a test. | Proof of successful import on MEE host (record in implementation report). |

### 3.8.7 Health Reporting Extension (amends R13)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R46 | `EmotionEngine.health()["license"]` extends the original spec's dict with: `plan_id` (str | None), `plan_name` (str | None), `features` (dict | None). If `self._license_client is None` (no process() call yet), omit the key entirely (backward compatible — existing code checking `health()["status"]` is unaffected). | Test: health() called before and after first process(); verify backward-compatible output. |

### 3.8.8 CLI Status Output Extension (amends R20)

| # | Requirement | Acceptance evidence |
|---|---|---|
| R47 | `mee-lic status` output includes: plan_id (truncated UUID, first 8 chars + "..."), plan_name, feature count and notable enabled features. All existing fields (status, remaining_days, device_id, last_verified) are preserved unchanged. | CLI test: activate against stub → verify all fields in output. |

---

## 3.9 Requirements Summary (Complete Inventory)

| Category | Original R# | Amended/Extended R# |
|---|---|---|
| License client core | R1–R7 | + R28, R29, R30, R35, R36, R37, R43, R44 |
| Trial and lockout | R8–R11 | + R31, R32, R33, R34, R38, R39, R41 |
| Engine integration | R12–R15 | + R40, R42, R46, R47 |
| Device ID | R16–R18 | (unchanged) |
| CLI | R19–R23 | + R47 |
| Observability | R24–R25 | (unchanged) |
| License file alignment | R26–R27 | (unchanged) |

**Total requirements: 47 (27 original + 20 extended).**

---

## Additional Acceptance Criteria (G2 Approval Conditions)

In addition to the existing acceptance criteria in §6, G2 implementation MUST satisfy ALL of the owner's required conditions:

### Condition 1: Amended Contracts Implemented
- `VerificationResult` dataclass implemented with all fields from R28–R29
- `TrialConfig` class with configurable duration and can_trial() from R31–R32
- Lifecycle status mapping from R40 (active/trialing/expired/degraded)
- Activation limit handling from R38–R39
- Extended health reporting from R46

### Condition 2: Keygate as Authority
- Server-side activation limits enforced ONLY by Keygate (no client-side count tracking)
- License entitlements read from Keygate's `features` map on every verify() call
- The `plan_name` is displayed but NEVER used in conditional logic

### Condition 3: Feature Validation & Unknown Features
- Tests covering known features with explicit True/False values
- Test for unknown feature keys (must be stored but ignored, not crash)
- Test for missing entitlements (must default to disabled, not implied-enabled)
- No plan_name string-matching in any MEE licensing code

### Condition 4: Lifecycle State Distinction
- Tests for each distinct lifecycle state: active, trialing, past_due, canceled, expired, suspended, revoked
- Test that temporary network failure + valid offline token → process continues (R41)
- Test that temporary network failure + invalid/absent offline token → correct error type

### Condition 5: Trial Configuration Precedence
- Tests documenting precedence: Keygate plan feature > `MEE_TRIAL_DAYS` env > default(14)
- Test that trial marker cannot be reset or extended (write is no-op if exists, R33)
- Documentation of all three precedence levels in code comments

### Condition 6: Ed25519 & Dependency Verification
- `cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey.from_public_bytes()` confirmed available on MEE host before G2 starts (R45)
- Tests for ed25519 token verification with known test vectors
- Test that base64url encoding/decoding is reversible without padding

### Condition 7: Five Licensing Categories Extensible
- Architecture supports Developer, Enterprise, OEM plans through Keygate's plan system
- No separate MEE software editions or code branches per license type
- All behavioral differences driven by the `features` map from Keygate

---

## Revised Acceptance Criteria (Gate C — Complete)

**Replace original §6 acceptance criteria with:**

1. All 47 requirements (R1–R47) pass their listed acceptance evidence.
2. E2E smoke chain: fresh install → trial → activate → process works → offline works → token expiry → LicenseExpiredError → deactivate → LicenseExpiredError.
3. All existing 170 tests pass with no regressions.
4. No license key, device ID, or token in logs (R25 grep + automated test).
5. `LICENSE.txt` is the license of record; pyproject.toml and README reference it.
6. **All 7 owner G2 conditions verified by dedicated tests** (see Conditions 1–7 above).
7. Keygate as authority: no hardcoded plan names in conditional logic; device limits enforced only server-side.
8. Unknown features stored but ignored; missing entitlements default to disabled — both tested.
9. Trial configuration precedence documented and tested (Keygate feature > env var > default).

---

## Version Bump Note

**Amended by CTO G1:** v0.1.0 → **v0.2.0** (unchanged from original spec).
