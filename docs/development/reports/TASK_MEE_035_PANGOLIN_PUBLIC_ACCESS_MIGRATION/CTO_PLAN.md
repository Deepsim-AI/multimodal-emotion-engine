# CTO Plan — TASK_MEE_035: Remote Demo Public Access Migration to Pangolin

**Task ID:** TASK_MEE_035
**Gate:** G1 — Plan (driven by the live failure of the Tailscale-Funnel public path)
**Date:** 2026-10-16
**Planned By:** CTO / Architect (recorded by Implementer from session evidence)
**Supersedes:** TASK_MEE_018 public-access approach (Tailscale Funnel)

---

## 1. Problem Statement

The remote browser demo's **public** path was served by Tailscale Funnel
(`https://jetson-agx.tail0d394d.ts.net/` + `wss://jetson-agx.tail0d394d.ts.net/`).
On 2026-10-16 the public WebSocket was returning **`500 Internal Server Error`**
on every request (GET, `/healthz`, and the WS upgrade), while the **page** host
kept working — so testers could load the page but the WS never connected.

The public path had been migrated (out-of-band, in the Pangolin control plane)
to the `deepsim.ai` domain:

- **Page:** `https://mee.deepsim.ai:8443/`  (Pangolin resource `mee`)
- **WS:**   `wss://meews.deepsim.ai:8443/`  (Pangolin resource `meews`)

…but the **client page and all operator docs still defaulted to the dead
Tailscale-Funnel URL**, and the WS 500 had to be root-caused in the control plane.

## 2. Scope

In scope (client + operator tooling + docs; **no** MEE engine/code changes):
- `mee/remotedemo/index.html` — default Server URL → `wss://meews.deepsim.ai:8443/`;
  remove dead Funnel default; add `meews`/`mee` host branch; update placeholder.
- `mee-remotedemo-start.sh` — 3-step start (WS + page + watchdog); Funnel demoted
  to optional legacy; print new public URLs; add live `/healthz` check.
- `mee-ws-watchdog.sh` — header note (public reachability via Pangolin, not Funnel).
- `docs/remotedemo/ACCESS.md` — primary URL → `mee.deepsim.ai` / `meews.deepsim.ai`.
- `docs/remotedemo/DEPLOYMENT.md` — architecture + steps + troubleshooting → Pangolin.
- `docs/remotedemo/SECURITY.md` — Funnel/VPS references → Pangolin/legacy.
- `CHANGELOG.md` — TASK_MEE_035 entry.

Control-plane (done in the Pangolin dashboard / verified against its DB, **not** in this repo):
- `meews` target `method` corrected **`https` → `http`** (the WS backend is plain
  HTTP on `127.0.0.1:8910`); `internalPort` republished.

Out of scope:
- Any change to `server.py` auth, engine, vision/voice models.
- Replacing the self-signed page cert (`mee.deepsim.ai` still self-signed).
- systemd / boot persistence (prototype remains manual-start).

## 3. Root Cause (WS 500) — verified against the Pangolin control-plane DB

The `targets` table on the VPS showed:

```
targetId 5  (meews WS)  ip=127.0.0.1  method=HTTPS  port=8910  internalPort=40065
targetId 3  (mee  page) ip=127.0.0.1  method=HTTPS  port=8443  internalPort=40395
```

The WS backend (`python3 -m mee.remotedemo.server`) speaks **plain HTTP** on
`127.0.0.1:8910` (verified: `/healthz` → 200 and WS upgrade → **101** over
plaintext). gerbil was therefore configured to speak **TLS to a plaintext
backend** → handshake failed → `500`. The page only *appeared* fine because that
app also runs its own HTTPS listener on 8443, which the browser reaches directly;
the loopback-only WS has no such fallback.

**Fix:** set the `meews` target `method` to **`http`** (leave `port=8910`). After
the change the DB read: `targetId 5 … method=http, internalPort=40843`.

## 4. Acceptance Criteria

- [x] `GET https://meews.deepsim.ai:8443/healthz` → `200 {"status":"ok"}`.
- [x] `wss://meews.deepsim.ai:8443/` completes a WS handshake (`101`) via a real
      `websockets` client, and a probe token returns `{"type":"error","code":"bad_token"}`
      (auth gate intact — no open endpoint).
- [x] Served page (via `mee.deepsim.ai` and `meews.deepsim.ai`) carries the new
      default `MEE_WS_PUBLIC = "wss://meews.deepsim.ai:8443/"` and the page loads (HTTP 200).
- [x] No `ws://…tail0d394d.ts.net`/`wss://…tail0d394d.ts.net` **default** remains in `index.html`.
- [x] `index.html` inline JS passes `node --check`.
- [x] `bash -n` clean on `mee-remotedemo-start.sh` and `mee-ws-watchdog.sh`.
- [x] Docs (ACCESS / DEPLOYMENT / SECURITY) list Pangolin as primary; Funnel marked
      deprecated/legacy.
- [x] `CHANGELOG.md` has a TASK_MEE_035 entry.
- [x] Committed locally and pushed to `origin/master` (in sync).

## 5. Rollout / Operator Notes

- **Token** is unchanged and still out-of-band (`~/.config/mee-remotedemo/token`);
  the page no longer needs the URL typed by hand.
- **Funnel** (`tailscale funnel 8910`) is no longer started by default; it remains
  only as a legacy fallback if Pangolin is unavailable.
- The self-signed cert on `mee.deepsim.ai:8443` still requires the browser to
  accept the certificate warning — expected for this prototype.
