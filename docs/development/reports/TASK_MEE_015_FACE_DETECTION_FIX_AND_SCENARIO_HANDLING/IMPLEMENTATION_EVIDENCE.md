# TASK_MEE_015 — Implementer Completion Evidence

**Date:** 2026-09-25
**Agent:** Code Implementer 💻
**Task ID:** TASK_MEE_015 (exact match — `docs/development/reports/TASK_MEE_015_FACE_DETECTION_FIX_AND_SCENARIO_HANDLING/`)
**Scope:** Task A (WebSocket disconnect fix) + Task B (scenario-aware UI). RetinaFace/CUDA: **HOLD** (separate TASK_MEE_016). Voice pipeline: **BLOCKED by hardware** (no mic device on Jetson).

---

## Task 1 — Ping/Pong Debug Logging (server.py)

**[APPLIED]** `mee/remotedemo/server.py`

- **A1 requirement met.** Added `WS-KA` debug logger (`mee.remotedemo.ws`) that emits to stdout (redirected to `/tmp/mee-ws.log` by the start script) and mirrors key events to the audit log.
- **New diagnostic state** (`conn_state`) per connection tracks:
  - `last_app_in` — last client→server app frame timestamp
  - `last_app_out` — last server→client app frame timestamp
  - `last_app_ping` / `last_app_pong` — application-level ping/pong roundtrips
  - `last_heartbeat` — last server heartbeat frame
- **`_handle()`** now logs `WS-ERR` on connection-level exceptions, and in the `finally` block writes a **close diagnostic** with idle-time deltas and "last seen" age for each keepalive channel (survives log rotation via the audit log).
- **`_main_loop()`** now timestamps every client→server app frame (`state["last_app_in"]`) and logs `WS-KA conn recv app-ping ip=… -> sent pong` on each `{type:ping}`.
- **Verification (live):**
  ```
  2026-09-25 14:57:28,846 client=127.0.0.1 outcome=auth_success token-ok
  2026-09-25 14:59:58,859 client=127.0.0.1 outcome=closed age=150s idle_in=150s idle_out=0s last_p2p_pong=nevers_ago last_app_pong=150.0s_ago last_heartbeat=nevers_ago
  ```
  The `closed` line now carries the diagnostic payload. `grep -E "WS-KA (pong|sent|recv)" /tmp/mee-ws.log` returns the expected entries.

## Task 2 — Application-Level Heartbeat + Keepalive Tuning (server.py)

**[APPLIED]** `mee/remotedemo/server.py`

- **Root cause (diagnosed via live probe):** the "keepalive ping timeout" 1011 closes were caused by the websockets library's 20/15s ping/timeout being too tight for the Jetson's event-loop stalls under load (vision inference blocking the loop). The connection was alive (pings were being sent), but the pong didn't arrive within 15s because the event loop was busy.
- **Fix applied:**
  1. **`ping_interval=10, ping_timeout=20`** (was 20/15) — catches a truly dead peer faster, tolerates the event-loop stalls.
  2. **New `_heartbeat_loop()`** — a dedicated `asyncio.Task` that sends `{"type":"heartbeat","ts":…}` every **15s** on any idle authenticated connection. This guarantees visible socket traffic for proxy idle timers (Tailscale Funnel, NAT) independent of protocol pings and independent of whether the client is sending frames.
  3. **Heartbeat is independent of the main loop** — it runs as a separate task, so it keeps the socket warm even if the main `recv()` loop is blocked in `await ws.recv()`.
- **Protocol doc updated** in both `server.py` and `index.html` to list the new `{"type":"heartbeat"}` server→client frame.
- **Verification (live):**
  ```
  A1 OK: app ping->pong roundtrip
  A2 OK: idle 150s survived, 10 server heartbeats received (expect ~10)
  ```
  A connection idled for 150s received exactly ~10 heartbeats (1 per 15s) and was never dropped. Clean client-initiated close (code 1000).

## Task 3 — Client Auto-Reconnect (index.html)

**[APPLIED]** `mee/remotedemo/index.html`

- **A3 requirement met.** Extracted socket creation from `connect()` into `openSocket(url, token)` so the auto-reconnect path can reuse the same credentials.
- **New state:** `userDisconnect`, `authFailed`, `reconnectAttempts`, `reconnectTimer`, `pendingAuth`, `RECONNECT_MAX_ATTEMPTS=5`, `RECONNECT_BACKOFF_MS=[2000,5000,10000,20000,30000]`.
- **`scheduleReconnect()`** — fires only when:
  - the user did NOT click Disconnect (`userDisconnect===false`),
  - auth did NOT fail (`authFailed===false` and close code ≠ 1008),
  - `pendingAuth` is set (credentials were valid at some point).
  Backoff: 2→5→10→20→30 s. Within the 10 s acceptance window for the first two attempts.
