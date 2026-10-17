# MEE Remote Demo — Deployment Guide

Deploy the Multimodal Emotion Engine remote browser demo on your Jetson.

## Quick overview (TL;DR)

```
Browser ──(HTTPS)──► me.deepsim.ai:8443   (HTML client page, self-signed cert)
            │
            └──(WSS)──► meews.deepsim.ai:8443 ──(Pangolin/gerbil)──► Jetson:8910
                                                                            (MEE WS, 127.0.0.1 only)
```

**TASK_MEE_035 (2026-10-16):** The public path is now served by **Pangolin**
(the `meews` resource on the `deepsim.ai` domain), not Tailscale Funnel.
Tailscale Funnel remains available as a **legacy fallback** but is not the
primary path and is not started by default.

**You need two things running on the Jetson:**
1. **WebSocket server** (port 8910, plain HTTP, loopback only)
2. **HTTPS static page** (port 8443, self-signed cert — required for camera/mic)

**Public reachability** is provided by the Pangolin site + `meews` resource on
the VPS (configured in the Pangolin dashboard). It is **not** a process on the
Jetson. To verify, open `https://meews.deepsim.ai:8443/healthz` and expect
`200 {"status":"ok"}`.

The simplest deployment method is the one-shot script described below.

---

## Quick start — all on one Jetson

> This is the simplest path: server + client + public URL all running on your Jetson.
> Follow Steps 1–2 in order. Use the helper script (recommended) or run each service manually.

### One-shot (recommended)

From a terminal on the Jetson, run:

```bash
cd /home/deepsim/multimodal-emotion-engine
bash mee-remotedemo-start.sh
```

This starts all three services and prints your access token + URLs.

> **2026-10-17 — voice runs in a separate worker process.** On this Jetson,
> loading the SpeechBrain/torch voice runtime and the MediaPipe vision runtime
> in the *same* process segfaults (native C-runtime collision). The demo
> therefore launches voice in its own subprocess (`mee/voice/voice_worker.py`,
> driven by the engine via `mee/voice/voice_worker_client.py`) so **camera and
> mic recognition are both available at once.** The script exports
> `MEE_VOICE_ENABLED=1` (both channels on). Set it to `0` to disable voice.
> The worker is spawned lazily on the first audio message and cleaned up on
> engine shutdown / server stop.

### Manual steps

#### Prerequisites

- Tailscale installed and logged in on the Jetson (`tailscale status` shows peers)
- Python 3.8+ with the `websockets >= 12` package:

```bash
python3 -c "import websockets; print(websockets.__version__)" || pip install websockets
```

#### Step 1 — Start the WebSocket server (creates token automatically)

```bash
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server > /tmp/mee-ws.log 2>&1 &
```

The server starts on `127.0.0.1:8910` and auto-generates an access token at `~/.config/mee-remotedemo/token`.

> **Tip (background mode):** The script does this for you. For manual background:
> ```bash
> cd /home/deepsim/multimodal-emotion-engine
> nohup python3 -m mee.remotedemo.server > /tmp/mee-ws.log 2>&1 &
> echo $!   # note this PID for stopping later
> ```

#### Step 2 — Generate the HTTPS cert (if not already present)

```bash
openssl req -x509 -newkey rsa:4096 -nodes -sha256 \
  -keyout /tmp/mee-key.pem -out /tmp/mee-cert.pem \
  -subj "/CN=jetson-agx" -days 365 2>/dev/null
```

The cert is only needed if you haven't run the helper script yet. The script auto-generates it on first run.

#### Step 3 — Start the HTTPS client page

```bash
cd /home/deepsim/multimodal-emotion-engine/mee/remotedemo
python3 https_server.py &
```

This serves the HTML demo page over **HTTPS** on port **8443**. HTTPS is mandatory because browsers require a secure context to grant camera/mic permissions via `getUserMedia()`.

#### Step 4 — (Optional) Tailscale Funnel — legacy fallback only

> **TASK_MEE_035 (2026-10-16):** This step is **deprecated**. Public access is
> now via Pangolin (`meews.deepsim.ai:8443`). Only run Funnel if Pangolin is
> down and you need an alternative public path for a specific tester on a
> restricted network.

From another terminal:

```bash
cd /home/deepsim/multimodal-emotion-engine
tailscale funnel 8910 > /tmp/mee-funnel.log 2>&1 &
```

This publishes your WebSocket server publicly via Tailscale's TLS termination
on the `*.ts.net` host. It is **not** the primary path anymore.

