# CTO_PLAN — TASK_MEE_019: License Plan Selection & Purchase UI

**Task ID:** TASK_MEE_019  
**Gate:** G1 — CTO Architecture Review + Task Plan  
**Date:** 2026-10-22  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)  
**Depends On:** TASK_MEE_015 (✅ CLOSED), Keygate plan config (✅ done by owner)

---

## 1. Executive Summary

Add a license management UI and server-side API to the MEE remote demo (`mee/remotedemo/`) enabling users to:
1. View current license status (trialing / licensed / expired)
2. Select from 5 plans and follow the correct flow per plan
3. Activate an existing key, deactivate, or request a free Community/Academic license

**All changes are additive.** Zero modifications to `mee/licensing/` (TASK_MEE_015 is complete).  
4 new backend endpoints in `server.py`; 4+ new sections in `index.html`.

---

## 2. Architecture Decisions

### AD-1: GET `/license/status` via `_http_endpoint`
The existing `RemotedemoServer._http_endpoint()` method serves plain HTTP on the WS port for non-upgrade requests (proven by `/healthz`). GET requests need no body, so this endpoint fits perfectly — returns `(HTTPStatus, headers, body_bytes)` tuple.

### AD-2: POST endpoints via a lightweight secondary HTTP server
The websockets `process_request` hook signature is `(path, request_headers) → response_tuple | None`. It does **not** receive the request body for POST requests. Adding a second HTTP server handles POST bodies correctly while keeping the WS port unchanged.

- Uses Python's `http.server.ThreadingHTTPServer` (stdlib, no new deps) bound to `0.0.0.0:MEE_DEMO_HTTP_PORT`
- Configurable via env var `MEE_DEMO_HTTP_PORT` (default: 18910 = config.port + 1000)
- The remote demo serves on the same host; when served behind Tailscale Funnel/HTTPS, the browser reaches both ports through the same tunnel
- When running locally (`ws://localhost:8910`), the HTTP port is `http://localhost:18910`

### AD-3: Rate-Limit Storage — In-Memory with TTL
Rate-limit state stored in a lightweight class (`CommunityRequestRateLimiter`) using `time.time()` and dictionaries keyed by email/IP. No disk I/O needed. Production hardening could migrate to Redis later.

### AD-4: Stripe Checkout URLs Are Public-Safe
All four paid plan checkout URLs are public payment links. They may appear in client-side code without security concern.

---

## 3. Requirements (Derived from Acceptance Criteria)

| Req | Description | Implementation Location |
|-----|-------------|------------------------|
| **R1** | `GET /license/status` — returns license status from `LicenseClient.status()` | `_http_endpoint()` in `server.py` |
| **R2** | `POST /license/activate {key}` — calls `LicenseClient.activate(key)` | Secondary HTTP server |
| **R3** | `POST /license/deactivate` — calls `LicenseClient.deactivate()` | Secondary HTTP server |
| **R4** | `POST /license/request-community {name,email,institution?}` — proxy to Keygate admin API, rate-limited | Secondary HTTP server + `CommunityRequestRateLimiter` |
| **R5** | Paid plans → Stripe Checkout URL in new tab (`window.open`) | `index.html` JS |
| **R6** | Community/Academic → self-service form (name required, email required, institution optional) | `index.html` HTML + JS |
| **R7** | Status card shows: status badge, plan name, days remaining, offline indicator, device ID | `index.html` CSS + JS rendering |
| **R8** | Deactivate button visible ONLY when status = "licensed" | Conditional DOM rendering |
| **R9** | No API keys or secrets in client-side code | KEYGATE_API_KEY read server-side only |
| **R10** | Community/Academic clearly marked "Free" (no checkout URL) | `index.html` plan cards |
| **R11** | Rate limiting: 429 when exceeded, with retry-after seconds | RateLimiter class in `server.py` |
| **R12** | All responses include `Cache-Control: no-store` + `Access-Control-Allow-Origin: *` | `_http_endpoint` helper already does this |

---

## 4. Implementation Plan — Exact File/Symbol/Line Guidance

### Phase A: Server-Side Endpoints (`mee/remotedemo/server.py`)

