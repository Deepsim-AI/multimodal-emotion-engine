# Core Contracts — TASK_MEE_015: MEE License Integration (Gate C)

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Author:** CTO / Architect 🏗️  
**Phase:** G1  

---

This document defines the frozen contracts between the new `mee/licensing/` package and existing MEE components. These contracts must not be violated by the Implementer during G2.

## 1. EmotionEngine ↔ LicenseClient Integration Contract

### 1.1 Process Flow (MUTABLE — per CTO plan)

```
EmotionEngine.process()
  │
  ├─ if self._license_client is None:
  │     self._license_client = LicenseClient(LicensingConfig())
  │
  ├─ valid = self._license_client.verify()
  │     │
  │     ├─ cached token valid (iat + exp >= now): → True (no network) [R4]
  │     ├─ cached token expired: POST /verify → success → cache + True
  │     └─ POST /verify fails (network error): 
  │           verify_offline() → cached offline check → result
  │
  ├─ if not valid:
  │     if is_trial_expired():
  │         raise LicenseExpiredError("Trial expired.")  [R10]
  │     raise LicenseExpiredError("License verification failed.")
  │
  └─ proceed with inference...
```

**Constraint**: `EmotionEngine.__init__` must NOT call any license code. Lazy initialization on first `process()` call.

### 1.2 Health() Extension (ADDITIVE ONLY)

The `health()` return dict gains an optional `license` key:

```python
{
    "status": "ready" | "degraded" | "unavailable",
    "detail": "...",
    "license": {                       # NEW — only if license_client initialized
        "status": "licensed" | "trialing" | "expired",  # R13
        "remaining_days": int | None,   # R13
        "offline": bool                 # R13
    }
}
```

**Constraint**: If `self._license_client is None`, omit the `license` key entirely (do not include `"license": null`). This preserves backward compatibility for code that checks `health().get("status")`.

### 1.3 Exception Contract

```python
# mee/licensing/errors.py
class LicenseExpiredError(Exception):        # R15 — raised from process()
    pass

class LicenseClientError(Exception):          # R1 — base class for client errors
    pass
```

**Constraint**: `LicenseExpiredError` must be importable via `from mee.api.license import LicenseExpiredError` (through the re-export in `mee/api/__init__.py`). It must NOT require importing from `mee/licensing/`.

### 1.4 Public API Contract

```python
# mee/api/license.py (or exported directly from mee/api/__init__.py)
def license_status() -> dict:
    """Return current license status for MEE.
    
    Thin wrapper over LicenseClient.status().
    Returns same shape as EmotionEngine.health()["license"].
    """
```

**Constraint**: `license_status()` must never raise — return a sensible default dict if no license client is configured or if an error occurs during retrieval.

### 1.5 CLI Contract (mee-lic)

| Command | Subcommand | Behavior | Stdout Format |
|---|---|---|---|
| `mee-lic` | — | Show help, version | Text |
| `mee-lic activate <key>` | activate | POST /api/v1/license/activate + cache result | "Activated. Status: licensed" + JSON status block |
| `mee-lic status` | status | Read local state + cached token info | Pretty-printed JSON with: status, remaining_days, device_id, last_verified |
| `mee-lic deactivate` | deactivate | POST /api/v1/license/deactivate + remove local state | "Deactivated." |
| `mee-lic verify` | verify | Force network verification (bypass cache) | Same as status after update |

**Constraint**: CLI uses argparse (stdlib only — no new dependencies). Exit code 0 on success, non-zero on failure. No license key or device ID in log output.

## 2. LicensingConfig Contract

```python
@dataclass(frozen=False)
class LicensingConfig:
    """Configuration for MEE license integration."""
    
    server_url: str = "https://licenses.deepsim.ai:8443"
        # Env: MEE_LICENSE_SERVER (default above)
    
    license_key: str | None = None
        # Env: MEE_LICENSE_KEY (optional — if set, auto-activate on first verify)
    
    device_id: str | None = None
        # Env: MEE_DEVICE_ID (optional — overrides auto-generation)
        # If unset: sha256(machine_id + boot_uuid)[:16] hex string
    
    home_dir: Path | None = None
        # Env: MEE_HOME /home dir for license state
        # Default: ~/.config/mee-licensing/
        # State files: $MEE_HOME/licenses/*.json (key_hash.json)
    
    @property
    def state_dir(self) -> Path:
        """Return the licenses/ subdirectory, creating if needed."""
        ...
    
    @device_id.setter
    def device_id(self, value: str):
        """Setter to update device_id after auto-generation."""
        ...
```