> `tailscale funnel` automatically terminates TLS and proxies WebSocket connections to your local `127.0.0.1:8910`. No nginx, no certificates needed for the WebSocket side.

#### Step 5 — Share access info with testers

Give the tester these three things:

1. **The page URL (HTTPS):**
   ```
   https://mee.deepsim.ai:8443/          (PUBLIC — primary, via Pangolin)
   https://jetson-agx:8443/              (tailnet — legacy fallback)
   ```
   Tell them to accept the self-signed cert warning when prompted.

2. **The WebSocket server URL (auto-filled by the page — no manual entry needed):**
   ```
   wss://meews.deepsim.ai:8443/          (via Pangolin; primary)
   ```

3. **The access token:**
   ```bash
   cat ~/.config/mee-remotedemo/token
   ```

4. **Instructions to:**
   - Open the page URL in their browser (Chrome recommended)
   - Accept the self-signed cert warning
   - Paste the WebSocket server URL and access token on the page
   - Grant camera + microphone permissions when prompted
   - Press **Start Test**

See `docs/remotedemo/ACCESS.md` for detailed tester-facing instructions.

> **Important:** The tester's browser must reach the WebSocket server over HTTPS
> (Pangolin provides this on `meews.deepsim.ai`). They cannot connect to
> `ws://127.0.0.1:8910` directly — that only works if their browser is running
> on the same machine as the server.

---

## Stopping, restarting, and restarting after a reboot

These servers are **not** installed as system services for the prototype — they are plain background processes and will **not** survive a reboot. You start them manually each time you want to test (or via the helper script below).

### Stop everything (quick)

> **2026-10-16 fix — use the stop script.** On this aarch64 Jetson the old
> `pkill` bracket-idiom patterns silently failed to match the real processes,
> which stacked stale watchdogs and left a stale server in charge. The scripts
> now use **PID files** (`.run/*.pid`) + port release (`fuser -k`), which are
> exact. Use this:

```bash
bash /home/deepsim/multimodal-emotion-engine/mee-remotedemo-stop.sh
```

The stop script kills the **watchdog first** (it respawns the WS server), then
the WS server and HTTPS page by PID, then releases ports 8910/8443 no matter
who holds them, and prints any remaining MEE processes.

<details>
<summary>Manual / legacy pkill (last resort only)</summary>

```bash
pkill -f 'mee-ws-watchdo[g]d'         # watchdog FIRST (else it respawns the server)
pkill -f 'mee.remote[d]emo.server'    # WebSocket server (port 8910)
pkill -f 'remote[d]emo/https_server'  # HTTPS static page (port 8443)
```

Verify nothing is left running:

```bash
pgrep -af 'watchdo[g]d'               || echo "watchdog: stopped"
pgrep -af 'remote[d]emo.server' || echo "ws server: stopped"
pgrep -af 'https_server'          || echo "page server: stopped"
ss -tlnp | grep -E '8910|8443'   || echo "ports free"
```

> The `[d]` in the pattern is a trick: it prevents `pkill` from matching its *own* command line (which also contains the string), avoiding a self-kill. **On this host these bracket patterns can mis-match** — prefer the stop script above.

</details>

> **Order matters:** stop the **watchdog first**. If the watchdog is still running when you kill the WS server, it will detect the missing listener within ~5 s and respawn it.

## Stability & resilience (TASK_MEE_018)

The public path (browser → Tailscale edge → funnel → Jetson) is long, and on this Jetson the WS server has been observed dying under CPU/memory pressure. Three layers of defense are in place so a single death does not take the demo down:

1. **Watchdog** (`mee-ws-watchdog.sh`) — started by `mee-remotedemo-start.sh` (step 4/4). Polls every 5 s; if `ss -tlnp` no longer shows `:8910`, it restarts `python3 -m mee.remotedemo.server`. Log: `/tmp/mee-ws-watchdog.log`. In production runs the client re-authenticates within ~30 s of a kill (verified 2026-09-28 14:38→14:39).
2. **Client reconnect** — `index.html` retries up to 12 times with backoff, then retries every 30 s **forever**. Close code 1006 (abnormal) is treated as transient, and `rate_limited` responses no longer raise the red "Server Error" banner.
3. **CPU thread cap** — `run_server()` sets `OMP_NUM_THREADS` / `OPENBLAS_NUM_THREADS` / `MKL_NUM_THREADS` / `VECLIB_MAXIMUM_THREADS` / `NUMEXPR_NUM_THREADS` to `MEE_DEMO_MAX_THREADS` (default **2**) before the engine is constructed, taming the inference CPU spikes on the shared Jetson. Override per-run: `MEE_DEMO_MAX_THREADS=4 python3 -m mee.remotedemo.server` (`0` = library default).

