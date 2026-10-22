# TASK_REQUEST — TASK_MEE_019: License Plan Selection & Purchase UI

**Task ID:** TASK_MEE_019
**Gate:** G0 — PM Intake
**Phase:** License UX (post-015)
**Date:** 2026-10-22
**Requested By:** Gateway Owner (Shouke Wei)
**Depends On:** TASK_MEE_015 (Gate C — License Integration, CLOSED)

---

## 1. Objective

Enable remote-demo users to:

1. **See their current license status** (trialing / licensed / expired, days remaining, plan name, offline state).
2. **Select a license plan** from five options (Community/Academic, Developer, Commercial, Enterprise, OEM/Embedded).
3. **Follow the correct purchase or free-request flow** per plan:
   - Paid plans → Stripe Checkout URL (opens in new tab).
   - Community/Academic → self-service free key request via Keygate admin API (server-side proxy, no card required).
4. **Activate an existing license key** (paste key → call engine verify → show result).
5. **Deactivate** the current license (safety: shown only when licensed).
6. **Document** all five plans and the purchase/activation flow in the README and licensing docs.

---

## 2. Keygate Plan Configuration (verified 2026-10-22)

| Plan | Slug | Stripe Price ID | Checkout URL | Max Activations | Billing |
|---|---|---|---|---|---|
| Community/Academic | `community-academic` | (none — free) | — | 1 | none |
| Developer | `developer` | `price_1UTM6HC0UMgquCywGgJKCTRU` | `https://licenses.deepsim.ai:8443/pay/6c5bce2c` | 3 | yearly |
| Commercial | `commercial` | `price_1UTMDIC0UMgquCywEe3Tlmbg` | `https://licenses.deepsim.ai:8443/pay/7d44a91b` | 3 | yearly |
| Enterprise | `enterprise` | `price_1UTMJfC0UMgquCywNBvdLCat` | `https://licenses.deepsim.ai:8443/pay/d09d97da` | 5 | yearly |
| OEM/Embedded | `oem-embedded` | `price_1UTMOYC0UMgquCywXu72uJwq` | `https://licenses.deepsim.ai:8443/pay/15f2f3d7` | 5 | yearly |

**Keygate API key** (server-side only, never in browser):
- Location: `/home/deepsim/Documents/shouke/workspace/keygate_api.txt`
- Prefix: `kg_live_c603...`
- Scope: `licenses:write`
- Admin endpoint verified: `POST /api/v1/admin/licenses` (tested successfully, test license cleaned up)

**Keygate Product ID (MEE):** `0722ae67-edb8-4e60-b019-91f14a7c92f5`

**Keygate Plan ID (Community/Academic):** `a2064f10-4deb-4eda-a8a7-5bf05aeac7a7`

---

## 3. Scope

### In Scope

| # | Item | Files |
|---|---|---|
| A | License status card in `index.html` | `mee/remotedemo/index.html` |
| B | Plan selection dropdown (5 plans) | `mee/remotedemo/index.html` |
| C | Purchase buttons (4 paid → Stripe Checkout URL in new tab) | `mee/remotedemo/index.html` |
| D | Community/Academic free-request form (name, email, institution) | `mee/remotedemo/index.html` |
| E | Keygate admin API proxy endpoint (`POST /license/request-community`) | `mee/remotedemo/server.py` |
| F | License activate endpoint (`POST /license/activate`) | `mee/remotedemo/server.py` |
| G | License status endpoint (`GET /license/status`) | `mee/remotedemo/server.py` |
| H | License deactivate endpoint (`POST /license/deactivate`) | `mee/remotedemo/server.py` |
| I | Existing key activation form | `mee/remotedemo/index.html` |
| J | Deactivate button (shown when licensed) | `mee/remotedemo/index.html` |
| K | README "Licensing & Plans" section | `README.md` |
| L | LICENSE.txt header with purchase links | `LICENSE.txt` |

### Out of Scope

- Keygate plan/price creation (already done by owner).
- API/SDK for user-side licensing (future task).
- Per-plan entitlement enforcement in the engine (Keygate features map already handles this; no code changes needed).
- CAPTCHA or bot protection for the free-request endpoint (v0: rate-limit by email+IP is sufficient).
- Changing the MEE licensing package (`mee/licensing/`) — all logic already exists from TASK_MEE_015.

---

## 4. Acceptance Criteria

1. **Each plan routes to the correct destination.**
   - Developer → `https://licenses.deepsim.ai:8443/pay/6c5bce2c`
   - Commercial → `https://licenses.deepsim.ai:8443/pay/7d44a91b`
   - Enterprise → `https://licenses.deepsim.ai:8443/pay/d09d97da`
   - OEM/Embedded → `https://licenses.deepsim.ai:8443/pay/15f2f3d7`
   - Community/Academic → `POST /license/request-community` (no external URL)

