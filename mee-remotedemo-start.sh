#!/usr/bin/env bash
# MEE Remote Demo — one-shot startup (test-use, no auto-start on boot).
# Run this after every reboot to bring up: WS server + static page + funnel.
set -euo pipefail

REPO=/home/deepsim/multimodal-emotion-engine
cd "$REPO"

echo "==> [1/3] MEE WebSocket server (127.0.0.1:8910)"
python3 -m mee.remotedemo.server > /tmp/mee-ws.log 2>&1 &
WS_PID=$!
echo "    pid=$WS_PID  log=/tmp/mee-ws.log"

echo "==> [2/3] Static client page (0.0.0.0:8082)"
(cd "$REPO/mee/remotedemo" && python3 -m http.server 8082) > /tmp/mee-http.log 2>&1 &
HTTP_PID=$!
echo "    pid=$HTTP_PID  log=/tmp/mee-http.log"

echo "==> [3/3] Tailscale Funnel for 8910"
tailscale funnel 8910 > /tmp/mee-funnel.log 2>&1 &
FUNNEL_PID=$!
echo "    pid=$FUNNEL_PID  log=/tmp/mee-funnel.log"

sleep 2
echo
echo "==> Access token:"
cat ~/.config/mee-remotedemo/token
echo
echo "==> Server URL (remote):  wss://jetson-agx.tail0d394d.ts.net/"
echo "==> Server URL (local):   ws://127.0.0.1:8910/"
echo "==> Page URL (local):     http://127.0.0.1:8082/"
echo "==> Page URL (tailnet):   http://100.97.141.103:8082/"
echo
echo "==> Stop everything:  kill $WS_PID $HTTP_PID $FUNNEL_PID"
echo "    (or: pkill -f 'mee.remote[d]emo.server'; pkill -f 'http.server 8082'; pkill -f 'tailscale funnel 8910')"
