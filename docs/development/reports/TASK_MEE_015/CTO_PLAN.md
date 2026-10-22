# CTO Plan — TASK_MEE_015: MEE License Integration (Gate C)

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Author:** CTO / Architect 🏗️ (`ollama/qwen3.6:35b`)  
**Phase:** G1 — Planning  

---

## 1. Pre-Planning Verification (G1 Gate)

### 1.1 Keygate Live Instance Status
- **Health**: `GET /health` → `{"checks":{"database":"ok"},"status":"ok","version":"0.1.15"}` ✅
- **Public SDK endpoints verified live:**
  - `GET /api/v1/license/pubkey` → `algorithm=ed25519`, `public_key=11f2184de3fd45d7b2f9cf967d61935e5a697d43538fc67e16bd7158b050e75e` (64-char hex) ✅
  - `POST /api/v1/license/activate` → `BAD_REQUEST: license_key and identifier are required` ✅ (endpoint exists, body params confirmed)
  - `POST /api/v1/license/verify` → same BAD_REQUEST pattern ✅
  - `POST /api/v1/license/deactivate` → same BAD_REQUEST pattern ✅
- **Oracle hardening confirmed**: All four SDK endpoints accept **no auth header** — they use `license_key` + `identifier` JSON body fields. `/verify` and `/deactivate` collapse license-knowable failures to `404 LICENSE_NOT_FOUND`.

### 1.2 Token Format (verified via OpenAPI spec)
- **Format**: `<base64url-payload>.<base64url-signature>`
- **Signed bytes**: The base64url-encoded *payload string* (not the raw JSON).
- **Payload fields** (all unix timestamps):
  - `lid` — license UUID
  - `pid` — product ID
  - `pln` — plan ID  
  - `sts` — status at issue (`active`, `trialing`, etc.)
  - `did` — device identifier (SHA-256 of original identifier + product ID)
  - `ftr` — feature entitlements map
  - `iat` / `exp` — issued at / check-in interval (seconds)
  - `vun` — license lapse date (absent = perpetual)
  - `upd` — updates maintenance period end (absent = no limit)
  - `grc` — grace days after `vun`
  - `nce` — per-issuance nonce

### 1.3 Dependencies Assessment
- **`cryptography`** 3.4.8 already installed, `Ed25519PublicKey.from_public_bytes()` available ✅
- **`requests`** already a transitive dependency ✅
- **No new Python packages needed.**

### 1.4 Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Trial implementation** | Client-local `.trial` marker + owner-accepted 14-day expiry (per user request). Keygate does not provide a "trial" license type for MEE specifically, and creating trial records via the API is out of scope. The server-side activation cap handles real device limits. | Simpler; no additional Keygate endpoint calls needed. User accepted this model in their G0 request. |
| **Device ID transmission** | `identifier` JSON field on all SDK calls (not a separate header). Consistent with Keygate 0.1.15 API contract. | Single parameter, well-documented, no ambiguity about where to put it. |
| **Token TTL policy** | Use the server-returned `exp` value from the signed token payload as the check-in interval. Store in local state; if `now - iat > exp`, trigger a network verify. If verify fails → fall back to cached offline verification. | The spec's R4/R5 behavior maps directly. The TTL is dynamic (plan-configured), not hardcoded. |
| **Retry policy** | Max 1 retry per call, exponential backoff base 1s, max 2 retries total. Matches the spec's "no retry storm" requirement (R7). | Keygate has brute-force protection (5 failures → 30s lockout); aggressive retries would trigger this. |
| **Offline mode** | ed25519-verify the cached token using the cached public key. If `now < iat + exp` in the token → offline OK. Else → trial/lockout. | Server is unavailable; cached signed token is the only evidence of prior activation. The `cryptography` library handles verification deterministically. |
| **License check placement** | Lazy: first call to `EmotionEngine.process()` triggers license initialization. On failure, raise `LicenseExpiredError`. Subsequent calls reuse the initialized client. | No startup cost for users who don't use `process()`. Consistent with the existing lazy model loading pattern in MEE. |
| **`license_files` in pyproject.toml** | Change from `["LICENSE", ...]` to `["LICENSE.txt", "docs/THIRD_PARTY_LICENSES.md"]` to match R26. | Proprietary license text is not SPDX-encodable; keep `{text = "See LICENSE.txt"}` but fix the file path reference. |