**Diagnostics for a suspected kill:**

```bash
grep -E 'TASK_MEE_034|TASK_MEE_035' /tmp/mee-ws.log     # every start (pid) + any SIGTERM/SIGINT/SIGABRT
tail -20 /tmp/mee-ws-watchdog.log                        # external kills + restarts
journalctl --since '10 min ago' | grep -viE 'llama|ollama' | grep -iE 'kill|oom|cgroup|memory' | tail
dmesg | grep -iE 'oom|killed process'                    # kernel OOM (expected: empty)
```

If a kill leaves **no** `TASK_MEE_035` line, the process received SIGKILL (uncatchable) — correlate the watchdog timestamp with `journalctl` for that minute.

### Stop a specific process by PID (if you have the PID)

```bash
kill <PID>          # graceful
kill -9 <PID>       # force, if it won't die
```

Find the PID with `pgrep -f 'remote[d]emo.server'` or `ss -tlnp | grep 8910`.

### Restart (stop, then start again)

```bash
# stop + start (recommended — exact PID/port cleanup)
bash ~/multimodal-emotion-engine/mee-remotedemo-stop.sh
bash ~/multimodal-emotion-engine/mee-remotedemo-start.sh
```

<details>
<summary>Manual restart (two services, no watchdog)</summary>

```bash
# stop
pkill -f 'mee.remote[d]emo.server'
pkill -f 'https_server'
sleep 1
# start
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server &
(cd mee/remotedemo && python3 https_server.py) &
```

</details>

### Restart after the PC/Jetson reboots

Since the servers are not auto-started, bring them back up manually after any reboot. Two options:

**Option A — the helper script (recommended, does all four in one command):**

```bash
~/multimodal-emotion-engine/mee-remotedemo-start.sh
```

This starts the WS server and the HTTPS static page, then prints your access
token and all the URLs. It is test-only — it does not install anything on boot.
Public reachability is via Pangolin (`meews.deepsim.ai`) — not started here.

**Option B — manually, three terminals:**

```bash
# Terminal 1 — WebSocket server
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server

# Terminal 2 — HTTPS static page (requires /tmp/mee-cert.pem + /tmp/mee-key.pem)
cd /home/deepsim/multimodal-emotion-engine/mee/remotedemo
python3 https_server.py

# Terminal 3 — Tailscale Funnel (LEGACY fallback only — usually not needed)
# Only if Pangolin is down and you need an alternative public path:
tailscale funnel 8910
```

The access token is **persistent** — it lives in `~/.config/mee-remotedemo/token` and is re-read on every start, so it does **not** change across reboots. You only get a new token if you delete that file (see Rotation below).

### Rotate the token (generate a fresh one)

```bash
pkill -f 'mee.remote[d]emo.server'
rm ~/.config/mee-remotedemo/token
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server &   # a new hex token is generated
sleep 1
cat ~/.config/mee-remotedemo/token   # share this new value
```

---

## Fallback paths

Use these if Tailscale Funnel doesn't work for your tester (e.g., blocked by firewall, or the tester is on a restricted network like mainland China).

### Option A — Share `index.html` directly + alternate WebSocket endpoint

If Funnel is unavailable but you still need testers to run the demo:

1. Copy `mee/remotedemo/index.html` to any HTTPS static host (GitHub Pages, an nginx VPS, etc.)
2. Have the tester point the page's server URL field to a different WebSocket endpoint (see Option B)

This doesn't solve the network reachability problem — it only gets the HTML file onto the tester's machine. The real fix is getting the WebSocket traffic through.

### Option B — Reverse proxy via a VPS in your Tailscale tailnet

When the Funnel URL is unreachable from the tester's network (common with mainland China firewalls), route through a VPS on the same tailnet.

#### On the VPS — allow reverse tunnels

Edit `/etc/ssh/sshd_config` and set:
```
AllowTcpForwarding yes
```
Then restart sshd: `sudo systemctl restart sshd`

#### From the Jetson — open a reverse tunnel

```bash
ssh -N -R 0.0.0.0:8910:127.0.0.1:8910 user@contabo-vps
```

Keep this session alive. It tunnels port 8910 from the VPS back to your Jetson.

#### On the VPS — configure nginx for WebSocket proxy + HTTPS page

