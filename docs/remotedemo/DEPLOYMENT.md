# TASK_MEE_014 Subtask 3: Deployment — MEE Remote Demo

Deployment guide for the MEE Remote Browser Demo on the controlled Jetson.

## Overview

- Local WebSocket server: `127.0.0.1:8910` (configurable via `MEE_DEMO_PORT`)
- Public entrypoint: Tailscale Funnel (HTTPS) → local port 8910
- Static client: `mee/remotedemo/index.html` (single file, served by any static host)
- Auth: shared access token (auto-generated on first boot, stored in
  `~/.config/mee-remotedemo/token`, mode 0600)
- Audit log: `~/.config/mee-remotedemo/auth.log` (rotated daily, 14 days kept)

## Prerequisites

1. Jetson reachable from the operator's machine
2. Tailscale installed and logged in on the Jetson (`tailscale status`)
3. The `websockets` Python package (>= 12) available in the MEE venv
4. A Tailscale account that permits Funnel (individual or team — both work)

## Step 1 — Verify Python environment

```bash
cd /home/deepsim/multimodal-emotion-engine
python3 -c "import websockets, print(websockets.__version__)" \
  || pip install websockets
```

## Step 2 — Generate a token (or let the server auto-generate)

On first boot the server creates `~/.config/mee-remotedemo/token`.
To pre-generate:

```bash
python3 -c "import secrets,pathlib; p=pathlib.Path.home()/'.config/mee-remotedemo'; p.mkdir(parents=True,exist_ok=True); t=p/'token'; t.write_text(secrets.token_hex(32)+'\n'); import os; os.chmod(t,0o600); print(t.read_text().strip())"
```

Record the token — it is the **only** credential you share with the remote tester.

## Step 3 — Run the server (foreground)

```bash
cd /home/deepsim/multimodal-emotion-engine
python3 -m mee.remotedemo.server
```

The server binds to `127.0.0.1:8910` by default. Override via:

```bash
MEE_DEMO_HOST=127.0.0.1 MEE_DEMO_PORT=8910 python3 -m mee.remotedemo.server
```

## Step 4 — Expose via Tailscale Funnel

```bash
tailscale funnel --https 443:8910
```

Tailscale prints the public HTTPS URL (e.g. `https://<hash>.tryfunnel.com`).
That URL terminates TLS and proxies WebSocket upgrades to `127.0.0.1:8910`.

> Note: `tailscale funnel` requires a Tailscale account that has Funnel
> enabled. Both individual and team accounts support it. If your account
> does not, use the fallback path in Step 5.

## Step 5 — Fallback: reverse proxy through a VPS (for restricted networks)

If the Funnel URL is unreachable from the tester's network (e.g. China
GFW), route through a VPS on the tailnet (e.g. contabo-vps at
`100.125.76.28`) using an SSH reverse tunnel or an nginx WebSocket proxy.

### Option A — SSH reverse tunnel (no nginx needed)

On the VPS:

```bash
# Allow reverse tunnels
sshd_config:  AllowTcpForwarding yes
```

From the Jetson, open a reverse tunnel:

```bash
ssh -R 0.0.0.0:8910:127.0.0.1:8910 user@contabo-vps
```

Then on the VPS, add an nginx server block:

```nginx
server {
    listen 443 ssl http2;
    server_name mee.example.com;
    # ... ssl_certificate / ssl_certificate_key ...

    location / {
        proxy_pass http://127.0.0.1:8910;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 1d;
    }
}
```

### Option B — Tailscale Serve on the VPS

```bash
# On the VPS (inside the same tailnet):
tailscale serve --bg --https 443 --set-path /  127.0.0.1:8910
```

Then share the resulting HTTPS URL.

## Step 6 — Serve the browser client

The client is a single static file at `mee/remotedemo/index.html`.
Any of the following works:

### a) Python (simplest)

```bash
cd /home/deepsim/multimodal-emotion-engine/mee/remotedemo
python3 -m http.server 8080
```

### b) Nginx (recommended for VPS path)

```nginx
server {
    listen 443 ssl http2;
    server_name mee.example.com;
    root /home/deepsim/multimodal-emotion-engine/mee/remotedemo;
    index index.html;
    # ... ssl cert ...

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

Then in the browser client, set the server URL to
`wss://mee.example.com/ws`.

## Step 7 — Hand off to the remote tester

Give the tester:

1. The public URL (e.g. `https://mee.example.com/`)
2. The access token (from `~/.config/mee-remotedemo/token`)
3. Instructions to open the URL, paste the token, grant camera + mic, and press **Start Test**

See `docs/remotedemo/ACCESS.md` for the tester-facing procedure.

## systemd service (optional, for autostart)

Create `/etc/systemd/system/mee-remotedemo.service`:

```ini
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
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mee-remotedemo
journalctl -u mee-remotedemo -f
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Browser says "Not secure" | Verify the public URL is HTTPS (Funnel or nginx). getUserMedia requires HTTPS. |
| `auth_timeout` | Token mismatch or network delay > 5s. Verify token; check `auth.log`. |
| `rate_limited` | Client sending > 15 FPS. Lower the client capture rate or raise `MEE_DEMO_MAX_FPS`. |
| `payload_too_large` | Client sending oversized frames/audio. Cap capture resolution. |
| No results | Engine not loaded. Check `journalctl -u mee-remotedemo` for import errors. |
| China unreachable | Use the fallback VPS path (Step 5). |

## Security notes

- The token is the **only** credential. Rotate by deleting `~/.config/mee-remotedemo/token` and restarting the server (a new one is generated).
- The server binds to `127.0.0.1` by default — it is not reachable from the LAN without a tunnel.
- All auth outcomes are logged to `auth.log` with client IP and timestamp.
- Source code, model weights, and the Jetson filesystem are never exposed to the tester.