---

## 2. Implementation Strategy

### Phasing — 2 sessions to manage model pressure

Given the scope (new package + integration + tests), I split into **2 Implementer sessions** to stay within model context limits:

- **Session A (core)**: Licensing package (`mee/licensing/`) + trial logic + CLI
- **Session B (integration)**: Engine integration + health() update + api/__init__.py + license file alignment + E2E tests

### 3. Exact File/Symbol/Line-Range Guidance (R-SI-2)

#### 3.1 New Files to Create

| File | Purpose | Notes |
|---|---|---|
| `<repo>/mee/licensing/__init__.py` | Package init; export `LicenseClient`, `LicenseExpiredError` | Minimal — just re-exports |
| `<repo>/mee/licensing/client.py` | `LicenseClient` class: activate/verify/status/deactivate | Core HTTP client against Keygate |
| `<repo>/mee/licensing/config.py` | `LicensingConfig` dataclass: env vars, defaults | MEE_LICENSE_SERVER, MEE_LICENSE_KEY, MEE_DEVICE_ID, MEE_HOME |
| `<repo>/mee/licensing/device.py` | Stable device ID generation + persistence | SHA-256(machine_id + boot_uuid) → first 16 hex chars |
| `<repo>/mee/licensing/errors.py` | `LicenseExpiredError`, `LicenseClientError` exception classes | Simple subclass tree |
| `<repo>/mee/licensing/offline.py` | ed25519 token verification with cached public key | Parse base64url payload, verify signature using cached pubkey |
| `<repo>/mee/licensing/trial.py` | Trial marker read/write (.trial JSON) | first_seen + expires_at ISO8601; 14-day window |
| `<repo>/mee/licensing/cli.py` | `mee-lic` CLI: activate/status/deactivate/verify | Uses click or argparse (prefer stdlib argparse for no new deps) |
| `<repo>/tests/test_licensing_client.py` | Unit tests with stub HTTP server | R1-R7 |
| `<repo>/tests/test_licensing_trial.py` | Trial marker tests | R8-R11 |
| `<repo>/tests/test_licensing_offline.py` | Offline token verification tests (mock network) | R5 |
| `<repo>/tests/test_licensing_device.py` | Device ID persistence tests | R16-R18 |
| `<repo>/tests/test_licensing_cli.py` | CLI command tests | R19-R23 |

#### 3.2 Files to Modify

| File | Symbol / Location | Change | Lines (approx) |
|---|---|---|---|
| `mee/api/engine.py` | `class EmotionEngine`, `__init__` (line ~127) | Add `self._license_client: LicenseClient \| None = None` as instance attribute. Lazy-init on first `process()` call. Read `MEE_LICENSE_KEY` from config if set. | +3 lines |
| `mee/api/engine.py` | `EmotionEngine.process` (line ~216) | Add `_license_check()` call at top of method, before any inference. On `LicenseExpiredError`, re-raise. On verify failure without offline fallback → raise `LicenseExpiredError`. | +5 lines at start |
| `mee/api/engine.py` | `EmotionEngine.health` (line ~339) | Add `license` block to returned dict: `{status, remaining_days \| null, offline: bool}`. Call `self._license_client.status()` if initialized; return `None` or omit if not yet initialized. | +10 lines in method body |
| `mee/api/__init__.py` | `__all__` | Re-export `license_status` from `mee.api.license`. | +2 lines |
| `mee/api/license.py` | **NEW file** (if needed) | Thin wrapper: imports `LicenseClient`, exposes `license_status()` function | 15-20 lines |
| `pyproject.toml` | `[project] license` (line 11) | Change `{text = "Apache-2.0"}` → `{text = "See LICENSE.txt"}` | 1 line |
| `pyproject.toml` | `license-files` (line 12) | Change `["LICENSE", "docs/THIRD_PARTY_LICENSES.md"]` → `["LICENSE.txt", "docs/THIRD_PARTY_LICENSES.md"]` | 1 line |
| `pyproject.toml` | `[project.scripts]` section | Add `mee-lic = "mee.licensing.cli:main"` entry point | +1 line |
| `README.md` | Third-Party Components & Licensing section (line ~145) | Update first row: "Core package code" → "Deepsim Commercial Software License v1.1 (proprietary)" ✅ commercial use | 2 lines changed |
| `docs/development/reports/TASK_MEE_015/LICENSE.txt` | **Move to repo root** | Rename `LICENSE_1.0` → keep as-is; `LICENSE.txt` already at root from owner's work | Already done (untracked) |