#### 4A.1 Rate Limiter Class
- **Location:** `server.py`, insert AFTER the `RateLimiter` class (~line ~80, after `AuthAuditor` at ~line 97)
- **New class:** `CommunityRequestRateLimiter`
  - `__init__(self)` — internal dicts: `_by_email` (email → [(timestamp, ip), ...]), `_by_ip` (ip → [timestamp, ...])
  - `check(self, email: str, ip: str) -> tuple[bool, int]` — returns `(allowed, retry_after_seconds)`; prunes stale entries on each call
  - Internal helpers: `_prune_email(email)` removes entries > 86400s old; `_prune_ip(ip)` removes entries > 3600s old

#### 4A.2 `GET /license/status` route handler
- **Location:** `server.py`, inside `_http_endpoint()` method (~line ~270, after `/healthz` block and before the `/` path block)
- Returns response tuple using existing `_res()` helper pattern (need to make it accessible or inline)

#### 4A.3 Secondary License HTTP Server
- **Location:** `server.py`, NEW section starting ~line 430+ (after main class, before `async def run_server()`)
- **New class:** `LicenseHTTPServer`
  - `__init__(self, port: int)` — binds to `0.0.0.0:port`
  - `start(self) → threading.Thread` — starts the ThreadingHTTPServer in background thread
  - `stop(self)` — shuts down the server
  - `_handle(self, path, headers, body_bytes)` — dispatches to route handlers
- **Route handlers:**
  - `GET /license/status` → calls `LicenseClient.status()` (via inline import)
  - `POST /license/activate` → calls `LicenseClient.activate(key)`
  - `POST /license/deactivate` → calls `LicenseClient.deactivate()`
  - `POST /license/request-community` → rate-limited proxy to Keygate admin API
- **Integration:**
  - `RemotedemoServer.__init__()`: create `self._license_server = LicenseHTTPServer(port)` where port = env or `config.port + 1000`
  - `RemotedemoServer.start()`: start the HTTP server in parallel with WS serve
  - `RemotedemoServer.stop()`: call `self._license_server.stop()`

#### 4A.4 Server Config
- Add to `RemotedemoConfig` or use env var `MEE_DEMO_HTTP_PORT` (default: port + 1000)
- No new config file needed — the secondary server is started automatically when the demo runs

### Phase B: Client-Side UI (`mee/remotedemo/index.html`)

#### 4B.1 CSS additions (~line ~80, before `footer` in `<style>`)
```css
/* License section */
.license-card { background: var(--panel); border-radius: 10px; padding: 14px;
  border: 1px solid #2a333f; margin-top: 16px; }
.license-card h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin: 0 0 10px; }
.license-status-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.plan-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px; margin-top: 10px; }
.plan-card { background: var(--panel-2); border: 1px solid #34404e; border-radius: 8px;
  padding: 10px; cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.plan-card:hover { border-color: var(--accent); box-shadow: 0 0 6px rgba(79,195,247,.15); }
.plan-card.selected { border-color: var(--accent); box-shadow: 0 0 8px rgba(79,195,247,.25); }
.plan-badge { display: inline-block; font-size: 10px; padding: 2px 6px; border-radius: 4px;
  text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }
.plan-badge-free { background: #1c3320; color: #6f6; }
.plan-badge-paid { background: #1a2538; color: var(--accent); }
#licenseForm { display: none; margin-top: 10px; padding: 10px; background: var(--panel-2);
  border-radius: 8px; }
#licenseForm.active { display: block; }
#licenseForm input { width: 100%; margin-bottom: 6px; }
.license-error { color: var(--err); font-size: 12px; margin-top: 4px; }
.license-ok { color: var(--ok); font-size: 12px; margin-top: 4px; }
```

