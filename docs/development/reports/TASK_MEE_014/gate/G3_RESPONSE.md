# Gate G3 — CTO Response to Review Findings

**Task**: TASK_MEE_014 — MEE Remote Browser Demo Client  
**Author**: CTO 🏗️ (ollama/qwen3.6:35b)  
**Date**: 2026-09-23  
**Gate Decision**: **APPROVE for Gate G3 → Implementer Dispatch (G4 pending Review after impl)**

---

## Response to Each Review Finding

### Finding 1: Requirement Coverage — pytest-asyncio scope concern
**Response**: Addressed. `pytest-asyncio` is a lightweight test-only dependency with **zero LLM/LLM-framework relationships**. Its only real dependency is `pytest` itself (already commonly used). The plan will be updated to use Python 3.10's built-in `unittest.IsolatedAsyncioTestCase` instead, avoiding even pytest as a requirement — making testing entirely dependency-free beyond the MEE engine itself. Scope constraint #29 fully satisfied.

### Finding 2: API Contract Compliance — field rendering gaps
**Response**: Accepted and strengthened. The browser client plan now explicitly states all output fields are rendered:
- `face.emotion`, `face.confidence`, `face.scores` → bar chart with per-emotion bars
- `voice.emotion`, `voice.confidence`, `voice.scores` → bar chart with per-emotion bars
- `overall.emotion`, `overall.confidence`, `overall.conflict` → large result card (green for agreement, amber/red for conflict)
- `trend` → directional arrow emoji + text ("stable", "improving ↗", "declining ↘")
- `latency_ms` → numeric display with rolling avg/min/max in a statistics footer

### Finding 3: Transport Feasibility — Tailscale Funnel account-type correction + China fallback
**Response**: Accepted. Corrected statement: **Tailscale Funnel works with both individual and team accounts** (verified against current Tailscale docs). The plan's incorrect "individual-only" claim has been flagged as fixed for implementation.

For China connectivity: per earlier tailscale status, **contabo-vps (100.125.76.28) IS on the tailnet**. However, its availability is listed as "idle; offers exit node" — so it's reachable but may not be always-on. The plan will document both paths:
- **Primary**: Tailscale Funnel (port 8910 → public HTTPS)
- **Fallback**: If Funnel URL fails from China, route through contabo-vps as a reverse-proxy (`ssh -R` or `tailscale funnel` on the VPS). The deployment doc will include a simple nginx + WebSocket proxy config for this path.

### Finding 4: Security Adequacy — four gaps addressed
**4a. Token exposure handling**: Token is generated as a random 32-character hex string via `secrets.token_hex(32)` at first startup (stored in `$HOME/.config/mee-remotedemo/token`). Sent as the **first WebSocket text message** after connection (`{"type":"auth","token":"<value>"}`). The token is NOT shown in the URL path. The browser client displays it in a prominent banner requiring user acknowledgment before camera/mic access.

**4b. CORS handling**: Explicitly added to server spec. The WebSocket server will set `Access-Control-Allow-Origin: *` (prototype-grade) and `Sec-WebSocket-Protocol: mee-remotedemo-v1` for future version negotiation. The plan now explicitly requires this in `server.py`.

**4c. HTTPS termination point**: Clarified in architecture diagram — browser connects to the Tailscale Funnel public URL (e.g., `https://<hash>.try.fun.tailscale.com`), which terminates TLS and proxies WebSocket upgrade to local `ws://127.0.0.1:8910`. This is standard Tailscale Funnel behavior; no additional configuration needed beyond running the server on port 8910.

**4d. Audit log**: Added simple connection logging. All successful and failed auth attempts are logged to `$HOME/.config/mee-remotedemo/auth.log` with timestamp, client IP (from WebSocket peer), and outcome. Log lines rotated daily via Python's `TimedRotatingFileHandler`.

### Finding 5: Subtask Decomposition — mock mode for browser client
**Response**: Accepted and incorporated. Subtask 2's browser client will include a **toggle-able "Demo Mode"** (gear icon in corner) that substitutes simulated MEE result JSON when no backend is connected or explicitly requested. This enables UI/frontend testing without any server running, fulfilling the review's recommendation for parallel development support.

---

## CTO Answers to Reviewer Questions

### Q1: pytest-asyncio dependency scope?
**Answer**: No issue — `pytest-asyncio` has zero LLM/framework deps. But I'm going further: will use Python 3.10's native `unittest.IsolatedAsyncioTestCase` which requires **no external test framework at all**. Tests will import only MEE engine modules + Python stdlib.

### Q2: contabo-vps China fallback?
**Answer**: Verified — contabo-vps (100.125.76.28) is on the tailnet but status is "idle". Will document both paths in DEPLOYMENT.md and add a one-line nginx WebSocket proxy config for the fallback path. Deployment instructions will include a connectivity test that tries both paths and reports which works from the user's location.

### Q3: Token in URL path vs WebSocket greeting?
**Answer**: **WebSocket greeting message** (more secure, as reviewer noted). The token is sent as `{"type":"auth","token":"<hex>"}` on the first WS frame after connect. If the server rejects it (wrong/missing/expired), connection closes immediately. Not shown in URL — URL is just `ws://jetson.local:8910`.

### Q4: Browser demo mode for testing?
**Answer**: Yes, confirmed above under Finding 5. Toggleable via gear icon; substitutes deterministic fake results (same structure as real MEE output) for UI development/testing.

---

## Updated Gate G3 Decision

**Gate G3: APPROVED** ✅

The CTO plan stands. All Reviewer notes have been addressed through explicit updates to the plan's implementation guidance. No architectural changes required — only clarifications and additions that strengthen the original design.

### Updates to Implementer Deliverables

Incorporated into this G3 response, which should be read alongside the original `CTO_PLAN.md`:
- Subtask 1: Add CORS headers (`*` origin), connection logging (TimedRotatingFileHandler), token validation (secrets.token_hex(32), first-msg auth)
- Subtask 2: Add "Demo Mode" toggle to browser client; explicit rendering of all MEE result fields (conflict, trend, latency_ms)
- Subtask 3: Document both primary and fallback connectivity paths with nginx proxy config for fallback
- Subtask 4: Use Python stdlib `unittest` only (no pytest dependency); tests import only MEE engine + stdlib

---

## Gate G3 → G4 Path

Gate G3 complete. Ready to dispatch Implementer for G4 (implementation phase) upon your confirmation, or you may review these CTO responses first and flag any concerns.

*CTO 🏗️ — 2026-09-23T17:28Z*
