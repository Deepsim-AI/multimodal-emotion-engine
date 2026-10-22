# Gate C Extensibility Analysis — TASK_MEE_015

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Author:** CTO / Architect 🏗️  

This analysis addresses two requirements from the owner:
1. Verify that the licensing system supports **extensible license types** (Developer, Enterprise, OEM).
2. Ensure the 14-day trial and three-device limit are **configurable policies**, not assumptions baked into logic.

---

## 1. License Type Extensibility Assessment

### 1.1 Keygate's Built-in Extensibility Mechanism

Keygate v0.1.15 provides a built-in extensibility mechanism for license types: **the `features` entitlements map**. Per the OpenAPI spec, every `/verify` response includes:

```json
{
  "success": true,
  "data": {
    "status": "active",
    "plan_id": "string",           // uniquely identifies the plan
    "plan_name": "string",          // human-readable (e.g., "Pro", "Developer", "Enterprise")
    "valid_until": "2027-10-01T00:00:00Z" | null,
    "updates_until": "..." | null,
    "features": {                  // ← THE EXTENSIBILITY MECHANISM
      "premium_support": true,
      "api_calls": "50000",
      "storage_gb": "100"
    },
    "token": "<signed-token>"
  }
}
```

Features have structured values: `{enabled: bool, value_type: "bool"|"int"|"string"|"quota"|"flag", value: string, used?: int, limit?: int}`.

Additionally, `/license/entitlements` can query features individually or all at once.

### 1.2 What Extends a License Type on Keygate's Side?

Keygate plans are **server-configured**. Each plan has:
- `plan_id` (unique identifier)
- `plan_name` (display name)
- `features` map (entitlements)
- `max_activations` (device limit)
- `token_ttl_days` (offline check-in interval)
- `floating_timeout` (for floating session plans, default 30 min)

**These are Keygate server-side configuration**, not client code. A new license type (e.g., "Enterprise") is created by:
1. Creating a new plan in Keygate's admin dashboard with its own set of features + limits
2. Assigning licenses to that plan via the Keygate portal or API

**No client code changes required on MEE side for each new keytype.**

### 1.3 What Extends a License Type on the MEE Client Side?

The GATE_C specification defines status values returned by the server:
- `active`, `trialing`, `past_due`, `canceled`, `expired`, `suspended`, `revoked`

These are **server-enforced lifecycle states**, not client-side assumptions. The client merely reads and acts on them.

The `plan_name` from Keygate's response provides the license type name. MEE's client code should **never hardcode plan names or types**. Instead, it should:
1. Read `plan_id` + `plan_name` from the verified token/response
2. Use the `features` map to determine what capabilities are available
3. Report `status` and `remaining_days` generically (not type-specific)

### 1.4 Current GATE_C Spec: Does It Support This?

**Verdict: Partially — requires CTO amendments.** The current spec's MEEConfig/LicensingConfig does NOT capture or expose `plan_id`, `plan_name`, or `features` from Keygate responses. This is a gap the Implementer must address.

#### Required Amendment to LicensingConfig.status() return value:

```python
# Current spec (incomplete):
{
    "status": "licensed" | "trialing" | "expired",
    "remaining_days": int | None,
    "offline": bool,
}

# Required amendment — include Keygate's plan data:
{
    "status": "licensed" | "trialing" | "expired" | "degraded",  # add degraded for suspended/revoked
    "plan_id": str | None,          # NEW
    "plan_name": str | None,        # NEW
    "remaining_days": int | None,
    "offline": bool,
    "features": dict | None,         # NEW — Keygate features map (if available)
}
```

#### Required Amendment to LicenseClient.verify() return value:

The `verify()` method currently returns a bare `bool`. This must change to also expose plan data for downstream consumers:

```python
# Current spec:
def verify(self) -> bool: ...

# Required amendment:
@dataclass
class VerificationResult:
    valid: bool
    license_status: str | None        # from Keygate: active, trialing, etc.
    plan_id: str | None
    plan_name: str | None
    features: dict | None             # entitlements map
    offline: bool
    last_verified_at: float | None

def verify(self) -> VerificationResult: ...
```

#### Required Amendment to EmotionEngine.health() license block:

```python
# Current spec is adequate — it just reports status/remaining_days.
# But if we add plan_name and features, health() should include them too:
{
    "status": "licensed" | "trialing" | "expired" | "degraded",
    "plan_id": str | None,
    "plan_name": str | None,
    "remaining_days": int | None,
    "offline": bool,
    "features": dict | None,
}
```

### 1.5 OEM / Enterprise Deviations from MEE Pro