#### 4B.2 HTML additions (~line ~160, after the emotion bars grid in right column)
```html
<!-- License Section -->
<div class="card license-card" id="licenseSection">
  <h2>License</h2>
  
  <!-- Status Display (shown when trialing/licensed/expired) -->
  <div id="licenseStatusCard" style="display:none;">
    <div class="license-status-row">
      <span id="licDot" class="dot off"></span>
      <span id="licStatus" style="font-weight:600;">—</span>
      <span id="licPlan" style="color:var(--muted); font-size:12px;"></span>
      <span id="licOffline" style="color:var(--warn); font-size:11px; display:none;">⚠ offline</span>
    </div>
    <div style="font-size:12px; color:var(--muted);" id="licMeta">
      <span id="licDays">—</span> · 
      <span id="licDevice">device: —</span>
    </div>
    <div class="row" style="margin-top:8px;">
      <button id="btnDeactivate" class="danger" style="display:none; font-size:12px; padding:6px 10px;">Deactivate License</button>
    </div>
  </div>
  
  <!-- Plan Selection -->
  <h3 style="font-size:12px; color:var(--muted); margin: 14px 0 6px; text-transform:uppercase;">Select a License Plan</h3>
  <div class="plan-grid" id="planGrid"></div>
  
  <!-- Community/Academic Form (shown when that plan is selected) -->
  <div id="licenseForm">
    <input type="text" id="reqName" placeholder="Your name *" required>
    <input type="email" id="reqEmail" placeholder="Email *" required>
    <input type="text" id="reqInstitution" placeholder="Institution (optional)">
    <div class="row">
      <button id="btnRequestFree" class="primary" style="font-size:12px; padding:6px 10px;">Request Free License</button>
      <span id="requestMsg"></span>
    </div>
  </div>
  
  <!-- Key Activation -->
  <h3 style="font-size:12px; color:var(--muted); margin: 14px 0 6px; text-transform:uppercase;">Activate Existing Key</h3>
  <div class="row">
    <input type="text" id="activateKey" placeholder="Paste your license key..." spellcheck="false">
    <button id="btnActivate" style="font-size:12px; padding:6px 10px;">Activate</button>
    <span id="activateMsg"></span>
  </div>
</div>
```

#### 4B.3 JavaScript additions (~line ~850+, after existing wiring)
- **Plan constants:**
```javascript
const PLANS = {
  "community-academic": { name: "Community / Academic", type: "free",  description: "Free for personal, education & non-commercial research use." },
  "developer":         { name: "Developer",            type: "paid",  checkout: "https://licenses.deepsim.ai:8443/pay/6c5bce2c" },
  "commercial":        { name: "Commercial",           type: "paid",  checkout: "https://licenses.deepsim.ai:8443/pay/7d44a91b" },
  "enterprise":        { name: "Enterprise",           type: "paid",  checkout: "https://licenses.deepsim.ai:8443/pay/d09d97da" },
  "oem-embedded":      { name: "OEM / Embedded",       type: "paid",  checkout: "https://licenses.deepsim.ai:8443/pay/15f2f3d7" },
};
```

- **License API functions:**
```javascript
const LICENSE_HTTP_PORT = window.location.port === "8910" ? "18910" : ""; // only for local dev; remote uses same origin via proxy
let licenseHttpBase = (() => {
  // When served from localhost, use the secondary HTTP port
  if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    return `http://${location.hostname}:${MEE_DEMO_HTTP_PORT || 18910}`;
  }
  // When served from remote (Tailscale Funnel, HTTPS), call same-origin via WS port proxy
  // Since process_request only handles GET, use relative path for status + the HTTP port for POST
  return window.location.origin + ":" + (parseInt(location.port) + 1000);
})();

async function getLicenseStatus() {
  const resp = await fetch(`${licenseHttpBase}/license/status`);
  return resp.json();
}

async function activateLicense(key) {
  const resp = await fetch(`${licenseHttpBase}/license/activate`, {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({key})
  });
  return resp.json();
}

async function deactivateLicense() {
  const resp = await fetch(`${licenseHttpBase}/license/deactivate`, { method: "POST" });
  return resp.json();
}

async function requestCommunityLicense(name, email, institution) {
  const resp = await fetch(`${licenseHttpBase}/license/request-community`, {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({name, email, institution})
  });
  return { ok: resp.ok, status: resp.status, data: resp.json() };
}
```

- **UI rendering functions:** `renderLicenseStatus(data)`, `renderPlanGrid()`, `handlePlanSelect(planSlug)`
- **Event wiring:** connect buttons (`#btnDeactivate`, `#btnActivate`, `#btnRequestFree`) to their handlers

### Phase C: Documentation Updates

#### 4C.1 README.md — "Licensing & Plans" section
- **Location:** After existing license paragraph (~line 143 of README)
- Add a new `<h3>Licensing & Plans</h3>` with:
  - Table of all 5 plans (name, type, purchase link, activation limit)
  - Brief description of Community/Academic free request flow
  - Reference to `mee-lic` CLI and Keygate docs

#### 4C.2 LICENSE.txt — Add plan purchase links in preamble
- Add a section after the title block listing all 5 license categories with their intended use and purchase/request URLs (from §4 of existing LICENSE.txt, enriched with actual URLs)

---

## 5. Test Strategy

