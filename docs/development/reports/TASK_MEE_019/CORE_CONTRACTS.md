# CORE_CONTRACTS — TASK_MEE_019 License UI Contracts

**Task ID:** TASK_MEE_019  
**Date:** 2026-10-22

---

## 1. API Contracts (immutable once shipped)

### GET /license/status
- **Auth:** None required
- **Returns:** `{status, plan_id, plan_name, remaining_days, offline, device_id}`
- **Never raises:** Always returns valid JSON, even on error
- **Cache-Control:** no-store

### POST /license/activate
- **Auth:** None (uses public Keygate endpoint)
- **Request body:** `{key: string}` — the license key to activate
- **Returns:** `{valid: bool, status: string, plan_name: string|null, message: string}`
- **Error responses:** 400 (missing key), 500 (Keygate error)

### POST /license/deactivate
- **Auth:** None (reads local state to find current key)
- **Request body:** `{}` — empty or absent
- **Returns:** `{status: "deactivated" | "error", message: string}`
- **Note:** Removes all local license state; device returns to trial evaluation

### POST /license/request-community
- **Auth:** Requires server-side KEYGATE_API_KEY (admin scope)
- **Request body:** `{name: string, email: string, institution?: string}`
- **Returns:** `{license_key: string|null, status: string, message: string}`
- **Rate limited:** 1/email/24h + 3/IP/hour → 429 when exceeded

---

## 2. Client Contracts

### JavaScript Constants (must stay in sync with Keygate)
```javascript
// File: mee/remotedemo/index.html
const PLANS = { /* ... */ };
```

### CSS Classes Added
- `.license-card` — status display container
- `.plan-grid` — 5-plan layout grid  
- `.plan-card` — individual plan selection card
- `.plan-badge-free`, `.plan-badge-paid` — plan type indicator
- `#licenseSection` — root license UI element

---

## 3. Security Contracts

| Contract | Enforced By | How |
|----------|------------|-----|
| KEYGATE_API_KEY never in browser | server.py | Read from env, used only in POST proxy |
| No hardcoded secrets | index.html | All JS constants are public URLs only |
| Rate limiting on free requests | CommunityRequestRateLimiter | In-memory TTL-based counters |
| Email format validation | Request handler before Keygate call | Regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| Name length check (min 2 chars) | Request handler | String length check |