Per Keygate's architecture, each license type gets its own plan with independent:
- `features` map (e.g., `"api_access": true` for Enterprise but not Developer)
- `max_activations` (e.g., 3 for Pro, unlimited for Enterprise — though we must verify this)
- `token_ttl_days` (different check-in cadences per plan)

**Client-side impact**: None. The client reads whatever Keygate sends in the `features` map and respects `plan_name`. The device limit comes from Keygate's server-side enforcement, not client code.

### 1.6 Risks to License Type Extensibility

| Risk | Assessment | Mitigation |
|---|---|---|
| Client hardcodes plan names | **HIGH** if spec is implemented as written | Amendment required: never match on plan_name string; use `features` map keys |
| Status enum doesn't cover new lifecycle states | Medium (Keygate may add more) | Accept any non-enum value from server; fall back to "other" status |
| Features schema changes over time | LOW (JSON map is additive) | Client must be forward-compatible with unknown feature keys |

---

## 2. Trial and Device Limit Configurability Assessment

### 2.1 14-Day Trial: Technical Default vs Hardcoded Assumption

#### Current GATE_C Spec Analysis

**R8 (trial marker):** Writes `.trial` with `expires_at = first_seen + 14 days`.  
**R9 (trial behavior):** Allows process() if trial not expired, logs warning.  
**R10 (trial expiry):** Raises `LicenseExpiredError` if trial expired and no license.

These requirements **specify a hardcoded 14-day window in the spec text**. Whether this is configurable depends on implementation:

#### Required Amendment — TrialConfig as a Separate Configurable Module

The trial duration must NOT be hardcoded in `trial.py`. Instead, it should be sourced from:

```python
# Priority order for trial_days:
# 1. MEE_TRIAL_DAYS env var (override)
# 2. LicensingConfig.trial_days default (configuration)
# 3. Keygate server-provided value (if the plan includes a "trial_period_days" feature)
# 4. System default (14 days as technical baseline)

@dataclass(frozen=False)
class TrialConfig:
    """Trial configuration — defaults are configurable, not assumptions."""
    
    trial_days: int = 14               # MEE_TRIAL_DAYS env var override
    
    def get_trial_days(self, plan_name: str | None = None, features: dict | None = None) -> int:
        """Resolve trial duration with server-side override.
        
        If the plan's features include 'trial_period_days', use that value
        (Keygate can configure this per-plan). Otherwise fall back to
        self.trial_days.
        """
        if features and "trial_period_days" in features:
            try:
                return int(features["trial_period_days"])
            except (ValueError, TypeError):
                pass
        
        # Fallback to env override
        env_val = os.environ.get("MEE_TRIAL_DAYS")
        if env_val:
            return int(env_val)
        
        return self.trial_days  # default 14 days
```

**This makes the 14-day value a configurable technical default, not a hard limit.** If an Enterprise agreement requires a 30-day trial, it's set via plan features in Keygate or `MEE_TRIAL_DAYS` env var — no code changes needed.

#### Trial Policy Enum for Future Flexibility

For future Developer/Enterprise/OEM tiers with potentially different trial behaviors (some may have no trial at all), the trial logic should check whether a trial is allowed:

```python
def can_trial(self, features: dict | None = None) -> bool:
    """Check if this license type allows a trial.
    
    Some plans (e.g., Enterprise, OEM) may not offer trials.
    If 'trial_enabled' feature exists and is False, no trial is allowed.
    """
    if features and "trial_enabled" in features:
        return bool(features["trial_enabled"])
    # Default: trials are always allowed for this product (backward compat)
    return True
```

### 2.2 Three-Device Limit: Technical Default vs Hardcoded Assumption

#### Current GATE_C Spec Analysis

**R3:** `LicenseClient` state stored at `$MEE_HOME/licenses/`. No device limit enforcement on the client.  
**R16-R18:** Device ID generation is stable (SHA-256).  
**Keygate R-0:** Server-side activation cap (`max_activations=3`) is the authority.

**Good news:** The spec already states correctly: **"No client-side device-limit enforcement."** This is architecturally sound.

The three-device limit comes from Keygate's `max_activations` plan property, which is enforced server-side during `/activate`. If a user hits the cap, Keygate returns `ACTIVATION_LIMIT` and the client must handle that gracefully (show an error message; do not silently reduce device ID).

#### Server-Side Source of Truth — Verification Required

The current MEE product in Keygate has `max_activations=3`. For future plans:
- Developer plan could have a different cap (e.g., 5 devices)
- Enterprise plan could have unlimited activations
- OEM license might have no device limit at all

**Client-side impact**: None. The client never reads or enforces `max_activations` — it is purely server-side. The only client-visible effect is: if activation fails with `ACTIVATION_LIMIT`, the client reports this as "device limit reached" to the user and directs them to Keygate portal.