#### 3.3 EmotionEngine._license_check() Method

This is a NEW internal method on `EmotionEngine`:

```python
def _license_check(self):
    """Initialize license client and verify license status.
    
    Called lazily on first process() call. Raises LicenseExpiredError
    if no valid license (trial expired or never activated).
    Returns None on success (silent).
    """
    if self._license_client is None:
        from ..licensing.client import LicenseClient
        from ..licensing.config import LicensingConfig
        config = LicensingConfig()
        self._license_client = LicenseClient(config)
    
    # Try online verify first
    verified = False
    offline_fallback = False
    
    try:
        verified = self._license_client.verify()  # returns bool: was valid?
    except NetworkError:
        offline_fallback = True
        verified = self._license_client.verify_offline()  # cached token check
    
    if not verified:
        from ..licensing.trial import is_trial_expired
        if is_trial_expired():
            raise LicenseExpiredError("Trial expired. Activate a license to continue.")
        raise LicenseExpiredError("License verification failed and no offline token available.")

    # Cache the fact that check was done so we don't repeat on every process() call?
    # NO — per spec R4/R5, verify must be called before each process().
    # But the CLIENT handles cache expiration internally.
```

**Wait** — re-reading the spec carefully: R12 says `process()` calls `LicenseClient.verify()` *before inference*. This means verification happens on every `process()` call. The client's internal caching (R4) prevents unnecessary network calls — but the method is still called each time.

Revised approach: Call `self._license_client.verify()` before every `process()`. The client handles caching internally per R4/R5. If it returns False (invalid), raise `LicenseExpiredError` after checking trial status.

#### 3.4 MEEConfig Addition

Add a `license_key` field to `MEEConfig` for the optional initial license key:

```python
# In MEEConfig dataclass (~line 54, after `voice_enabled`)
license_key: Optional[str] = field(default_factory=lambda: os.environ.get("MEE_LICENSE_KEY"))
```

This avoids a second env var; `LicensingConfig` will read from env directly anyway. The config field is for consistency with the existing pattern but not strictly necessary since the licensing layer reads env vars itself.

**Decision**: Skip adding to `MEEConfig`. `LicensingConfig` in the new module reads env vars independently. This avoids polluting the core config schema with licensing concerns and keeps licensing a separate concern (SRP).

---

## 4. Task Breakdown for Implementer

### Session A — Core Licensing Package
**Scope**: R1-R7, R8-R11, R16-R18, R24-R25, all new `mee/licensing/` files + tests.

| Priority | Item | Files | Complexity |
|---|---|---|---|
| 1 | `errors.py` — exception classes | `mee/licencing/errors.py` | Trivial |
| 2 | `config.py` — LicensingConfig dataclass | `mee/licensing/config.py` | Simple |
| 3 | `device.py` — stable device ID | `mee/licensing/device.py` | Moderate |
| 4 | `trial.py` — trial marker logic | `mee/licensing/trial.py` | Simple |
| 5 | `offline.py` — ed25519 verification | `mee/licensing/offline.py` | Moderate (crypto) |
| 6 | `client.py` — LicenseClient HTTP client | `mee/licensing/client.py` | Complex (network, caching, error handling) |
| 7 | Package `__init__.py` | `mee/licensing/__init__.py` | Trivial |
| 8 | Tests: device + trial + offline + client | 4 test files | Moderate-High |

### Session B — Integration & Alignment
**Scope**: R12-R15, R19-R23, R26-R27, engine integration, CLI, pyproject changes.

