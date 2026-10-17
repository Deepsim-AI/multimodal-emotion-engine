# Implementation Evidence — TASK_MEE_035

**Task ID:** TASK_MEE_035
**Gate:** G2 — Implementation (evidence)
**Date:** 2026-10-16
**Implemented By:** Implementer 💻

---

## 1. Control-plane fix (root cause) — verified

The WS 500 was a **Pangolin `meews` target misconfiguration**, not a code bug.

- **Before:** `targets` table (VPS `db.sqlite`) → `targetId 5 … method=HTTPS, port=8910, internalPort=40065`.
- **After (dashboard change, confirmed by re-reading the DB):** `targetId 5 … method=http, port=8910, internalPort=40843`.
- Local backend unchanged and healthy: `http://127.0.0.1:8910/healthz` → `200 {"status":"ok"}`;
  WS upgrade over plaintext → `101`; probe token → `{"type":"error","code":"bad_token"}`.

## 2. Code changes (this repo)

### `mee/remotedemo/index.html`
- `funnelAutoConfig()` — default Server URL now `MEE_WS_PUBLIC = "wss://meews.deepsim.ai:8443/"`.
- New branch for hosts `meews.deepsim.ai` / `mee.deepsim.ai` → pre-fill the public WS URL.
- Dead `wss://jetson-agx.tail0d394d.ts.net/` default removed (kept only as a legacy guard).
- Placeholder → `wss://meews.deepsim.ai:8443  (or ws://localhost:8910)`.
- Verified: inline `<script>` passes `node --check`; no `tail0d394d` default remains.

### `mee-remotedemo-start.sh`
- Now **3 steps** (WS server → HTTPS page → watchdog). `tailscale funnel 8910` removed from the
  default path (documented as legacy fallback only).
- Idempotent: `pkill`s any existing instance before (re)starting each service.
- Prints the new public URLs (`mee.deepsim.ai:8443`, `meews.deepsim.ai:8443`) + token.
- Adds a **live check**: `curl /healthz` on local `8910` and public `meews.deepsim.ai:8443`.
- Verified: `bash -n` clean.

### `mee-ws-watchdog.sh`
- Header note: public reachability is via Pangolin (`meews.deepsim.ai`), not Funnel; the
  watchdog only keeps the local `127.0.0.1:8910` listener alive.
- Verified: `bash -n` clean.

### Docs
- `docs/remotedemo/ACCESS.md` — primary page URL `https://mee.deepsim.ai:8443/`; WS auto-filled
  to `wss://meews.deepsim.ai:8443/`; Funnel marked deprecated.
- `docs/remotedemo/DEPLOYMENT.md` — architecture diagram, Step 4 (Funnel) marked legacy, Step 5
  URLs, stop/restart, troubleshooting table → Pangolin.
- `docs/remotedemo/SECURITY.md` — all Funnel/VPS references → Pangolin / legacy.
- `CHANGELOG.md` — TASK_MEE_035 entry added under `[Unreleased]`.

## 3. Verification (live, 2026-10-16)

| Check | Command | Result |
|-------|---------|--------|
| Public WS health | `curl -sk https://meews.deepsim.ai:8443/healthz` | `200 {"status":"ok"}` |
| Public WS handshake | `websockets.connect("wss://meews.deepsim.ai:8443/")` | **CONNECT OK** |
| Auth gate intact | probe `auth` with `probe` token | `{"type":"error","code":"bad_token"}` |
| Served page default | `curl -sk https://meews.deepsim.ai:8443/ \| grep MEE_WS_PUBLIC` | `wss://meews.deepsim.ai:8443/` |
| JS syntax | `node --check` on inline script | OK |
| Shell syntax | `bash -n` start.sh / watchdog.sh | OK |
| No stale default | `grep 'urlEl.value = .*tail0d394d' index.html` | none |

## 4. Commit / push

- Committed as `3f63356 TASK_MEE_035: migrate remote demo public access to Pangolin (meews.deepsim.ai)`.
- Merged remote `3ef40ed` (TASK_MEE_016) → merge commit `72f383c`; conflicts resolved (kept HEAD
  superset; preserved remote MediaPipe work).
- Pushed to `origin/master` → `3ef40ed..72f383c`; working tree clean.
