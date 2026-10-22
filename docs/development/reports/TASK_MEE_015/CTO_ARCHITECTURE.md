# CTO Architecture Review — TASK_MEE_015: MEE License Integration (Gate C)

**Task ID:** TASK_MEE_015  
**Date:** 2026-10-21  
**Author:** CTO / Architect 🏗️  
**Phase:** G1 — Architecture Review  

---

## 1. Architecture Assessment

The `GATE_C_SPECIFICATION.md` proposes a clean separation: a new `mee/licensing/` package that operates independently of the core emotion engine, integrating only at `EmotionEngine.process()` via a lazy-loaded `LicenseClient`. This is architecturally sound.

### 1.1 Component Diagram

```
User / MEE Consumer
    │
    ├── EmotionEngine.process() ──→ LicenseClient.verify() (before inference)
    │                                   │
    │                               [cached valid token] → OK (no network)
    │                               [expired/no token] → Keygate API
    │                                                   │
    │                                       Keygate (https://licenses.deepsim.ai:8443)
    │                                          POST /api/v1/license/verify
    │                                          {license_key, identifier}
    │                                         ┌─→ 200: status + ed25519-signed token
    │                                         └─→ 404: LICENSE_NOT_FOUND (oracle-hardened)
    │
    ├── mee-lic CLI (activate/status/deactivate/verify)
    │     └── same Keygate endpoints
    │
    └── Local state ($MEE_HOME/licenses/ + $MEE_HOME/device_id)
         - license key hashes → signed token cache
         - .trial → 14-day trial marker
         - device_id → stable SHA-256 hash
```

### 1.2 Key Architectural Decisions (vs. GATE_C_SPECIFICATION.md proposals)

| Decision | Spec Suggested | CTO Decision | Rationale |
|---|---|---|---|
| Device ID parameter name | `device_id` header or body | **`identifier` JSON body field** | Keygate 0.1.15 API uses `identifier` (not `device_id`) for both activation and verification. Using a different name would require the server to support it — and the spec says CTO decides from Keygate API docs. The docs are clear: `identifier`. |
| Trial key issuance | "client-local vs server-recorded" (CTO decides) | **Client-local** (owner-accepted per G0) | Owner explicitly chose R8/R9 trial model in the spec. No server-side trial license is needed or configured on the MEE product in Keygate. |
| Token TTL handling | CTO to decide | **Read from token's `exp` field** | The TTL is plan-configured (not hardcoded). The signed payload carries `iat` and `exp` as unix timestamps — client must read these, not assume a fixed value. |
| Retry policy in spec R7 | "at most one retry per call" | **Accept as-is** | Consistent with Keygate's brute-force protection (5 failures → 30s lockout). Two retries (original + 1) with 1s exponential base is sufficient for transient network issues. |
| MEEConfig modification | Spec suggested adding license config to MEEConfig | **Separate LicensingConfig** | Adding licensing fields to `MEEConfig` violates SRP — the core engine config should not be polluted with license concerns. The new `LicensingConfig` reads env vars directly. |

### 1.3 Risk Assessment for Architecture

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Token payload format mismatch (base64url encoding detail) | Medium | High — offline verification breaks entirely | Implementer must verify against a real token from Keygate before shipping |
| Oracle hardening confusion | High | Medium — client misinterprets 404 responses | Documented in CTO plan; client treats ALL non-200 from /verify as "no valid license" |
| cryptography 3.4.8 API differences on Python 3.10+ | Low | Medium — verification fails silently | Verified in G1: `Ed25519PublicKey.from_public_bytes()` available ✅ |
| Trial marker tampering by malicious user | Certain (by design) | Low — stated as best-effort, not DRM | Documented; server-side activation cap is the real enforcement mechanism |

---

## 2. Core Contracts

### 2.1 LicenseClient Contract

