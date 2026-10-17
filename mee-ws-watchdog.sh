#!/usr/bin/env bash
# MEE WS watchdog: restarts the remotedemo WS server if it dies.
# TASK_MEE_035 (2026-10-16): public reachability is via Pangolin (meews.deepsim.ai),
#   not Tailscale Funnel.  The watchdog only keeps the local 127.0.0.1:8910 listener
#   alive; it does not manage any tunnel/funnel.
# Run with: nohup bash ~/multimodal-emotion-engine/mee-ws-watchdog.sh &
LOG=/tmp/mee-ws-watchdog.log
while true; do
  if ! ss -tlnp 2>/dev/null | grep -q ':8910 '; then
    echo "$(date -Is) WS server down — restarting" >> "$LOG"
    cd /home/deepsim/multimodal-emotion-engine || exit 1
    setsid nohup python3 -m mee.remotedemo.server >> /tmp/mee-ws.log 2>&1 < /dev/null &
    sleep 5
  fi
  sleep 5
done