| Priority | Item | Files | Complexity |
|---|---|---|---|
| 1 | `cli.py` — mee-lic CLI | `mee/licensing/cli.py` | Moderate |
| 2 | Engine integration (3 methods modified) | `mee/api/engine.py` | Moderate |
| 3 | `api/__init__.py` license_status export + new `license.py` | `mee/api/`, `mee/api/license.py` | Simple |
| 4 | pyproject.toml changes (license + scripts) | `pyproject.toml` | Trivial |
| 5 | README.md license section update | `README.md` | Trivial |
| 6 | LICENSE file alignment (already done by owner; verify) | `LICENSE.txt`, `LICENSE_1.0` | Trivial |
| 7 | Tests: CLI + integration + E2E smoke | 3 test files | Moderate |

---

## 5. Test Strategy

### Unit Tests (Session A)
- **`test_licensing_config.py`**: Default values, env var overrides, MEE_HOME path resolution
- **`test_licensing_device.py`**: Device ID stability across calls, `MEE_DEVICE_ID` override, SHA-256 computation
- **`test_licensing_trial.py`**: Trial marker creation, expiry (14 days), tampered marker detection
- **`test_licensing_client.py`**: Stub server for activate/verify/deactivate; network timeout behavior; retry logic; 5s timeout enforcement

### Integration Tests (Session B)
- **`test_licensing_offline.py`**: Mock network failure → offline token verification via `cryptography.Ed25519PublicKey`
- **`test_licensing_cli.py`**: CLI smoke tests against stub server + trial-only mode
- **`test_engine_license_integration.py`**: EmotionEngine with mock license client; verify that process() raises on invalid license, works on valid license

### E2E Smoke Test (Session B)
A standalone script (`tools/license_smoke_test.py`) that:
1. Creates a fresh virtualenv-like temp dir with `$MEE_HOME` pointing to a temp location
2. `mee-lic status` → "trial" (first run, no license)
3. Activates against a stub Keygate (or skips if live Keygate is needed for testing)
4. Verifies that `EmotionEngine()` imports cleanly

### Log Scraping Test (R25)
A single test that runs CLI commands and grep-captures all log output for:
- License key patterns (`KG-[A-Z0-9]{8}-`)
- Device ID values
- Signed token fragments

---

## 6. Acceptance Criteria (derived from GATE_C_SPECIFICATION.md §6)

1. All 27 discrete requirements (R1–R27) pass — each verified by its listed acceptance evidence type.
2. E2E smoke chain: fresh install → trial → activate → process works → offline works → token expiry → LicenseExpiredError → deactivate → LicenseExpiredError.
3. Existing 170 tests pass with no regressions.
4. No license key, device ID, or token in logs (R25 grep + automated test).
5. `LICENSE.txt` canonical; pyproject.toml + README reference it (R26/R27).
6. Version bump: 0.1.0 → 0.2.0.

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `cryptography` 3.4.8 API differences (Ed25519PublicKey.from_public_bytes() signature) | Medium | Verify against live Python in G1 — confirmed available ✅ |
| Token format mismatch (base64url vs base64, payload encoding) | High | OpenAPI spec gives exact field names and encoding; implementer must verify via a real token capture if possible. **If no valid license is accessible, the plan defers this to the Implementer's first test against live Keygate.** |
| Oracle hardening (all invalid-license responses collapse to 404) | Medium | Client code cannot distinguish "invalid key" from "license deleted" — this is by design. Accept it; document as expected behavior. |
| Trial marker tampering | Low (best-effort, not DRM) | Documented as a courtesy gate, not enforcement. Server-side activation cap is the real limit. |
| `requests` not directly listed in pyproject dependencies | Medium | Verify it's a guaranteed transitive dep. If not, add to `[project.dependencies]`. |

---

## 8. Model Pressure Management

| Phase | Required Models | Always Unload |
|---|---|---|
| Session A (core package) | qwen3.6:35b, qwen3.8:27b | ornith-1.5:35b, laguna-xs-2.1 |
| Session B (integration) | qwen3.6:35b, qwen3.8:27b | ornith-1.5:35b, laguna-xs-2.1 |
| Review phase | laguna-xs-2.1, qwen3.6:35b | qwen3.8:27b, ornith-1.5:35b |

---

## 9. Notes for Implementer