```python
class LicenseClient:
    def __init__(self, config: LicensingConfig):
        """Initialize with config. No network calls on construction."""
    
    def activate(self, license_key: str, identifier: str) -> dict:
        """POST /api/v1/license/activate {license_key, identifier}.
        Returns parsed response data (success + data fields).
        Raises LicenseClientError on HTTP errors that are not LICENSE_NOT_FOUND."""
    
    def verify(self) -> bool:
        """Check license validity.
        1. If cached token is valid and unexpired → True (no network).
        2. Else → POST /api/v1/license/verify {license_key, identifier}.
           On success → cache new token + public key → True.
           On network error → fall back to offline verification → result.
           Returns False if no valid license found."""
    
    def verify_offline(self) -> bool:
        """Validate cached signed token using cached ed25519 public key.
        Parse base64url(payload).base64url(signature).
        Check iat + exp >= now.
        Returns True if the token is valid and unexpired."""
    
    def status(self) -> dict:
        """Return current license status dict:
        {status: 'licensed'|'trialing'|'expired', 
         remaining_days: int|None,
         offline: bool,
         device_id: str,
         last_verified: str|None}"""
    
    def deactivate(self) -> None:
        """POST /api/v1/license/deactivate {license_key, identifier}.
        Remove local state file. Raises LicenseClientError on failure."""
```

### 2.2 LicensingConfig Contract

```python
@dataclass
class LicensingConfig:
    server_url: str = "https://licenses.deepsim.ai:8443"  # MEE_LICENSE_SERVER or default
    license_key: str | None = None                         # MEE_LICENSE_KEY or None
    device_id: str | None = None                           # MEE_DEVICE_ID or auto-generated
    home_dir: str = "~/.config/mee-licensing/"             # MEE_HOME/licenses/ or default
    
    @property
    def state_dir(self) -> Path: ...                          # resolved $MEE_HOME/licenses/
    @property
    def device_id(self) -> str: ...                           # auto-generated if not set
```

### 2.3 Trial Contract

```python
# trial.py
def write_trial_marker(home_dir: Path) → None:
    """Write .trial with {first_seen: <ISO8601>, expires_at: first_seen + 14 days}.

def is_trial_expired(home_dir: Path) → bool:
    """Read .trial; return True if now > expires_at. Return False if no trial marker."""

def remaining_trial_days(home_dir: Path) → int | None:
    """Return remaining days in trial, or None if not in trial or expired."""
```

### 2.4 EmotionEngine Integration Contract

```python
# EmotionEngine.process() — before inference:
if self._license_client is None:
    self._license_client = LicenseClient(LicensingConfig())

try:
    valid = self._license_client.verify()
except NetworkError:
    # fallback handled inside verify() via offline path
    pass

if not valid:
    from ..licensing.trial import is_trial_expired
    if is_trial_expired():
        raise LicenseExpiredError("Trial expired. Activate a license to continue.")
    raise LicenseExpiredError("License verification failed.")
```

### 2.5 Health() Extension Contract

```python
# EmotionEngine.health() — add to return dict:
license_info = None
if self._license_client is not None:
    st = self._license_client.status()
    license_info = {
        "status": st["status"],           # "licensed" | "trialing" | "expired"
        "remaining_days": st.get("remaining_days"),  # int or None
        "offline": st.get("offline", False),
    }
# Return the dict WITH or WITHOUT license_info depending on whether client exists.
```

---

## 3. Files Not In Scope (Explicitly Excluded)

- **`docs/ARCHITECTURE.md`** — May be updated by PM in G5; not part of CTO plan scope
- **`ARCHITECTURE.md` additions for licensing** — Out of scope; document the module in the task's deliverables, not the system architecture doc
- **Keygate changes** — Gate B is complete; Keygate has `RELEASE_KEY_ENCRYPTION_KEY` set and both licenses encrypted at rest. No Keygate changes needed for Gate C.
- **AI Companion licensing** — Explicitly out of scope per G0 R6

---

## 4. Conclusion

The specification proposes a sound architecture with appropriate separation of concerns. The primary deviation from the spec is:

1. **Using `identifier` (not `device_id`) as the Keygate API parameter name** — mandated by Keygate 0.1.15's OpenAPI spec.
2. **Separate `LicensingConfig` class** instead of modifying `MEEConfig` — prevents core config pollution and respects SRP.

No architectural changes to the spec are rejected. The plan is approved for G2 implementation with the modifications noted above.

**G1: ARCHITECTURE APPROVED.**
