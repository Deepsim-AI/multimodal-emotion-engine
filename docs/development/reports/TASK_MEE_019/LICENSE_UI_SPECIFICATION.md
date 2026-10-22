# LICENSE_UI_SPECIFICATION — TASK_MEE_019 Extended Spec

**Task ID:** TASK_MEE_019  
**Date:** 2026-10-22  
**Derived from:** CTO_PLAN.md + PM_G0_INTAKE.md

---

## 1. API Contract

### GET /license/status
```
Response 200:
{
  "status": "trialing" | "licensed" | "expired",
  "plan_id": null | "a2064f10-..." | "...",
  "plan_name": null | "Community / Academic" | "Developer" | ...,
  "remaining_days": 14 | null,
  "offline": false,
  "device_id": "xxx"
}
```

### POST /license/activate
```
Request: {"key": "KG-XXXXX..."}
Response 200: {"valid": true, "status": "licensed", "plan_name": "Developer", "message": "activated"}
Response 400: {"valid": false, "message": "missing 'key' field"}
Response 500: {"valid": false, "message": "error details"}
```

### POST /license/deactivate
```
Request: {}
Response 200: {"status": "deactivated", "message": "license deactivated"}
Response 500: {"status": "error", "message": "error details"}
```

### POST /license/request-community
```
Request: {"name": "John Doe", "email": "john@university.edu", "institution": "MIT (optional)"}
Response 200: {"license_key": "KG-...", "status": "trialing", "message": "free license issued"}
Response 400: {"error": "name is required"} / {"error": "email format invalid"}
Response 429: {"retry_after": 1800, "message": "too many requests — try again later"}
Response 500: {"error": "Keygate API error details"}
```

---

## 2. Plan Configuration (from Keygate)

| Plan Slug | Name | Type | Checkout URL | Plan ID |
|-----------|------|------|-------------|---------|
| community-academic | Community / Academic | Free | — | a2064f10-4deb-4eda-a8a7-5bf05aeac7a7 |
| developer | Developer | Paid | https://licenses.deepsim.ai:8443/pay/6c5bce2c | — |
| commercial | Commercial | Paid | https://licenses.deepsim.ai:8443/pay/7d44a91b | — |
| enterprise | Enterprise | Paid | https://licenses.deepsim.ai:8443/pay/d09d97da | — |
| oem-embedded | OEM / Embedded | Paid | https://licenses.deepsim.ai:8443/pay/15f2f3d7 | — |

---

## 3. Rate Limiting Policy

| Scope | Limit | Window |
|-------|-------|--------|
| Per email | 1 request | 24 hours |
| Per IP | 3 requests | 1 hour |

Exceeded → HTTP 429 with `retry_after` seconds in response body.

---

## 4. UI Layout

```
┌─────────────────────────────────────┐
│  License                            │
├─────────────────────────────────────┤
│  ● licensed · Developer             │
│     Device: abc123                  │
│     [Deactivate]                    │
├─────────────────────────────────────┤
│  Select a License Plan              │
│                                     │
│  ┌──────┐ ┌──────┐ ┌──────┐        │
│  │Free  │ │Paid  │ │Paid  │ ...     │
│  │Comm  │ │Dev   │ │Comm. │         │
│  │Acad  │ │      │ │      │         │
│  │[Sel] │ │[Sel] │ │[Sel] │         │
│  └──────┘ └──────┘ └──────┘        │
├─────────────────────────────────────┤
│  Activate Existing Key              │
│  [Key__________________] [Activate] │
└─────────────────────────────────────┘
```