1. **Do NOT write implementation code yet.** This is a CTO plan (G1). Hand this to the user for approval → G2 assignment to Implementer.
2. **The `identifier` parameter on Keygate SDK endpoints** is the device identity mechanism. There is no separate `device_id` field — use `identifier` for both activation and verification calls.
3. **Oracle hardening means**: If a license key doesn't exist in Keygate, `/verify` returns `404 LICENSE_NOT_FOUND`. Your client code must handle this gracefully (not raise an unhandled HTTP error) — treat it as "no valid license" and fall through to trial logic.
4. **Token TTL is server-controlled** — the `exp` field in the signed token payload tells the client how long it can stay offline before needing to check in. Do NOT hardcode a 7-day value; read from the token.
5. **The existing MEEConfig class should NOT be modified** for licensing concerns. The new `LicensingConfig` in `mee/licensing/config.py` handles all license-related configuration independently via env vars.

---

## 10. Pre-G2 Checklist (CTO)

- [x] Read GATE_C_SPECIFICATION.md in full
- [x] Verify Keygate live instance health and API endpoints
- [x] Document the `identifier` parameter mapping (Keygate's device ID mechanism)
- [x] Document the oracle hardening behavior and its implications for client error handling
- [x] Confirm ed25519 verification is possible with existing `cryptography` dep
- [x] Verify exact line numbers in engine.py for integration points
- [x] Note: Both known license keys returned 404 from live Keygate (test-mode license deleted after testing; manual key may have been deactivated). **Implementer should expect that initial testing will use a fresh activation against Keygate.**
- [ ] **NOT done**: Capturing a real signed token — would require an active MEE license with a valid device activation on the live Keygate instance. Deferring to Implementer or requiring owner to provide one.

---

**G1 COMPLETE. Awaiting user approval before proceeding to G2 (Implementer assignment).**

---

## 11. Extensibility Amendment Notes (Added 2026-10-21 per owner request)

The GATE_C_EXTENSIBILITY_ANALYSIS.md document details five required amendments to the core contracts
(CORE_CONTRACTS.md §7) that transform this from a MEE Pro-only client into a multi-tier-compatible client.

**Amendments A-G are required before G2 implementation begins.** They cover:

1. **VerificationResult dataclass** — LicenseClient.verify() returns rich plan/feature metadata (not bare bool)
2. **TrialConfig class** — trial duration sourced from Keygate plan features → env var → configurable default
3. **Status map extension** — maps Keygate's full lifecycle states (including `suspended`/`revoked` → `"degraded"`)
4. **ACTIVATION_LIMIT error handling** — graceful device-cap enforcement per Keygate plan config
5. **Feature-based behavior** — CRITICAL: never match on plan names; drive all decisions from the `features` map

The extensibility analysis is available at:
`docs/development/reports/TASK_MEE_015/GATE_C_EXTENSIBILITY_ANALYSIS.md`

These amendments are additive — no breaking changes to existing contracts. They can be implemented within Session A (~2-3 hours).

**PLAN_EOF

---

## 11. Extensibility Amendment Notes (Added 2026-10-21 per owner request)

The GATE_C_EXTENSIBILITY_ANALYSIS.md document details five required amendments to the core contracts
(CORE_CONTRACTS.md section 7) that transform this from a MEE Pro-only client into a multi-tier-compatible client.

**Amendments A-G are required before G2 implementation begins.** They cover:

1. **VerificationResult dataclass** - LicenseClient.verify() returns rich plan/feature metadata (not bare bool)
2. **TrialConfig class** - trial duration sourced from Keygate plan features -> env var -> configurable default
3. **Status map extension** - maps Keygate's full lifecycle states (including suspended/revoked to degraded)
4. **ACTIVATION_LIMIT error handling** - graceful device-cap enforcement per Keygate plan config
5. **Feature-based behavior** - CRITICAL: never match on plan names; drive all decisions from the features map

The extensibility analysis is available at:
docs/development/reports/TASK_MEE_015/GATE_C_EXTENSIBILITY_ANALYSIS.md

These amendments are additive - no breaking changes to existing contracts. They can be implemented within Session A (~2-3 hours).
