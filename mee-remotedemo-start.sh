#!/usr/bin/env bash
# MEE Remote Demo — one-shot startup (test-use, no auto-start on boot).
# TASK_MEE_035 (2026-10-16): public access is now served by Pangolin/gerbil on
#   the deepsim.ai hosts (mee / meews), NOT Tailscale Funnel.  Funnel is kept
#   only as an optional legacy fallback — it is not started by default.
#
# This brings up:
#   [1] WS server          127.0.0.1:8910   (plain HTTP; auth token in server.py)
#   [2] HTTPS static page  0.0.0.0:8443     (self-signed; for camera/mic)
#   [3] watchdog           (auto-restart the WS server if it dies)
# Public reachability (browser -> internet -> Pangolin -> this host) is provided
# by the Pangolin site + meews resource on the VPS — configured in the dashboard,
# not by any process on this box.
set -euo pipefail

REPO=/home/deepsim/multimodal-emotion-engine
cd "$REPO"

# Ensure cert exists; generate if missing (needed by the 8443 page server)
if [ ! -f /tmp/mee-cert.pem ] || [ ! -f /tmp/mee-key.pem ]; then
    echo "==> Generating self-signed HTTPS cert..."
    openssl req -x509 -newkey rsa:4096 -nodes -sha256 \
      -keyout /tmp/mee-key.pem -out /tmp/mee-cert.pem \
      -subj "/CN=jetson-agx" -days 365 2>/dev/null
    echo "    cert=/tmp/mee-cert.pem key=/tmp/mee-key.pem"
fi

echo "==> [1/3] MEE WebSocket server (127.0.0.1:8910)"
# Restart cleanly if already running (idempotent re-run)
pkill -f 'mee.remote[d]emo.server' 2>/dev/null || true
sleep 1
python3 -m mee.remotedemo.server > /tmp/mee-ws.log 2>&1 &
WS_PID=$!
echo "    pid=$WS_PID  log=/tmp/mee-ws.log"

echo "==> [2/3] HTTPS static client page (0.0.0.0:8443)"
pkill -f 'remote[d]emo/https_server' 2>/dev/null || true
sleep 1
(cd "$REPO/mee/remotedemo" && python3 https_server.py) > /tmp/mee-https.log 2>&1 &
HTTP_PID=$!
echo "    pid=$HTTP_PID  log=/tmp/mee-https.log"

echo "==> [3/3] WS watchdog (auto-restart if server dies)"
if [ ! -f "$REPO/mee-ws-watchdog.sh" ]; then
    echo "    WARNING: $REPO/mee-ws-watchdog.sh missing; skipping watchdog."
else
    pkill -f 'mee-ws-watchdo[g]d' 2>/dev/null || true
    sleep 1
    (setsid nohup bash "$REPO/mee-ws-watchdog.sh" > /dev/null 2>&1 < /dev/null &)
    sleep 1
    WATCHDOG_PID=$(pgrep -f 'mee-ws-watchdo[g]d' | head -1)
    echo "    pid=${WATCHDOG_PID:-?}  log=/tmp/mee-ws-watchdog.log"
fi

sleep 2
echo
echo "==> Access token (hand to users out-of-band; NOT auto-filled on the page):"
echo "    $(cat ~/.config/mee-remotedemo/token)"
echo
echo "==> PUBLIC (any device, no Tailscale needed) — via Pangolin:"
echo "    Page:   https://mee.deepsim.ai:8443/        <- open this; type the token above"
echo "    WS:     wss://meews.deepsim.ai:8443/        <- auto-filled by the page"
echo
echo "    (legacy / tailnet fallback, only if needed):"
echo "    Page:   https://jetson-agx:8443/           ^ accept self-signed cert"
echo "    WS:     ws://127.0.0.1:8910/               (same machine only)"
echo "    Funnel: tailscale funnel 8910              (DEPRECATED — not started by default)"
echo
echo "==> Live check (should print 200):"
timeout 6 curl -s -o /dev/null -w '    local 8910 /healthz -> %{http_code}\n' http://127.0.0.1:8910/healthz 2>/dev/null || true
timeout 8 curl -sk -o /dev/null -w '    public meews /healthz -> %{http_code}\n' https://meews.deepsim.ai:8443/healthz 2>/dev/null || echo "    public meews check skipped (no network)"
echo
echo "==> Stop everything:"
echo "    pkill -f 'mee-ws-watchdo[g]d'; pkill -f 'mee.remote[d]emo.server'; pkill -f 'remote[d]emo/https_server'"
