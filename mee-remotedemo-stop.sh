#!/usr/bin/env bash
# MEE Remote Demo — stop everything (watchdog, WS server, HTTPS page).
# Companion to mee-remotedemo-start.sh. Uses PID files + port kill so it works
# even if cmdline patterns mis-match on this host.
set -uo pipefail

REPO=/home/deepsim/multimodal-emotion-engine
RUNDIR="$REPO/.run"

kill_pidfile() {
    local f=$1 pid
    [ -f "$f" ] || return 0
    pid=$(cat "$f" 2>/dev/null) || return 0
    [ -n "$pid" ] || return 0
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null && echo "    stopped pid=$pid ($(basename "$f"))"
    fi
    rm -f "$f"
    return 0
}

echo "==> Stopping MEE Remote Demo..."
# Watchdog first (it respawns the WS server).
kill_pidfile "$RUNDIR/watchdog.pid"
pkill -f 'mee-ws-watchdog\.sh' 2>/dev/null && echo "    killed stray watchdog(s) by pattern" || true
sleep 1
kill_pidfile "$RUNDIR/ws.pid"
kill_pidfile "$RUNDIR/https.pid"
# Release the ports no matter who holds them.
fuser -k -TERM 8910/tcp 2>/dev/null && echo "    released :8910" || true
fuser -k -TERM 8443/tcp 2>/dev/null && echo "    released :8443" || true
sleep 1
echo "==> Done."
echo "    remaining MEE procs:"
ps -eo pid,args | grep -E 'https_server|remotedemo\.server|mee-ws-watchdog\.sh' | grep -v grep || echo "    (none)"