#### Required Amendment — Handle ACTIVATION_LIMIT Gracefully

The current spec's R1 (`LicenseClient.activate()`) does not specify handling of the `ACTIVATION_LIMIT` error code. This must be added:

```python
# LicenseClient.activate() error handling extension:
def activate(self, license_key: str, device_id: str) -> VerificationResult:
    try:
        response = self.http.post(f"{self.server_url}/api/v1/license/activate", ...)
        # Success → parse and cache token + features
    except KeygateError as e:
        if e.code == "ACTIVATION_LIMIT":
            # This is a policy error, not a client bug. Report to user.
            raise LicenseActivatedError("Device activation limit reached. "
                                        "Contact support to free a device slot.",
                                        limit_hit=True)
        else:
            raise  # Other errors propagate normally
```

### 2.3 Configurability Summary Matrix

| Policy | Source of Truth | Configurable? | How to Change | Code Change Required? |
|---|---|---|---|---|
| **Trial duration** | Keygate plan `features.trial_period_days` → env `MEE_TRIAL_DAYS` → default 14 days | ✅ Yes (3 levels) | Set plan feature, or set env var, or change default | YES — must implement in G2 (not in current spec) |
| **Trial allowed?** | Keygate plan `features.trial_enabled` → always-true default | ✅ Yes | Set plan feature to false | YES — must add check in G2 |
| **Device limit** | Keygate plan `max_activations` | ✅ Yes (server-side only) | Change plan config in Keygate admin | NO — server-only enforcement |
| **Check-in TTL** | Keygate plan `token_ttl_days` → from signed token `exp` field | ✅ Yes (server-side only) | Change plan config in Keygate admin | NO — client reads from token |
| **License server URL** | `MEE_LICENSE_SERVER` env var → hardcoded default | ✅ Yes | Set env var | YES — already in spec via LicensingConfig |

---

## 3. Required CTO Plan Amendments

The following items must be added to the G2 implementation plan (session A) before implementation begins:

### Amendment 1: LicensingConfig.status() Return Value Extension
- Add `plan_id`, `plan_name`, `features` to the return dict
- These come from Keygate's `/verify` response `data` field
- Must be forward-compatible with unknown feature keys

### Amendment 2: LicenseClient.verify() → VerificationResult Dataclass
- Change return type from `bool` to a rich dataclass
- Includes all Keygate-provided metadata (status, plan info, features)
- Enables downstream code to make decisions based on license type

### Amendment 3: TrialConfig — Externalized Duration
- Add `TrialConfig` class with configurable `trial_days` default
- Priority: Keygate plan feature → env var → hardcoded default (14 days)
- Add `can_trial()` method to check if trial is allowed for this plan

### Amendment 4: ACTIVATION_LIMIT Error Handling
- Add graceful handling of `ACTIVATION_LIMIT` in `LicenseClient.activate()`
- Raise a new exception class that includes `limit_hit=True` flag
- CLI must display "device limit reached" with instructions

### Amendment 5: Status Mapping Extension
- Extend status mapping to handle future Keygate lifecycle states:
  - Map `active` → `"licensed"` (current behavior)
  - Map `suspended`, `revoked` → `"degraded"` (new — distinct from expired)
  - Accept any unmapped status as a string literal (forward-compatible)

---

## 4. Conclusion

### Extensibility Verdict: **CONDITIONALLY SUPPORTED**

The Keygate server provides the extensibility mechanism (plans + features map). The MEE client GATE_C spec, as written, is **insufficiently general** for multi-tier licensing. It treats every license as "Pro" with a fixed 14-day trial and no awareness of plan-level feature differences.

**The required amendments above transform the current design from a Pro-only client into a multi-tier-compatible client.** The key principle: the MEE client never asserts what type of license it has — it reads Keygate's `features` map and adapts behavior accordingly.

### Configurability Verdict: **PARTIALLY SUPPORTED**

- Device limit: ✅ Server-side only (no client code needed)
- Token TTL: ✅ Server-controlled (read from signed token)
- Trial duration: ❌ Hardcoded 14 days in spec — requires amendment
- Trial enabled/disabled: ❌ Not addressed in spec — requires new feature flag check
- License server URL: ✅ Env-var configurable

### G2 Impact

Amendments 1-5 are all additive (no breaking changes to existing contracts). They can be implemented within Session A of the current two-session plan, adding ~2-3 hours of work. The Implementer should implement them alongside the core package (not as a separate session).

**These amendments are required before G2 implementation begins.** The spec must be updated in the task directory; the CTO has authorized these changes.