2. **No placeholder checkout URL is presented as a working purchase link.**
   - All four paid URLs are real, verified Keygate checkout IDs.
   - Community/Academic has no checkout URL (free flow only).

3. **Activation, status, and deactivation use real backend endpoints — not simulated success.**
   - `GET /license/status` returns real data from `LicenseClient.status()`.
   - `POST /license/activate {key}` calls `LicenseClient.activate(key)` → real Keygate verification.
   - `POST /license/deactivate` calls `LicenseClient.deactivate()` → real Keygate deactivation.
   - `POST /license/request-community {email, name, institution}` calls Keygate admin API → returns real license key.

4. **Backend secrets never reach browser code.**
   - `KEYGATE_API_KEY` is read server-side from environment variable or config file.
   - No API key, Stripe secret, or Keygate admin credential appears in `index.html`, JS, or any client-side file.
   - The four Stripe Checkout URLs are public-safe (they are payment links, not secrets).

5. **Existing local MEE CLI licensing remains functional.**
   - `mee-lic activate <key>` still works.
   - `mee-lic status` still works.
   - `mee-lic deactivate` still works.
   - No changes to `mee/licensing/` package.

6. **Community/Academic free request is rate-limited.**
   - Max 1 request per email per 24 hours (server-side, in-memory or file-based).
   - Max 3 requests per IP per hour (server-side).
   - Exceeding limits returns HTTP 429 with a clear message.

7. **Free-request form collects: name, email, institution (optional).**
   - Email is required and validated (basic format check).
   - Name is required (min 2 chars).
   - Institution is optional.

8. **Status card shows: status, plan name, days remaining (if applicable), offline state, device ID.**
   - Matches `LicenseClient.status()` output fields (R47 from 015 spec).

9. **Deactivate button is only visible when status is "licensed" (not trialing, not expired).**
   - Clicking it calls `POST /license/deactivate` and refreshes the status card.

10. **README and LICENSE.txt document all five plans with their purchase/request flows.**

---

## 5. Security Constraints

| # | Rule |
|---|---|
| S1 | `KEYGATE_API_KEY` is read from `MEE_KEYGATE_API_KEY` env var or `$MEE_HOME/keygate_api_key` file. Never hardcoded. |
| S2 | The four Stripe Checkout URLs are public (they are payment links). They may appear in client-side code. |
| S3 | The Keygate admin API key is **never** sent to the browser. The proxy endpoint reads it server-side. |
| S4 | The free-request endpoint validates email format and applies rate limits before calling Keygate. |
| S5 | The activate endpoint does NOT require the API key (it uses the public `/license/activate` SDK endpoint). |
| S6 | The status endpoint does NOT require the API key (it reads local trial state + calls the public `/license/verify` if a key is present). |
| S7 | All server-side HTTP responses include `Cache-Control: no-store` and `Access-Control-Allow-Origin: *` (consistent with existing `_http_endpoint`). |

---

## 6. Dependencies

| Dependency | Status |
|---|---|
| TASK_MEE_015 (License Integration) | ✅ CLOSED |
| Keygate plans created (5 plans) | ✅ Done by owner |
| Keygate API key created (`licenses:write` scope) | ✅ Done by owner |
| `RELEASE_KEY_ENCRYPTION_KEY` set | ✅ Done (2026-10-21) |
| MEE remote demo running | ✅ (watchdog + start script in place) |

---

## 7. Prerequisites Checklist (PM Verification)

- [x] Registry check: TASK_MEE_016 is taken (CUDA Compatibility Fix). 017, 018, 035 taken. **TASK_MEE_019 is the next available ID.**
- [x] Keygate plan configuration verified (5 plans, 4 with Stripe prices, 1 free).
- [x] Keygate API key verified (prefix `kg_live_c603`, scope `licenses:write`).
- [x] Admin license creation endpoint verified (`POST /api/v1/admin/licenses` → 200 + license key).
- [x] Checkout URLs verified (4 real checkout IDs).
- [x] Encryption key set and verified.
- [x] `server.py` HTTP endpoint architecture understood (`_http_endpoint` method, `process_request` contract).
- [x] `index.html` license section: currently empty (no license UI exists).
- [x] `mee/licensing/` package: fully functional from TASK_MEE_015, no changes needed.

---

## 8. Handoff

**Status:** G0 complete. Handed to CTO for G1 (architecture review + task plan with acceptance criteria).

**CTO must produce:**
- `CTO_PLAN.md` with exact file/symbol/line-range guidance (R-SI-2).
- Requirements list (R1–Rn) derived from the acceptance criteria above.
- Test strategy for each endpoint.
- Any architectural decisions (e.g., rate-limit storage, error handling, CORS).