Add to `/etc/nginx/sites-available/mee`:
```nginx
server {
    listen 443 ssl http2;
    server_name mee.example.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /ws {
        proxy_pass http://127.0.0.1:8910;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 1d;
    }

    # Also serve the HTML client page (must be HTTPS for camera/mic)
    location / {
        root /path/to/mee/remotedemo;   # where index.html lives
        try_files $uri $uri/ =404;
    }
}
```

Then in the HTML client, set the server URL to `wss://mee.example.com/ws`.

> **This is complex.** Only follow this if Option A won't work. The VPS needs a domain, SSL cert (use `certbot`), and nginx installed.

---

## Optional: Auto-start the servers with systemd

For production use, install the servers as system services so they survive reboots:

### WebSocket server

```bash
sudo tee /etc/systemd/system/mee-remotedemo.service > /dev/null << 'EOF'
[Unit]
Description=MEE Remote Demo WebSocket server
After=network.target

[Service]
WorkingDirectory=/home/deepsim/multimodal-emotion-engine
ExecStart=/usr/bin/python3 -m mee.remotedemo.server
Environment=MEE_DEMO_HOST=127.0.0.1
Environment=MEE_DEMO_PORT=8910
Restart=on-failure
User=deepsim

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now mee-remotedemo
journalctl -u mee-remotedemo -f
```

### HTTPS client page (separate service)

First generate the cert if it doesn't exist:
```bash
openssl req -x509 -newkey rsa:4096 -nodes -sha256 \
  -keyout /tmp/mee-key.pem -out /tmp/mee-cert.pem \
  -subj "/CN=jetson-agx" -days 365 2>/dev/null
```

Then create the service:
```bash
sudo tee /etc/systemd/system/mee-remotedemo-page.service > /dev/null << 'EOF'
[Unit]
Description=MEE Remote Demo HTTPS client page
After=network.target mee-remotedemo.service

[Service]
WorkingDirectory=/home/deepsim/multimodal-emotion-engine/mee/remotedemo
ExecStart=/usr/bin/python3 https_server.py --certfile /tmp/mee-cert.pem --keyfile /tmp/mee-key.pem
Restart=on-failure
User=deepsim

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now mee-remotedemo-page.service
journalctl -u mee-remotedemo-page.service -f
```

The token is auto-generated on first start (same as Step 2 above).

