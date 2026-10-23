# MEE Offline License Behaviour (TASK_MEE_020, Decision #5)

**Binding rule C12 (Decision #4, CTO_PLAN §5):** the only permitted
pass-through is **network down + valid offline token → allow**.
Every other failure path **blocks** inference (C2, C10, C11).

This page documents exactly what happens in each scenario so that
field / Jetson deployments know what to expect when connectivity is
unavailable.

---

## 1. The offline mechanism

The licensing client caches a **signed token** (ed25519, from Keygate)
locally. Each token carries:

- `iat` — issued-at (unix timestamp, seconds)
- `exp` — **check-in interval** (seconds), server-set by Keygate

At runtime, `offline.py::_TokenPayload.is_within_ttl()` computes:

```
within_ttl = (iat + exp) >= now
```

`exp` is **not** an absolute expiry — it is the *check-in window*. The
Keygate server sets it during activation/verification. A typical value is
**72 hours** (3 days) to cover reasonable connectivity gaps in field
environments (CTO decision #5 recommends Keygate's default be ≥ 72 h).

---

## 2. Scenario matrix (Decision #5 / C12)

| # | License state | Network | `verify()` result | Inference |
|---|---------------|---------|-------------------|-----------|
| V1 | Valid (active) | Online  | **valid** (online) | ✅ Allowed |
| V2 | Valid (cached token within TTL) | **Down** | **valid** (offline, C12) | ✅ **Allowed** (only pass-through) |
| V3 | Token expired (TTL elapsed) | Down | **invalid** | ❌ **Blocked** |
| V4 | Invalid lifecycle (revoked/suspended/past_due/canceled/expired) | Online | **invalid** | ❌ **Blocked** (R42) |
| V5 | No license key at all | any | trial evaluation | per trial rules |

These are covered by `tests/test_licensing_offline_matrix.py`:
- V1 → `test_valid_license_online_verify`
- V2 → `test_valid_license_offline_allow`
- V3 → `test_expired_token_offline_blocks`
- V4 → `test_invalid_status_online_blocks`

---

## 3. What the customer should expect

### Network is down + token is valid
- `process()` proceeds normally.
- No network call is made (the cached signed token is used).
- This is the **intended** offline operation mode (C8: preserve
  reasonable offline operation for Jetson/field).

### Network is down + token is expired
- `process()` raises `LicenseExpiredError` — **inference is blocked**.
- The customer must reconnect and re-verify to obtain a fresh token.

### Network is down + no valid license at all
- Trial evaluation applies (if a trial is active, it is allowed until it
  expires; otherwise blocked).

---

## 4. Re-verification when connectivity returns

When the device reconnects, the customer (or an automated job) can force a
fresh verification:

```bash
mee-lic verify            # CLI — re-verify against Keygate
```

or in code:

```python
from mee.api import LicenseClient, LicensingConfig
client = LicenseClient(LicensingConfig())
result = client.verify(force_network=True)
print(result.valid, result.license_status)
```

A successful re-verification refreshes the cached token (new `iat`/`exp`),
extending the offline window.

---

## 5. Keygate configuration note (out of MEE scope)

The `exp` check-in interval is **server-set by Keygate**, not by MEE code.
To adjust the offline grace window, change the Keygate product/plan
configuration on the server (see the open item in
`G2_IMPLEMENTATION.md` §7). MEE client code does **not** hard-code a grace
window — it honours whatever `exp` Keygate issues.

---

## 6. Interaction with the integrity check

The integrity self-check (`mee/licensing/integrity.py`) is independent of
offline licensing:

- It verifies the **integrity of the installed files** (tamper detection).
- It runs **before** license verification in the gate.
- If it blocks (C10/C11), inference is blocked **regardless** of offline
  token state — integrity is a precondition for any license path.
- The offline pass-through (C12) applies to the *license* path only, after
  integrity has passed.