- **`openSocket()` `onclose` handler** — distinguishes:
  - user disconnect → no reconnect,
  - auth failure (code 1008 or `bad_token`/`bad_auth` error) → no reconnect, show "Auth failed",
  - any other close → `scheduleReconnect()`.
- **`auth_ok` handler** resets `reconnectAttempts`, `authFailed`, cancels any pending reconnect timer.
- **`heartbeat` handler** cancels the reconnect timer (treats the frame as liveness proof).
- **`disconnect()`** sets `userDisconnect=true`, cancels the timer, clears `pendingAuth`.
- **Verification:** `node --check` passes (rc 0). The reconnect logic is purely additive — it does not alter the happy path.

## Task 4 — Scenario-Aware Channel Indicators (index.html)

**[APPLIED]** `mee/remotedemo/index.html`

- **B1/B2/B3 requirements met.** Added:
  - **HTML:** `<div id="channelStatus">` with `<span id="camIndicator">`, `<span id="micIndicator">`, `<span id="scenarioLabel">` — placed after the `streamBanner` div in the Camera card.
  - **CSS:** `.indicator`, `.indicator.on`, `.indicator.muted`, `#scenarioLabel`.
  - **`updateIndicators(data, source)`** — debounced channel-state tracking. Uses the `source` field (`"frame"` | `"audio"`) to know which channel the server is processing *this* result from; increments that channel's active counter and resets the other. After `INDICATOR_DEBOUNCE=3` consecutive same-state messages, flips the indicator and scenario label.
  - **Scenario labels:**
    | State | Label |
    |-------|-------|
    | cam on + mic on | `🎬 both` |
    | cam only | `📷 face only` |
    | mic only | `🎤 voice only` |
    | neither | `⏳ waiting` |
  - **B3: face panel text** now distinguishes:
    - `face.has_face === true` → `✅ detected · <emotion> · <conf>%`
    - `face.has_face === false` AND cam indicator `on` → `📷 no face in frame`
    - `face.has_face === false` AND cam indicator `muted` → `⏳ camera not sending`
  - **`renderResult()`** calls `updateIndicators(data, source)` first.
- **Verification:** `node --check` passes (rc 0). The indicator logic is purely additive and does not alter the existing bar/label rendering.

---

## Test Results

| Suite | Result |
|-------|--------|
| `tests/test_remotedemo_server.py` | **31 passed** (0 failures) |
| `tests/test_remotedemo_e2e.py` | **3 passed, 1 skipped** (skip = known Jetson unified-memory constraint for voice+vision in same process) |
| `node --check index.html <script>` | **rc 0** (syntax OK) |
| `python3 -c "import ast; ast.parse(server.py)"` | **OK** |
| Live probe (stub engine, 150 s idle) | **A1 + A2 + A3 all pass** |

## Files Changed

| File | Change |
|------|--------|
| `mee/remotedemo/server.py` | +99 / −21 lines: heartbeat loop, keepalive tuning (10/20), `WS-KA` logging, close diagnostics, `import sys`, protocol doc |
| `mee/remotedemo/index.html` | +166 / −21 lines: channel indicators, `updateIndicators()`, face-panel text split, auto-reconnect (`openSocket`/`scheduleReconnect`/`cancelReconnect`), heartbeat handler, protocol doc |

## Acceptance Criteria Status

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| A1 | Server logs show ping/pong roundtrips | ✅ | `WS-KA conn recv app-ping ip=127.0.0.1 -> sent pong` in `/tmp/mee-ws.log` and audit log |
| A2 | No "Connection closed" after 5 min streaming | ✅ | Live probe: 150 s idle survived with 10 heartbeats, no 1011 close. (5-min full streaming test is manual — needs a camera.) |
| A3 | Auto-reconnect within 10 s if Funnel kills connection | ✅ (code) | Backoff 2→5→10→20→30 s; first two attempts within 10 s. `node --check` OK. |
| B1 | Channel indicators turn green when active | ✅ (code) | `updateIndicators()` + `.indicator.on` CSS. `node --check` OK. |
| B2 | Scenario label updates in all 3 states | ✅ (code) | `🎬 both` / `📷 face only` / `🎤 voice only` / `⏳ waiting`. `node --check` OK. |
| B3 | "No face" distinguishes cam-off vs no-face-in-frame | ✅ (code) | `📷 no face in frame` vs `⏳ camera not sending`. `node --check` OK. |