---

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| **"WebSocket connection failed" in browser** | Make sure the WS URL is `wss://meews.deepsim.ai:8443/` (Pangolin), not `ws://`. Browsers require WSS on HTTPS pages. |
| **No permission prompt / "Permission denied or no devices: TypeError"** | The page was loaded over `http://` instead of `https://`. Camera/mic requires a secure context. Access via `https://mee.deepsim.ai:8443/` (Pangolin) or `https://jetson-agx:8443/` (tailnet). Accept the self-signed cert warning first. |
| **Browser shows "Not secure" for page** | This is the self-signed cert warning — click Advanced → Proceed. It's expected on a Jetson dev machine. |
| **`tailscale funnel: invalid flag` error** | *(legacy path only)* Use `tailscale funnel 8910`, not `--https 443:8910`. The primary path is now Pangolin — you shouldn't need Funnel at all. |
| **"Token expired" or auth fails** | Token mismatch. Verify `cat ~/.config/mee-remotedemo/token` matches what you told the tester. Delete and restart the server to generate a new one. |
| **No emotion results** | Engine model may not have loaded yet. Check `/tmp/mee-ws.log` for import errors, or wait 10–30 seconds after startup for the engine to initialize. |
| **Face works but "Voice Emotion — no voice data" / all-zero bars** | The voice pipeline is fine — your **mic is delivering silence**. 2026-10-17: the panel now says `🎤 mic silent (no voice energy…)` and there is a **live mic-level meter** next to the Microphone indicator. If that meter stays at 0% while you speak, the mic track is silent — most often the browser blocked `getUserMedia` on the self-signed `https://` origin. Check the address-bar padlock → site settings → Microphone = **Allowed**, ensure the correct input device is selected, and hard-reload (`Ctrl/Cmd+Shift+R`). Verify on the server: `grep 'WS-KA-audio' /tmp/mee-ws.log \| tail` — `mean_abs` near 0.0 = silent; a real voice shows `mean_abs` ~0.05+. |
| **"Server error" banner / `unknown message type 'mute'`** | 2026-10-16: fixed. The server now acks the client's `{type:"mute"}` mic-toggle message with `mute_ok` instead of erroring. If you see it again, you're running an older server — restart via `mee-remotedemo-stop.sh` + `mee-remotedemo-start.sh`. |
| **Voice recognition segfaults / server crashes on audio** | 2026-10-17: voice now runs in a **separate worker process** (`MEE_VOICE_ENABLED=1`), so the SpeechBrain/torch voice runtime no longer shares an address space with the MediaPipe vision runtime (that in-process combination segfaults this host). If it still crashes, confirm `MEE_VOICE_ENABLED` is `1` in the start script and restart. |
| **China mainland unreachable** | Funnel may be blocked by the GFW. Use the VPS fallback above. |
| **"Keep-alive" or "invalid Connection header"** | You're hitting the WebSocket server with a regular HTTP request (e.g., `http://127.0.0.1:8910/` in the browser address bar). This is expected — the server only speaks WebSocket. Use the Funnel URL and the HTML client instead. |
| **"empty Connection header" / "Failed to open a WebSocket connection"** | You connected with `ws://` (plaintext). Use `wss://meews.deepsim.ai:8443/` (Pangolin, TLS). Reserve `ws://` for same-tailnet/same-machine IPs like `ws://127.0.0.1:8910`. |
| **"Disconnected (code 1008)" / "invalid access token" / "token mismatch"** | The token in the browser does not match `~/.config/mee-remotedemo/token`. Copy the exact value with `cat ~/.config/mee-remotedemo/token` (no trailing spaces/quotes). If it still fails after a restart, a code-level token bug may be present — see the fix in `config.py` `resolve_token()` (it now keeps `self.token` in sync with the file). |
| **Server gone after reboot** | Expected — the prototype servers are not installed as system services. Re-run `~/multimodal-emotion-engine/mee-remotedemo-start.sh` (see *Stopping, restarting, and restarting after a reboot*). |
| **HTTPS page doesn't start (`[SSL: CERTIFICATE_VERIFY_FAILED]`)** | The cert/key files at `/tmp/mee-cert.pem` and `/tmp/mee-key.pem` are missing or corrupted. Re-run the openssl command in Step 2 above. |
| **"Address already in use" on port 8443** | Another process is already bound to that port. Pick a different port by editing the `--port` default in `https_server.py`. |
| **Repeated "Disconnected (code 1006)" / connect–disconnect flapping** | Transient abnormal closes through the tunnel edge. The client now auto-reconnects (12 backoff attempts, then forever every 30 s). If it flaps continuously, the WS server is likely being killed externally — check `/tmp/mee-ws-watchdog.log`, `grep TASK_MEE_035 /tmp/mee-ws.log`, and the *Stability & resilience* section above. |
| **"Server Error" banner during streaming** | If the banner text is `rate_limited`, it is benign frame-dropping (server is slower than your send rate) and the client no longer shows it. Any **other** error text is a real failure — check `/tmp/mee-ws.log`. |
| **Results stop after a kill, no reconnect** | The watchdog may be dead. `pgrep -af 'mee-ws-watchdo[g]d'` — if absent, restart it: `nohup bash ~/multimodal-emotion-engine/mee-ws-watchdog.sh &` (or just re-run `mee-remotedemo-start.sh`). |
| **`ws.log` shows `Address already in use` on 8910 after reboot** | A duplicate start attempt raced the watchdog. Harmless — the watchdog keeps the live instance; re-run `pgrep -af 'remote[d]emo.server'` to confirm exactly one server.

---

## HTTPS cert management

The self-signed cert at `/tmp/mee-cert.pem` and `/tmp/mee-key.pem` expires after 365 days. When it does, regenerate:

```bash
openssl req -x509 -newkey rsa:4096 -nodes -sha256 \
  -keyout /tmp/mee-key.pem -out /tmp/mee-cert.pem \
  -subj "/CN=jetson-agx" -days 365 2>/dev/null
```

Then restart the page server:
```bash
pkill -f 'https_server'
cd /home/deepsim/multimodal-emotion-engine/mee/remotedemo && python3 https_server.py &
```

Browser users will need to re-accept the cert warning after renewal.

---

## Security notes

- The access token is the **only** credential for this demo. No passwords, no API keys.
- Rotate the token by deleting `~/.config/mee-remotedemo/token` and restarting the server (a new one auto-generates).
- The WebSocket server binds to `127.0.0.1` by default — it is **not** reachable from your LAN without a tunnel or proxy.
- All auth events are logged to `~/.config/mee-remotedemo/auth.log` with client IP and timestamp, rotated daily (14 days kept).
- Source code, model weights, and the Jetson filesystem are never exposed to remote testers.