## 3. Keygate API Client Contract (Internal)

All internal HTTP methods MUST use `requests` with a **5-second timeout** (R7). No custom timeout config.

| Method | Endpoint | Body | Success Response | Failure Handling |
|---|---|---|---|---|
| `activate()` | `POST /api/v1/license/activate` | `{license_key, identifier}` | `{success: true, data: {...}}` | 404 → no valid license; other non-2xx → raise LicenseClientError |
| `verify()` | `POST /api/v1/license/verify` | `{license_key, identifier}` | `{success: true, data: {status, token, ...}}` | 404 → return False (oracle-hardened); network error → offline fallback |
| `deactivate()` | `POST /api/v1/license/deactivate` | `{license_key, identifier}` | `{success: true}` or `{success: false}` (still ok) | Non-2xx → raise LicenseClientError |

**Constraint**: All failures from `/verify` that are not network errors return Python `False` (not exceptions), because Keygate's oracle hardening collapses all license-knowable failures to a single 404. The caller determines meaning via the success response vs. False return.

## 4. Offline Verification Contract

```python
def verify_signed_token(cached_token: str, cached_public_key_hex: str) -> bool:
    """Verify an ed25519-signed token using a cached public key.
    
    Steps:
    1. Split token on '.' → [payload_b64url, signature_b64url]
    2. base64url-decode payload_b64url → bytes (this is the SIGNED DATA)
    3. base64url-decode signature_b64url → bytes
    4. Decode cached_public_key_hex → Ed25519PublicKey.from_public_bytes(hex_bytes)
    5. pubkey.verify(signature, signed_data) → True if valid
    
    Token payload structure (JSON):
      {lid, pid, pln, sts, did, fpr, ftr, iat, exp, vun?, upd?, grc?, nce}
    
    Returns True if signature is valid AND token not expired (iat + exp >= now).
    """
```

**Constraint**: base64url encoding uses NO padding (`+` → `-`, `/` → `_`, no trailing `=`). Use `base64.urlsafe_b64decode()` in Python.

## 5. Trial Contract

```python
# trial.py — file format for .trial:
# {
#   "first_seen": "2026-10-21T18:30:00Z",
#   "expires_at": "2026-11-04T18:30:00Z"
# }

def write_trial_marker(state_dir: Path) → None:
    """Write trial marker with first_seen = now, expires_at = now + 14 days.
    State: create state_dir if needed."""

def is_trial_expired(state_dir: Path) → bool:
    """Read .trial from state_dir; return True if now > expires_at or file missing.
    Returns False if trial marker exists and not expired."""

def remaining_trial_days(state_dir: Path) → int | None:
    """Return remaining days (ceil of fractional days) if in trial, else None."""
```

## 6. Frozen Files (No Changes Allowed During G2)

The following files must NOT be modified during G2 implementation (beyond what the CTO plan explicitly authorizes):

| File | Constraint | Reason |
|---|---|---|
| `mee/fusion/emotion_fusion.py` | 0-line diff | Fusion logic untouched by licensing |
| `mee/state/history.py` | 0-line diff | State management untouched |
| `mee/state/estimator.py` | 0-line diff | Trend estimation untouched |
| `mee/vision/processor.py` | 0-line diff | Vision pipeline untouched |
| `mee/voice/*.py` | 0-line diff | Voice pipeline untouched |
| `tests/test_fusion.py` | 0-line diff | Fusion tests untouched |
| `tests/test_vision.py` | 0-line diff | Vision tests untouched |
| `tests/test_voice.py` | 0-line diff | Voice tests untouched |
| `mee/api/engine.py` | Only: license integration seams (see CTO §3) | Core engine contract preserved |

---

**These contracts are FROZEN at G1. Changes require CTO re-approval via an amended plan.**

---

## 7. GATE C EXTENSIBILITY AMENDMENTS (Required by CTO — G1 amendment)

These amendments are **required** for G2 implementation. They transform the design from a MEE Pro-only client into a multi-tier-compatible client that respects Keygate's per-plan feature map.

### 7.1 Amendment A: VerificationResult Dataclass

```python
@dataclass
class VerificationResult:
    """Rich result of LicenseClient.verify() — replaces bare bool."""
    valid: bool
    license_status: str | None        # Keygate status: active, trialing, suspended, etc.
    plan_id: str | None               # Keygate plan UUID
    plan_name: str | None             # Keygate plan name (e.g., "Pro", "Developer", "Enterprise")
    features: dict | None             # Keygate entitlements map — forward-compatible with unknown keys
    offline: bool                     # Was verification done offline?
    last_verified_at: float | None    # Unix timestamp of last successful verification

def verify(self) -> VerificationResult: ...  # replaces the old bool return
```