### Unit Tests (`tests/test_license_ui.py` — NEW file)
| Test | Target | Approach |
|------|--------|----------|
| `test_rate_limiter_basic` | `CommunityRequestRateLimiter.check()` | 2 requests same email → second denied (429 equivalent) |
| `test_rate_limiter_email_ttl` | `CommunityRequestRateLimiter.check()` | Simulated 86401s wait → allowed again |
| `test_rate_limiter_ip_limit` | `CommunityRequestRateLimiter.check()` | Same IP, 3 different emails → third denied |
| `test_rate_limiter_ip_email_independent` | `CommunityRequestRateLimiter.check()` | Same email, different IPs → counts independently |

### Integration Tests (via existing test infrastructure)
| Test | Approach |
|------|----------|
| `test_license_status_integration` | Run RemotedemoServer in test mode; call GET `/license/status`; verify shape + values match `LicenseClient.status()` |
| `test_activate_endpoint` | POST `/license/activate {key}` with valid key → verify 200 + `{valid: true}` |
| `test_deactivate_endpoint` | Activate then deactivate via endpoint → verify status changes |
| `test_community_request_rate_limited` | Rapid POST to `/license/request-community` same email → first succeeds, subsequent get 429 |
| `test_community_missing_fields` | POST without name or email → 400 with clear message |

### Manual Test Checklist (for PM/Owner verification)
1. Open remote demo page → license section at bottom of right column
2. Click each plan card → paid opens checkout in new tab, community opens form
3. Fill community form with valid name/email → get real license key back
4. Paste existing key into activation field → activate and refresh status
5. Status shows: licensed/trialing/expired, plan name, device ID
6. Click deactivate (only visible when licensed) → status changes
7. Test rate limiting: send 2+ community requests rapidly → 429

---

## 6. Gate Checklist — G1 Prerequisites

| Check | Status |
|-------|--------|
| TASK_DESCRIPTION.md present | ⚠ PM may want to create from TASK_REQUEST for standardization |
| TASK_REGISTRY.md row (→ DRAFTED) | ✅ Confirmed in memory |
| LOCK released | ✅ G0 complete |
| Prior task artifacts exist | ✅ TASK_MEE_015 all gates closed |
| Acceptance criteria clear | ✅ 12 AC + 7 security constraints documented |
| Dependencies verified | ✅ Keygate plans, API key, encryption key all confirmed |

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| POST body reading in websockets `process_request` not supported | High | Resolved: separate lightweight HTTP server on configurable port |
| Remote demo behind Funnel: HTTP port reachable? | Medium | Server binds to same host as WS (0.0.0.0); accessible via same tunnel |
| Keygate API key exposure in browser | Critical (blocked) | KEYGATE_API_KEY used ONLY server-side; never in client code |
| Community request abuse (spam) | Medium | Rate limiting 1/email/24h + 3/IP/hour; future: CAPTCHA or email verification |
| Stripe checkout URL in client code | Low (acceptable) | Checkout URLs are public payment links, not secrets — per S2 constraint |

---

## 8. Artifacts This Gate Produces

- ✅ `CTO_PLAN.md` (this file)
- `LICENSE_UI_SPECIFICATION.md` — endpoint specs + plan config table (✅ written)
- `CORE_CONTRACTS.md` — API shapes, rate limit policy, security contracts (✅ written)
- `BOUNDARIES.md` — what this task does NOT touch (✅ written)

---

## 9. Requirements Traceability

| Req | Acceptance Criterion | Implementation Location |
|-----|---------------------|------------------------|
| AC1 | Each plan routes correctly | `index.html` JS `PLANS` constant + `handlePlanSelect()` |
| AC2 | No placeholder URLs | All 4 paid URLs verified in Keygate; community = free (no URL) |
| AC3 | Real backend endpoints | `server.py` 4 route handlers using real `LicenseClient` / Keygate admin API |
| AC4 | Secrets never reach browser | KEYGATE_API_KEY read server-side only; checkout URLs are public-safe |
| AC5 | CLI unchanged | Zero changes to `mee/licensing/` or `cli.py` |
| AC6 | Rate limiting | `CommunityRequestRateLimiter` in `server.py` + 429 responses |
| AC7 | Form fields: name, email, institution (optional) | `index.html` form HTML + JS validation |
| AC8 | Status card shows required fields | `renderLicenseStatus()` renders all fields from `GET /license/status` |
| AC9 | Deactivate only visible when licensed | Conditional DOM rendering in `renderLicenseStatus()` |
| AC10 | README + LICENSE.txt document plans | Section added to both files (§4C) |

---

**CTO 🏗️ — Gate G1 Plan Complete. Awaiting owner approval.**
