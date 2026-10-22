# PM_G0_INTAKE — TASK_MEE_019: License Plan Selection & Purchase UI

**Task ID:** TASK_MEE_019
**Gate:** G0 — PM Intake
**Date:** 2026-10-22
**PM:** Shouke Wei (gateway-owner)

---

## Intake Summary

User requests a License UI in the MEE remote demo enabling:
1. View current license status (trialing / licensed / expired).
2. Select one of 5 plans (Community/Academic, Developer, Commercial, Enterprise, OEM/Embedded).
3. Paid plans → Stripe Checkout URL (new tab).
4. Community/Academic → self-service free key request (Keygate admin API, server-side proxy).
5. Activate an existing license key.
6. Deactivate the current license.
7. Document all plans in README + LICENSE.txt.

## Verification Performed (G0)

| Check | Result |
|---|---|
| Registry: next available ID | **TASK_MEE_019** (016=CUDA, 017=Camera, 018=RemoteDemo, 035=Pangolin all taken) |
| Keygate plans (5) | ✅ Verified in Postgres: 1 free (Community/Academic), 4 paid (Developer/Commercial/Enterprise/OEM) |
| Keygate API key | ✅ `kg_live_c603...` scope `licenses:write`, stored at `/home/deepsim/Documents/shouke/workspace/keygate_api.txt` |
| Admin license creation | ✅ `POST /api/v1/admin/licenses` tested → 200 + real license key (cleaned up) |
| Checkout URLs (4) | ✅ All real: `6c5bce2c`, `7d44a91b`, `d09d97da`, `15f2f3d7` |
| Encryption key | ✅ `RELEASE_KEY_ENCRYPTION_KEY` set (2026-10-21) |
| `server.py` HTTP endpoints | ✅ `_http_endpoint` method handles `/healthz`, `/` (page). New license endpoints will be added here. |
| `index.html` license section | ✅ Currently empty — no license UI exists |
| `mee/licensing/` package | ✅ Fully functional from TASK_MEE_015, no changes needed |

## Key Decisions (Owner)

| Decision | Value |
|---|---|
| Community/Academic flow | Self-service via Keygate API (not Stripe $0, not admin-issued) |
| Rate limiting | 1 per email per 24h, 3 per IP per hour |
| Free-request form fields | name (required), email (required), institution (optional) |
| Backend secrets | `KEYGATE_API_KEY` server-side only, never in browser |
| 4 paid plans | Stripe Checkout URLs (public-safe, may be in client code) |
| Existing CLI | `mee-lic` commands remain functional (no changes to `mee/licensing/`) |

## Artifacts Produced

- `TASK_REQUEST.md` — full intake with scope, acceptance criteria, security constraints, dependencies.

## Handoff

**To:** CTO (G1 — architecture review + task plan)
**From:** PM (G0 — intake complete)
