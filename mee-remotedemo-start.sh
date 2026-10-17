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
#
# Cleanup strategy (2026-10-16 fix): PID files + fuser-by-port, NOT pkill/pkill
# cmdline patterns. On this aarch64 host the bracket-idiom pgrep/pkill patterns
# silently failed to match the real processes, so old versions stacked up stale
# watchdogs and left stale servers in charge. PID files are exact.
set -euo pipefail

REPO=/home/deepsim/multimodal-emotion-engine
# The `mee` package is only importable from the repo root — the original script
# relied on `cd "$REPO"`. Restore it (dropping it broke `python3 -m` when the
# script was launched from ~). Also export PYTHONPATH as belt-and-suspenders so
# a future caller can't regress this again regardless of cwd.
cd "$REPO"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
# 2026-10-17: Voice now runs in a SEPARATE worker process (mee/voice/
# voice_worker.py, driven by the engine via voice_worker_client.py). This
# isolates the SpeechBrain/torch voice runtime from the MediaPipe vision
# runtime so they no longer share an address space (that in-process
# combination segfaults this host). Both camera AND mic recognition are
# therefore available at once. Set MEE_VOICE_ENABLED=0 to disable voice.
export MEE_VOICE_ENABLED=1
RUNDIR="$REPO/.run"
mkdir -p "$RUNDIR"
WS_PIDFILE="$RUNDIR/ws.pid"
HTTP_PIDFILE="$RUNDIR/https.pid"
WATCHDOG_PIDFILE="$RUNDIR/watchdog.pid"

# --- helpers ---------------------------------------------------------------

# Kill by PID file if the process is still alive (ignore missing/stale file).
kill_pidfile() {
    local f=$1 pid
    [ -f "$f" ] || return 0
    pid=$(cat "$f" 2>/dev/null) || return 0
    [ -n "$pid" ] || return 0
    if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null || true
    fi
    rm -f "$f"
    return 0
}

# Kill by PID, wait up to 5s for the process to actually exit.
kill_pid_wait() {
    local pid=$1 i
    kill -TERM "$pid" 2>/dev/null || true
    for i in 1 2 3 4 5; do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 1
    done
    return 0
}

# Wait up to N seconds for a TCP port to start accepting connections.
# Returns non-zero (failing the script under set -e) if it never opens, so a
# bind collision or a crashed startup aborts loudly instead of silently leaving
# the previous server in charge.
wait_port() {
    local port=$1 host=${2:-127.0.0.1} i
    for i in $(seq 1 10); do
        if (exec 3<>"/dev/tcp/${host}/${port}") 2>/dev/null; then
            exec 3>&- 3<&- 2>/dev/null || true
            return 0
        fi
        sleep 1
    done
    echo "    ERROR: nothing is listening on ${host}:${port}" >&2
    return 1
}

# Kill the old watchdog FIRST (it respawns the WS server), then any process
# still bound to our ports. Order matters: stop the respawner before we touch
# the ports, otherwise it re-launches the server under our feet.
cleanup() {
    kill_pidfile "$WATCHDOG_PIDFILE"
    # Belt-and-braces: also catch stray watchdogs by plain literal pattern
    # (NOT the bracket idiom — pgrep on this host mis-matches bracket patterns).
    pkill -f 'mee-ws-watchdog\.sh' 2>/dev/null || true
    sleep 1
    kill_pidfile "$WS_PIDFILE"
    kill_pidfile "$HTTP_PIDFILE"
    # Release the ports regardless of who holds them.
    fuser -k -TERM 8910/tcp 2>/dev/null || true
    fuser -k -TERM 8443/tcp 2>/dev/null || true
    sleep 1
}

# --- cert ------------------------------------------------------------------
# Ensure cert exists; generate if missing (needed by the 8443 page server)
if [ ! -f /tmp/mee-cert.pem ] || [ ! -f /tmp/mee-key.pem ]; then
    echo "==> Generating self-signed HTTPS cert..."
    openssl req -x509 -newkey rsa:4096 -nodes -sha256 \
      -keyout /tmp/mee-key.pem -out /tmp/mee-cert.pem \
      -subj "/CN=jetson-agx" -days 365 2>/dev/null
    echo "    cert=/tmp/mee-cert.pem key=/tmp/mee-key.pem"
fi

cleanup

# --- [1] WS server ---------------------------------------------------------
echo "==> [1/3] MEE WebSocket server (127.0.0.1:8910)"
python3 -m mee.remotedemo.server > /tmp/mee-ws.log 2>&1 &
WS_PID=$!
echo "$WS_PID" > "$WS_PIDFILE"
if ! wait_port 8910; then
    echo "    pid=$WS_PID died during startup — see /tmp/mee-ws.log" >&2
    exit 1
fi
echo "    pid=$WS_PID  log=/tmp/mee-ws.log"

# --- [2] HTTPS static page -------------------------------------------------
echo "==> [2/3] HTTPS static client page (0.0.0.0:8443)"
( cd "$REPO/mee/remotedemo" && exec python3 https_server.py ) > /tmp/mee-https.log 2>&1 &
HTTP_PID=$!
echo "$HTTP_PID" > "$HTTP_PIDFILE"
if ! wait_port 8443; then
    echo "    pid=$HTTP_PID died during startup — see /tmp/mee-https.log" >&2
    exit 1
fi
echo "    pid=$HTTP_PID  log=/tmp/mee-https.log"

# --- [3] watchdog ----------------------------------------------------------
echo "==> [3/3] WS watchdog (auto-restart if server dies)"
if [ ! -f "$REPO/mee-ws-watchdog.sh" ]; then
    echo "    WARNING: $REPO/mee-ws-watchdog.sh missing; skipping watchdog."
else
    # setsid puts the watchdog in its own session so it survives the script
    # exiting. Capture its PID, then confirm it's actually running before we
    # print success — if the pidfile is gone, the watchdog died at startup.
    setsid nohup bash "$REPO/mee-ws-watchdog.sh" > /dev/null 2>&1 < /dev/null &
    WD_PID=$!
    echo "$WD_PID" > "$WATCHDOG_PIDFILE"
    # Wait for it to settle, then verify it's still alive.
    sleep 1
    if kill -0 "$WD_PID" 2>/dev/null && [ -f "$WATCHDOG_PIDFILE" ]; then
        echo "    pid=$WD_PID  log=/tmp/mee-ws-watchdog.log"
    else
        echo "    ERROR: watchdog (pid=$WD_PID) exited during startup" >&2
        rm -f "$WATCHDOG_PIDFILE"
        exit 1
    fi
fi

# --- summary ---------------------------------------------------------------
sleep 1
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
echo "    bash $REPO/mee-remotedemo-stop.sh"
echo "    (or) pkill -f 'mee-ws-watchdog\.sh'; pkill -f 'mee.remotedemo.server'; fuser -k 8910/tcp 8443/tcp"
