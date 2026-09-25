# MEE Remote Demo — Deployment Guide

Deploy the Multimodal Emotion Engine remote browser demo on your Jetson.

## Quick overview (TL;DR)

```
Browser ──(HTTPS via Tailscale Funnel)──► Jetson:8910 ──(WS)──► MEE WebSocket server
                                    (public URL)              (local only)
```

**You need two things on the Jetson:**
1. A running **WebSocket server** (port 8910, `ws://`)
2. A public HTTPS URL to reach it (Tailscale Funnel is easiest)

Everything else — token, static HTML page, auth — is handled automatically or with one-liner commands below.

---

## Prerequisites

- Jetson reachable from the operator's machine
- Tailscale installed and logged in on the Jetson (`tailscale status` shows peers)
- A Tailscale account that permits Funnel (individual or team accounts both work)
- Python 3.8+ with the `websockets >= 12` package (see Step 1)

---

## Quick start — all on one Jetson

> This is the simplest path: server + client + public URL all running on your Jetson.
> Follow Steps 1–7 in order. Each step depends on the previous one completing.

### Step 1 — Ensure Python and websockets are ready

```bash
cd /home/deepsim/multimodal-emotion-engine
python3 -c "import websockets; print(websockets.__version__)" || pip install websockets
```

If this prints a version number (e.g. `12.0`), you're good. If it installs `websockets`, that's also fine.

### Step 2 — Start the WebSocket server (creates token automatically)

```bash
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server
```

**What just happened:** The server started on `127.0.0.1:8910` and auto-generated an access token at `~/.config/mee-remotedemo/token`. That token is the only credential you'll share with remote testers.

> **Note:** "First boot" in earlier docs meant "the first time you start the server." You don't need to reboot the Jetson — just running the command above is sufficient. If the token file already exists from a previous run, the server reuses it; delete `~/.config/mee-remotedemo/token` and restart if you want a new one.

Keep this terminal open — the server runs in the foreground. You'll open another terminal or SSH session for the remaining steps.

> **Tip (background mode):** To run it in the background instead of tied to a terminal:
> ```bash
> cd /home/deepsim/multimodal-emotion-engine
> nohup python3 -m mee.remotedemo.server > /tmp/mee-ws.log 2>&1 &
> echo $!   # note this PID for stopping later
> ```
> Logs go to `/tmp/mee-ws.log`; check with `tail -f /tmp/mee-ws.log`.

### Step 3 — Open the public URL with Tailscale Funnel

From **another terminal** (or a new SSH session on the same Jetson):

```bash
cd /home/deepsim/multimodal-emotion-engine
tailscale funnel 8910
```

Tailscale prints a public HTTPS URL like:

```
https://<hash>.tryfunnel.com
```

**Write this down.** It's the address remote testers will visit.

> `tailscale funnel` automatically terminates TLS and proxies WebSocket connections to your local `127.0.0.1:8910`. No nginx, no certificates, no VPS needed.

### Step 4 — Start the static client (the HTML page)

The browser demo is a single file at `mee/remotedemo/index.html`. Serve it with Python's built-in HTTP server:

```bash
cd /home/deepsim/multimodal-emotion-engine/mee/remotedemo
python3 -m http.server 8080
```

This serves the page on `http://localhost:8080` locally. To access it remotely, add Funnel for port 8080 as well, or just open the HTML file directly in your browser (see Step 5).

### Step 5 — Connect the remote tester

Give the tester these three things:

1. **The public URL** from Step 3 (e.g. `https://<hash>.tryfunnel.com`)
2. **The access token** from `~/.config/mee-remotedemo/token`:
   ```bash
   cat ~/.config/mee-remotedemo/token
   ```
3. **Instructions to:**
   - Open the public URL in their browser (Chrome/Firefox/Safari)
   - Paste the access token into the field on the page
   - Grant camera + microphone permissions when prompted
   - Press **Start Test**

See `docs/remotedemo/ACCESS.md` for detailed tester-facing instructions.

> **Important:** The tester's browser must reach the WebSocket server over HTTPS (Tailscale Funnel provides this). They cannot connect to `ws://127.0.0.1:8910` directly — that only works if their browser is running on the same machine as the server.

---

## Stopping, restarting, and restarting after a reboot

These servers are **not** installed as system services for the prototype — they are plain background processes and will **not** survive a reboot. You start them manually each time you want to test (or via the helper script below).

### Stop everything (quick)

```bash
pkill -f 'mee.remote[d]emo.server'   # WebSocket server (port 8910)
pkill -f 'http.server 8082'          # static page (port 8082)
pkill -f 'tailscale funnel 8910'     # Tailscale Funnel
```

Verify nothing is left running:

```bash
pgrep -af 'remote[d]emo.server' || echo "ws server: stopped"
pgrep -af 'http.server 8082'    || echo "http server: stopped"
ss -tlnp | grep -E '8910|8082'  || echo "ports free"
```