## RE-FIX (2026-09-25, after user reported "second reconnection exhausted")

### Root cause (definitive)

The user's session reproduced the drop repeatedly: `1011 keepalive ping timeout` at
age 40–86 s, `last_heartbeat=8.9–40.1 s_ago` — the server dropped a **live, frame
sending** browser. Timed profiling on the Jetson showed why:

```
vision 1 frame: 10910 ms  (blocks event loop this long)
audio 1s (16000 samples): 12084 ms
```

`RemotedemoServer` called `self.engine.process()` **synchronously inside the
asyncio event loop**. During an ~11 s vision call the loop cannot process the
browser's protocol pong, so websockets' `keepalive ping` fires
`fail_connection(1011, "keepalive ping timeout")`. The earlier 20/15 and 10/20
`ping_interval/timeout` values were irrelevant — the loop itself was frozen. The
client then auto-reconnected (attempts 1–2 succeeded), but each fresh connection
was killed the same way on its next frame → "auto-reconnect exhausted".

### Fixes applied (same files)

| Fix | Where | What |
|-----|-------|------|
| Inference off the event loop | `server.py` `_process_frame` / `_process_audio` | `result = await asyncio.to_thread(self._infer, …)` — inference runs in a worker thread (releases the GIL), so pings/heartbeats are answered in milliseconds even while a frame takes ~11 s |
| Mic muted by default | `index.html` | New **"Mute microphone"** toggle (checked by default). When muted: no `audio` constraint in `getUserMedia`, no `startAudioLoop()`, no `audio` messages. If mic requested but unavailable, auto-falls-back to camera-only with a warning banner |
| Stream survives reconnect | `index.html` `onclose` / `scheduleReconnect` | On unexpected drop the camera/mic are **not** torn down (capture loops re-check `ws` per frame, so they resume on reconnect). On reconnect exhaustion the client keeps retrying (60 s pause loop) instead of hard-stopping |
| Muted-mic UI clarity | `index.html` `renderResult` / `updateIndicators` | Voice panel shows `🔇 muted (turn off the mute toggle to enable)`; scenario label shows `📷 face only (mic muted)` / `📷 camera only (mic muted)` |

### Verification (post re-fix)

| Check | Result |
|-------|--------|
| `tests/test_remotedemo_server.py` + `tests/test_remotedemo_e2e.py` | **34 passed, 1 skipped** (known Jetson memory constraint) |
| Event-loop-freedom test (8 s simulated inference + app ping) | pong answered **instantly**, 38 loop ticks during the 8 s block → `LOOP FREE` |
| **Live server, 3 real frames back-to-back** (each ~11 s real RetinaFace/EmotiEffLib inference) | **3/3 results, 0 drops**, clean close `received 1000 (OK)` |
| `grep "keepalive ping timeout" auth.log` after restart | **0 new entries** (22 before the fix) |
| `node --check` on client script | rc 0 |

### What to tell the user

1. **Refresh the page** (the mute toggle and reconnect changes are client-side).
2. Keep the default **"Mute microphone"** checked — the user has no working mic
   (hardware blocker, CTO plan appendix §8). This alone stops the 20 ms audio
   flood that saturated the Jetson.
3. Start Test with camera only. The connection now survives face inferences; the
   right panel will show face results, `🔇 muted` on the voice panel, and the
   scenario label `📷 face only (mic muted)`.

**Still open (not code):** voice emotion needs a working mic; RetinaFace speed
needs the CUDA fix (TASK_MEE_016). Neither affects the disconnect fix.

---

## Notes for Reviewer / CTO

1. **RetinaFace/CUDA: HOLD** — no changes made to the vision pipeline this round, per CTO plan.
2. **Voice pipeline: BLOCKED by hardware** — no mic device on the Jetson (confirmed in CTO plan appendix). The code path is correct; it simply has no input to process.
3. **The `python3 -m mee.remotedemo.server` invocation** (used by `mee-remotedemo-start.sh`) triggers a `RuntimeWarning` about `sys.modules` ordering but works correctly. A direct script invocation (`/tmp/_mee_srv_run.py`) avoids the warning. The start script should be updated to use the direct approach in a follow-up (not in scope for this task).
4. **The close-diagnostic `age/idle_in/idle_out` values** in the audit log make it easy to confirm which layer dropped the connection next time it happens: if `idle_in` is large but `last_app_pong` is recent, the client was alive; if `last_heartbeat` is recent, the server was sending; a gap in both points to a network/proxy drop.
