# CTO Plan — TASK_MEE_018: Remote Demo Public Access, Reconnect Resilience & Stability

**Task ID:** TASK_MEE_018
**Gate:** G1 — Plan (retrospective; work was driven by live user-testing failures on 2026-09-27/28)
**Date:** 2026-09-28
**Planned By:** CTO / Architect (recorded by Implementer from session evidence)

---

## 1. Problem Statement (user reports)

Tester team (Mr. Xu) testing remotely over the public internet reported, in order:

1. **Page unreachable outside the tailnet** — testers in China (VPN) and on phone
   data could not reach `https://jetson-agx:8443/` (tailnet-only address).
2. **Token auto-fetch failed publicly** — the original `/token` HTTP endpoint
   exposed the auth token to anyone who could reach the funnel URL (security
   regression) and was unreliable through the proxy.
3. **"Disconnected (code 1006)" flapping** — connection dropped and reconnected
   repeatedly during streaming; recognition unstable.
4. **Server dying repeatedly with no trace** (10:51–11:44 and again
   12:15–13:26 on 2026-09-28) — ~20–40 forced restarts, no OOM in dmesg,
   no cgroup `oom_kill` counters, no crash traceback.
5. **False "Server Error" banner** on the client whenever the server's 15 FPS
   rate limiter tripped (benign overflow misreported as failure).

## 2. Scope

In scope (all under `mee/remotedemo/` + repo-level helpers):
- `server.py` — public funnel endpoint (`GET /`, `GET /healthz`), `/token`
  removal, startup banner, CPU thread cap, signal diagnostics.
- `index.html` — manual token entry, client-side throttling, reconnect
  hardening, rate-limit banner silencing.
- `https_server.py` (new) — HTTPS static page on 8443.
- `mee-ws-watchdog.sh` (new) — auto-restart loop for the WS server.
- `mee-remotedemo-start.sh` — 4-step startup, public-vs-tailnet URL labeling,
  token shown once out-of-band.
- `docs/remotedemo/ACCESS.md`, `docs/remotedemo/DEPLOYMENT.md` — updated.

Out of scope:
- Runtime product changes (engine, models, `deepefflib`) — Layer 2 untouched.
- Root-cause elimination of the external SIGKILL source (diagnostics added;
  killer not yet identified — see §6 Open items).

## 3. Accepted Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Public Funnel**: WS server (8910) serves `GET /` (page) + `GET /healthz` via `process_request`, alongside WS upgrade. Single public URL for page + transport. | Testers without Tailscale (China VPN, phone data) need one reachable URL; funnel provides TLS termination. |
| D2 | **Remove `/token` endpoint** (Option 3: manual token entry). Token is handed out-of-band (chat/secure channel) and typed into the page. | Exposing the token over a public HTTP endpoint defeats the auth model. |
| D3 | **Client throttling ~10 FPS** (100 ms capture interval + 90 ms min send gap). | Server rate limit is 15 FPS; Jetson inference is ~11 s/frame for full pipeline — flooding the queue caused drops and CPU spikes. |
| D4 | **Reconnect hardening**: max attempts 5→12, then infinite 30 s-interval retry; ignore close code 1006 as transient. | Public path through funnel/Tailscale edge produces transient abnormal closes; giving up after 5 was far too aggressive. |
| D5 | **Silence `rate_limited` error banner** client-side. | Benign overflow must not read as server failure. |
| D6 | **WS watchdog** (`mee-ws-watchdog.sh`) started by the start script; restarts server within ~5 s if the listener disappears. | Server was being killed externally and repeatedly; availability must not depend on one process surviving. |
| D7 | **CPU thread cap** `MEE_DEMO_MAX_THREADS=2` (default; override env `=N`, `0`=library default) applied in `run_server()` before engine construction. | Inference burst on shared Jetson unified memory/CPU correlated with the external kills; capping MediaPipe/XNNPACK/OpenCV/BLAS pools reduces spike width. |
| D8 | **Startup banner** `TASK_MEE_034 server started pid=... host=... port=...` to ws log + audit log. | Every kill leaves a timestamp + PID to correlate with the killer. |
| D9 | **Signal diagnostics** (TASK_MEE_035): catch SIGTERM/SIGINT/SIGABRT, log signal + PID, re-raise. SIGKILL uncatchable — documented as the remaining blind spot. | Distinguishes graceful external stops (watchdogd? systemd? user `kill`) from hard kills. |

## 4. File / Symbol / Line Guidance (R-SI-2)