> The `[d]` in the pattern is a trick: it prevents `pkill` from matching its *own* command line (which also contains the string), avoiding a self-kill.

### Stop a specific process by PID (if you have the PID)

```bash
kill <PID>          # graceful
kill -9 <PID>       # force, if it won't die
```

Find the PID with `pgrep -f 'remote[d]emo.server'` or `ss -tlnp | grep 8910`.

### Restart (stop, then start again)

```bash
# stop
pkill -f 'mee.remote[d]emo.server'
sleep 1
# start
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server &
```

### Restart after the PC/Jetson reboots

Since the servers are not auto-started, bring them back up manually after any reboot. Two options:

**Option A — the helper script (recommended, does all three in one command):**

```bash
~/multimodal-emotion-engine/mee-remotedemo-start.sh
```

This starts the WS server, the static page, and the Tailscale Funnel, then prints your access token and all the URLs. It is test-only — it does not install anything on boot.

**Option B — manually, three terminals:**

```bash
# Terminal 1 — WebSocket server
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server

# Terminal 2 — static page
cd /home/deepsim/multimodal-emotion-engine/mee/remotedemo
python3 -m http.server 8082

# Terminal 3 — Tailscale Funnel (only if you need the remote URL)
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

### Option A — Simplest fallback: share `index.html` directly

If Funnel is unavailable but you still need testers to run the demo:

1. Copy `mee/remotedemo/index.html` to any static host (GitHub Pages, an nginx VPS, etc.)
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

#### On the VPS — configure nginx for WebSocket proxy

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
}
```

Then in the HTML client, set the server URL to `wss://mee.example.com/ws`.

> **This is complex.** Only follow this if Option A won't work. The VPS needs a domain, SSL cert (use `certbot`), and nginx installed.

---

## Optional: Auto-start the server with systemd

For production use, install the server as a system service so it survives reboots:

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

Check the service status with `systemctl status mee-remotedemo`. The token is auto-generated on first start (same as Step 2 above).

---

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| **"WebSocket connection failed" in browser** | Make sure the Funnel URL is `https://`, not `http://`. Browsers block `ws://` on HTTPS pages. |
| **Browser says "Not secure"** | getUserMedia (camera/mic) requires HTTPS. Verify your public URL uses https:// |
| **`tailscale funnel: invalid flag` error** | Use `tailscale funnel 8910`, not `--https 443:8910`. The correct syntax is just the port number. |
| **"Token expired" or auth fails** | Token mismatch. Verify `cat ~/.config/mee-remotedemo/token` matches what you told the tester. Delete and restart the server to generate a new one. |
| **No emotion results** | Engine model may not have loaded yet. Check `journalctl -u mee-remotedemo` for import errors, or wait 10–30 seconds after startup for the engine to initialize. |
| **China mainland unreachable** | Funnel may be blocked by the GFW. Use the VPS fallback in Step 5 above. |
| **"Keep-alive" or "invalid Connection header"** | You're hitting the WebSocket server with a regular HTTP request (e.g., `http://127.0.0.1:8910/` in the browser address bar). This is expected — the server only speaks WebSocket. Use the Funnel URL and the HTML client instead. |
| **"empty Connection header" / "Failed to open a WebSocket connection"** | You connected with `ws://` (plaintext) to the **Tailscale Funnel** endpoint, which is TLS/HTTPS only. Use `wss://jetson-agx.tail0d394d.ts.net/` (no port). Reserve `ws://` for same-tailnet IPs like `ws://100.97.141.103:8910`. |
| **"Disconnected (code 1008)" / "invalid access token" / "token mismatch"** | The token in the browser does not match `~/.config/mee-remotedemo/token`. Copy the exact value with `cat ~/.config/mee-remotedemo/token` (no trailing spaces/quotes). If it still fails after a restart, a code-level token bug may be present — see the fix in `config.py` `resolve_token()` (it now keeps `self.token` in sync with the file). |
| **"Address already in use" (OSError 98) on the static page** | Another process is already bound to that port (e.g. Open WebUI on 8080). Pick a free port, e.g. `python3 -m http.server 8082`. |
| **Server gone after reboot** | Expected — the prototype servers are not installed as system services. Re-run `~/multimodal-emotion-engine/mee-remotedemo-start.sh` (see *Stopping, restarting, and restarting after a reboot*). |
| **`BrokenPipeError` in the `http.server` log** | Harmless — the browser cancelled the response mid-transfer (page reload/navigation). Ignore unless requests are actually failing. |

---

## Security notes

- The access token is the **only** credential for this demo. No passwords, no API keys.
- Rotate the token by deleting `~/.config/mee-remotedemo/token` and restarting the server (a new one auto-generates).
- The server binds to `127.0.0.1` by default — it is **not** reachable from your LAN without a tunnel or proxy.
- All auth events are logged to `~/.config/mee-remotedemo/auth.log` with client IP and timestamp, rotated daily (14 days kept).
- Source code, model weights, and the Jetson filesystem are never exposed to remote testers.