### 7.2 Amendment B: TrialConfig — Externalized Duration

```python
@dataclass(frozen=False)
class TrialConfig:
    """Trial configuration — defaults are configurable, not assumptions."""
    
    trial_days: int = 14           # Default 14 days
    _trial_enabled_default: bool = True
    
    def get_trial_days(self, plan_name: str | None = None, features: dict | None = None) -> int:
        """Resolve trial duration with server-side override.
        
        Priority: Keygate plan feature → MEE_TRIAL_DAYS env → default (14 days).
        """
        # 1. Server-provided trial period
        if features and "trial_period_days" in features:
            try:
                return int(features["trial_period_days"])
            except (ValueError, TypeError):
                pass
        
        # 2. Environment override
        env_val = os.environ.get("MEE_TRIAL_DAYS")
        if env_val:
            return int(env_val)
        
        # 3. Default
        return self.trial_days
    
    def can_trial(self, features: dict | None = None) -> bool:
        """Check if this plan allows a trial.
        
        Some plans (Enterprise, OEM) may disable trials via feature flag.
        """
        if features and "trial_enabled" in features:
            return bool(features["trial_enabled"])
        return self._trial_enabled_default
```

### 7.3 Amendment C: LicensingConfig.status() Return Value Extension

```python
# Updated status() return dict (replaces the current spec):
{
    "status": str,                 # "licensed" | "trialing" | "expired" | "degraded" | other
    "plan_id": str | None,         # NEW — from Keygate plan_id
    "plan_name": str | None,       # NEW — from Keygate plan_name
    "remaining_days": int | None,  # existing
    "offline": bool,               # existing
    "features": dict | None,       # NEW — Keygate entitlements map
}

# Status mapping (forward-compatible):
STATUS_MAP = {
    "active": "licensed",
    "trialing": "trialing",
    "past_due": "expired",       # treat past_due same as expired for MEE (no payment processing)
    "canceled": "expired",
    "expired": "expired",
    "suspended": "degraded",     # NEW — distinct from expired
    "revoked": "degraded",       # NEW — distinct from expired
}
# Any unmapped status → use as-is (forward-compatible)
```

### 7.4 Amendment D: ACTIVATION_LIMIT Error Handling

```python
# New exception class in errors.py:
class ActivationLimitError(LicenseClientError):
    """Raised when Keygate rejects activation due to max_activations cap."""
    def __init__(self, message: str = "Device activation limit reached. Contact support.",
                 limit_hit: bool = True):
        super().__init__(message)
        self.limit_hit = limit_hit

# LicenseClient.activate() must handle Keygate's ACTIVATION_LIMIT error code:
def activate(self, license_key: str, device_id: str) -> VerificationResult:
    try:
        response = self.http.post(...)
        return self._parse_activation_response(response)
    except KeygateHTTPError as e:
        if e.code == "ACTIVATION_LIMIT":
            raise ActivationLimitError()
        raise  # Other errors propagate normally
```

### 7.5 Amendment E: Health() License Block Extension

```python
# Updated EmotionEngine.health() license block (extends existing spec):
{
    "status": str,                 # per STATUS_MAP above
    "plan_id": str | None,         # NEW
    "plan_name": str | None,       # NEW
    "remaining_days": int | None,  # existing
    "offline": bool,               # existing  
    "features": dict | None,       # NEW
}
```

### 7.6 Amendment F: Feature-Based Behavior (No Plan Name Hardcoding)

**CRITICAL CONSTRAINT for Implementer:** The MEE client MUST NEVER hardcode or match on plan names (e.g., `if plan_name == "Pro"`). All behavioral decisions must be driven by the **features map**:

```python
# CORRECT — feature-based:
has_api_access = features.get("api_access", {}).get("enabled", False)
can_fusion = features.get("fusion_enabled", {}).get("enabled", True)

# WRONG — name-based (DO NOT DO THIS):
if plan_name == "Enterprise":
    # ...
elif plan_name == "Developer":
    # ...
```

### 7.7 Amendment G: CLI Status Output Extension

The `mee-lic status` output must include new fields from VerificationResult:
- `plan_id` (truncated UUID, e.g., `a1b2c3d4...`)
- `plan_name`
- `features` summary (count of feature keys + notable enabled features)
- All existing fields remain unchanged

---

**These amendments are incorporated into the frozen contracts by CTO G1 amendment.**