| File | Symbol / region | Change |
|------|-----------------|--------|
| `mee/remotedemo/server.py` | `_http_endpoint` (`process_request` handler) | `GET /` → serves `index.html`; `GET /healthz` → `{"status":"ok"}`; `GET /token` → **removed** (410/404); WS upgrade falls through to websockets. |
| `mee/remotedemo/server.py` | `RemotedemoServer.start()` | Banner: `TASK_MEE_034 server started pid=... host=... port=...` + `pid=` in audit record. |
| `mee/remotedemo/server.py` | `run_server()` (top) | Thread-cap block reading `MEE_DEMO_MAX_THREADS` (default `"2"`) into `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS` via `setdefault` before engine build. |
| `mee/remotedemo/server.py` | `_install_signal_diagnostics()` + `main()` | New module function; called first in `main()`; installs handler for SIGTERM/SIGINT/SIGABRT logging `TASK_MEE_035 received signal <NAME> (pid=...)`. |
| `mee/remotedemo/index.html` | reconnect block | `RECONNECT_MAX_ATTEMPTS = 12`; after exhaustion → `setTimeout(reconnect, 30000)` loop (never gives up); `rate_limited` → no red banner. |
| `mee/remotedemo/index.html` | capture loop | `FRAME_INTERVAL_MS = 100`, `MIN_SEND_GAP_MS = 90`. |
| `mee/remotedemo/index.html` | token card | No auto-fetch; static instruction "enter the token provided by your operator". |
| `mee/remotedemo/https_server.py` | (new file) | stdlib `http.server` + `ssl` context, serves `index.html` on 0.0.0.0:8443 with self-signed cert. |
| `mee-ws-watchdog.sh` | (new file) | `while true; do ss -tlnp | grep -q ':8910 ' || restart; sleep 5; done`. |
| `mee-remotedemo-start.sh` | steps `[1/4]`–`[4/4]` | Cert gen → WS → HTTPS page → funnel → watchdog; labeled PUBLIC vs TAILNET URLs; prints token once. |
| `docs/remotedemo/ACCESS.md` | full doc | Public funnel URL as primary; manual token entry; reconnect/troubleshooting notes. |
| `docs/remotedemo/DEPLOYMENT.md` | full doc | 4-component model, stop/restart incl. watchdog, stability section, troubleshooting rows for 1006 / rate-limit / watchdog. |

## 5. Acceptance Criteria

1. `https://jetson-agx.tail0d394d.ts.net/` returns the client page (HTTP 200)
   from a device **without** Tailscale installed. ✅ verified 2026-09-28
2. `wss://jetson-agx.tail0d394d.ts.net/` upgrades to WebSocket and streams
   frames/audio; results render. ✅ verified (repeated tester sessions)
3. No `GET /token` route on the server; page contains no fetch of a token
   endpoint. ✅
4. Client tolerates transient 1006 closes: reconnects, resumes streaming,
   never shows "server error" for `rate_limited`. ✅ (code + tester report
   "it seems good now")
5. If the WS process dies, the watchdog restarts it within ~5 s and the
   client reconnects without operator action. ✅ (watchdog log: 14:36/14:38
   restarts, client re-authenticated 14:39:55)
6. Every server start logs `TASK_MEE_034 server started pid=...` to
   `/tmp/mee-ws.log` and the audit log. ✅
7. `MEE_DEMO_MAX_THREADS` default `2` is applied in `run_server()` before
   engine construction; override honored. ✅ (code)
8. Server survived ≥ 20 min continuous with active tester traffic after
   reboot (pid 1818, 13:44 → 14:44, 3 auth_success cycles, clean closes). ✅
9. Docs: ACCESS.md + DEPLOYMENT.md describe the 4-component stack, manual
   token entry, watchdog, and stop/restart. ✅ (this update)

## 6. Open Items (not blockers for G3 review)

- **External SIGKILL source unidentified.** Evidence so far: no dmesg OOM,
  all `oom_kill` counters 0, process RSS only ~23 MB, killed in bursts
  correlated with CPU-heavy inference + concurrent ollama (qwen3.8:27b,
  ~36 GB) load. Mitigations in place (thread cap 2, watchdog, signal
  diagnostics). Next evidence needed: a kill that shows
  `TASK_MEE_035 received signal ...` in ws log (rules in SIGTERM/SIGINT)
  vs. silence (SIGKILL) + journalctl window capture.
- Consider (if still needed): `nvpmodel` power-mode pinning, or moving
  inference off the OpenClaw cgroup, to further isolate the MEE server.
