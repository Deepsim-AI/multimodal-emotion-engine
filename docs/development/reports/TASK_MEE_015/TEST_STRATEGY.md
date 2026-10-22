# Test Strategy — TASK_MEE_015: MEE License Integration (Gate C)

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Author:** CTO / Architect 🏗️  

---

## 1. Test Philosophy

Per AGENTS.md R-SI-6: **Separate implementation from documentation.** Tests are part of the implementation deliverable, not a separate phase. All tests written during G2 by the Implementer; no separate test-writing session needed.

## 2. Test Categories

### 2.1 Unit Tests (Session A — Core Package)

| File | Scope | Key Test Cases |
|---|---|---|
| `tests/test_licensing_config.py` | LicensingConfig | Defaults, MEE_LICENSE_SERVER override, MEE_LICENSE_KEY override, MEE_DEVICE_ID override, MEE_HOME path resolution, state_dir creation |
| `tests/test_licensing_device.py` | device.py | Auto-generated ID is deterministic, MEE_DEVICE_ID takes precedence, persistent across restarts (delete `/tmp`, keep state), SHA-256 computation correctness |
| `tests/test_licensing_trial.py` | trial.py | Write marker on first call, expiry at 14 days, remaining_days calculation, missing marker returns False for is_trial_expired() |
| `tests/test_licensing_client.py` | client.py | activate with stub server (success + already_activated), verify success/404, deactivate success/network error, retry logic (max 1 retry), timeout enforcement (5s) |

### 2.2 Integration Tests (Session B — Integration)

| File | Scope | Key Test Cases |
|---|---|---|
| `tests/test_licensing_offline.py` | offline.py + client interaction | Cache valid token → simulate network failure → verify still returns True via offline; expired cached token → offline returns False; invalid signature detection |
| `tests/test_licensing_cli.py` | cli.py | `mee-lic status` in trial mode, `mee-lic activate` with stub server, `mee-lic verify` forces refresh, `mee-lic deactivate` removes state, help output present |
| `tests/test_engine_license_integration.py` | EmotionEngine + LicenseClient | process() raises LicenseExpiredError when license invalid; process() works when valid; health() returns license block after first process(); lazy init (no license client on __init__); multiple process() calls reuse client |

### 2.3 E2E Smoke Test

| File | Scope | Key Flow |
|---|---|---|
| `tools/license_smoke_test.py` | Full chain fresh install → trial status → activate (stub) → licensed status → process works → offline → expired → deactivated → LicenseExpiredError | All in one executable script with isolated temp `$MEE_HOME` |

### 2.4 Security Test (R25 — No Key Leakage)

Single test that:
1. Runs CLI commands with all three license paths (trial, activated, expired)
2. Captures ALL stdout/stderr/log output
3. Greps for patterns: `KG-[A-Z0-9]{8}-`, hex device IDs, token fragments
4. Asserts zero matches

## 3. Test Execution Requirements

- **Before G2**: Run `pytest -q` on existing 170 tests — baseline pass confirmed
- **After G2**: All 170 original tests MUST pass; 0 regressions allowed
- **New test count**: ~6 unit + ~3 integration + 1 E2E + 1 security = ~11 new tests
- **Total expected**: ~181 tests

## 4. Stub Server for Testing

A lightweight HTTP stub server is needed in `tests/test_licensing_client.py`. Use Python's `http.server.HTTPServer` with a custom handler (no third-party dependency). Test endpoints:
- `POST /api/v1/license/activate` → return `{success: true, data: {...}}` or `already_activated`
- `POST /api/v1/license/verify` → return token + status for valid key; 404 for invalid
- `POST /api/v1/license/deactivate` → confirm success

## 5. Rejection Criteria (G3)

The reviewer MUST reject the G2 deliverables if:
1. Any of the 170 existing tests fail with new code
2. No test exists for the offline verification path
3. A license key, device ID, or token appears in any captured log output
4. `mee-lic --help` fails to run after `pip install -e .`

---

**Test strategy approved by CTO G1. Ready for Implementer execution.**
