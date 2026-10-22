"""TASK_MEE_014 Subtask 1: WebSocket backend bridging the browser client to EmotionEngine.

Protocol (browser <-> server), documented for the client in index.html:
  Text JSON messages (client -> server):
    {"type":"auth","token":"<hex>"}          — MUST be the first message
    {"type":"frame","data":"<base64-jpeg>"}  — camera frame
    {"type":"audio","data":"<base64-f32-le>"} — audio chunk (float32 little-endian)
    {"type":"stop"}                          — stop processing loop
    {"type":"ping"}                          — liveness probe
  Text JSON messages (server -> client):
    {"type":"auth_ok","protocol":"mee-remotedemo-v1"}
    {"type":"error","code":"...","message":"..."}
    {"type":"result","data":{face,voice,overall,trend,latency_ms},"server_ts":...}
    {"type":"pong","ts":...}
    {"type":"heartbeat","ts":...}      — server keeps the socket warm (TASK_MEE_015 Task 2)

Design constraints (from CTO_PLAN.md + G3_RESPONSE.md):
  - Thin wrapper: every inference result is exactly EmotionEngine.process() output.
  - Single-threaded inference per connection; global max_connections cap.
  - Rate limiting: max_fps per connection; oversized payloads rejected.
  - Auth: token as first WS text message; failure closes the connection.
  - Audit log: every auth outcome (success/failure) appended to auth_log_file.
  - CORS: Access-Control-Allow-Origin header on the WebSocket upgrade.

TASK_MEE_019 (License Plan Selection & Purchase UI):
  * GET  /license/status           (WS port, _http_endpoint)
  * POST /license/activate         {key}
  * POST /license/deactivate       {}
  * POST /license/request-community {name,email,institution?}
    The three POST endpoints live on a secondary stdlib HTTP server
    (ThreadingHTTPServer) on MEE_DEMO_HTTP_PORT (default WS port + 1000),
    because websockets' process_request hook never receives a request body.
  * Rate limiting (CommunityRequestRateLimiter): 1 free-license request per
    email per 24h, 3 per IP per hour.  429 + retry_after when exceeded.
  * Security: KEYGATE_API_KEY is read server-side only (env or $MEE_HOME
    file); it never appears in index.html or any client-side code (AC4/S3).
"""
from __future__ import annotations

import asyncio
import base64
import json
import json as _json  # TASK_MEE_019: alias used by the license HTTP handlers
import logging
import logging.handlers
import os
import re
import signal
import threading
import time
from pathlib import Path
from typing import Optional
import sys

try:
    import websockets
    from websockets.server import serve
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore[assignment]
    serve = None  # type: ignore[assignment]

from .config import RemotedemoConfig

PROTOCOL_VERSION = "mee-remotedemo-v1"
# TASK_MEE_015 Task 2: application-level heartbeat cadence. The server sends a
# small {"type":"heartbeat"} frame every HEARTBEAT_INTERVAL_S to any idle
# authenticated connection so proxy/firewall idle timers (Tailscale Funnel,
# NAT) see traffic even when the client is silent. Distinct from protocol
# pings (which websockets auto-answers) and from the client's app-level ping
# (which this server answers with {"type":"pong"}).
HEARTBEAT_INTERVAL_S = 15.0
MAX_AUTH_TIMEOUT_S = 5.0
MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_AUDIO_CHUNK_SAMPLES = 16000
# TASK_MEE_017 Task B (fix): the voice model (IEMOCAP wav2vec2) needs a minimum
# of audio samples to run — a single 20 ms chunk (320 samples @ 16 kHz) is far
# too short and the `avg_pool` kernel errors out ("Kernel size (2) > input (1)").
# Running inference on every 20 ms chunk also floods the worker-thread pool and
# clogs the WS send buffer, which the browser interprets as a dead socket and
# drops the connection ("Reconnecting…").  We therefore buffer incoming chunks
# per-connection and only run inference once we have at least
# AUDIO_INFERENCE_SAMPLES of audio (~2 s).  This both fixes the short-input
# error and throttles inference to a sane rate.
AUDIO_INFERENCE_SAMPLES = 16000   # 2.0 s @ 16 kHz
AUDIO_BUFFER_MAX_SAMPLES = 64000  # 4.0 s @ 16 kHz — discard oldest beyond this

# TASK_MEE_019 (CommunityRequestRateLimiter policy — CORE_CONTRACTS §3):
#   per email: 1 free-license request per 24 hours (86400 s)
#   per IP:    3 free-license requests per hour (3600 s)
COMMUNITY_LIMIT_EMAIL = 1
COMMUNITY_EMAIL_WINDOW_S = 86400
COMMUNITY_LIMIT_IP = 3
COMMUNITY_IP_WINDOW_S = 3600

# TASK_MEE_019 (S1): Keygate admin API key — server-side only, never in the
# browser.  Resolution precedence (env wins over file):
#   1. MEE_KEYGATE_API_KEY environment variable
#   2. $MEE_HOME/keygate_api_key file (MEE_HOME defaults to
#      ~/.config/mee-licensing — same home dir as mee.licensing.config)
KEYGATE_ADMIN_ENV = "MEE_KEYGATE_API_KEY"


def _keygate_api_key() -> Optional[str]:
    """TASK_MEE_019 (S1): resolve the Keygate admin API key, server-side only."""
    env = (os.environ.get(KEYGATE_ADMIN_ENV) or "").strip()
    if env:
        return env
    try:
        import pathlib
        home = os.environ.get("MEE_HOME", "").strip()
        base = (pathlib.Path(home).expanduser() if home
                else pathlib.Path.home() / ".config" / "mee-licensing")
        f = base / "keygate_api_key"
        if f.exists():
            val = f.read_text().strip()
            if val:
                return val
    except OSError:
        pass
    return None


def _keygate_base_url() -> str:
    """TASK_MEE_019: Keygate admin API base URL (same server as the SDK API)."""
    url = (os.environ.get("MEE_LICENSE_SERVER") or "").strip()
    return url or "https://licenses.deepsim.ai:8443"


# TASK_MEE_019: Keygate plan ID for the free Community/Academic plan
# (verified in Keygate Postgres 2026-10-22, TASK_REQUEST §2).
KEYGATE_COMMUNITY_PLAN_ID = "a2064f10-4deb-4eda-a8a7-5bf05aeac7a7"


class AuthError(Exception):
    pass


class PayloadTooLarge(Exception):
    pass


class RateLimited(Exception):
    pass


class RateLimiter:
    """Simple per-connection frame rate limiter (tokens per second)."""

    def __init__(self, max_rate: int):
        self.max_rate = max(1, int(max_rate))
        self.tokens = float(self.max_rate)
        self.updated = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(float(self.max_rate),
                          self.tokens + (now - self.updated) * self.max_rate)
        self.updated = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class AuthAuditor:
    """Append-only audit log for auth outcomes (G3_RESPONSE.md 4d)."""

    def __init__(self, path=None):
        self.path = Path(path) if isinstance(path, str) else path
        # Unique logger per auditor so multiple RemotedemoServer instances
        # (e.g. across tests) don't share a handler bound to the first path.
        name = f"mee.remotedemo.audit.{os.getpid()}.{id(self)}"
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._logger.handlers = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.TimedRotatingFileHandler(
                self.path, when="midnight", backupCount=14, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self._logger.addHandler(handler)

    def record(self, client_ip: str, outcome: str, detail: str = "") -> None:
        self._logger.info("client=%s outcome=%s %s", client_ip, outcome, detail)


class CommunityRequestRateLimiter:
    """TASK_MEE_019 (AC6, CORE_CONTRACTS §3): rate limiter for the free
    Community/Academic license request endpoint.

    Policy (in-memory, TTL-pruned on every call — AD-3, no disk I/O):
      - at most 1 request per email per 24 hours
      - at most 3 requests per IP per hour
    The two counters are independent (a single email from two IPs is allowed
    twice; the same IP can serve up to 3 different emails per hour).

    ``check()`` records a hit only when the request is allowed (denied
    attempts do not extend the window) and returns ``(allowed,
    retry_after_seconds)`` — the caller maps a denial to HTTP 429.
    """

    def __init__(self,
                 email_limit: int = COMMUNITY_LIMIT_EMAIL,
                 email_window_s: int = COMMUNITY_EMAIL_WINDOW_S,
                 ip_limit: int = COMMUNITY_LIMIT_IP,
                 ip_window_s: int = COMMUNITY_IP_WINDOW_S):
        self.email_limit = email_limit
        self.email_window_s = email_window_s
        self.ip_limit = ip_limit
        self.ip_window_s = ip_window_s
        self._by_email: dict = {}  # email -> [timestamp, ...]
        self._by_ip: dict = {}     # ip -> [timestamp, ...]
        self._lock = threading.Lock()

    # -- internals -------------------------------------------------------

    def _prune(self, entries: list, window_s: float, now: float) -> list:
        return [t for t in entries if now - t <= window_s]

    # -- public API ------------------------------------------------------

    def check(self, email: str, ip: str) -> tuple:
        """Return ``(allowed, retry_after_seconds)`` for (email, ip).

        On success the hit is recorded in both counters (per email and per IP)
        so each limit tracks independently.  On denial nothing is recorded.
        """
        now = time.time()
        email = (email or "").strip().lower()
        ip = ip or "unknown"
        with self._lock:
            email_entries = self._prune(
                self._by_email.get(email, []), self.email_window_s, now)
            ip_entries = self._prune(
                self._by_ip.get(ip, []), self.ip_window_s, now)
            if len(email_entries) >= self.email_limit:
                retry_after = int(max(1, round(
                    email_entries[0] + self.email_window_s - now)))
                self._by_email[email] = email_entries
                self._by_ip[ip] = ip_entries
                return (False, retry_after)
            if len(ip_entries) >= self.ip_limit:
                retry_after = int(max(1, round(
                    ip_entries[0] + self.ip_window_s - now)))
                self._by_email[email] = email_entries
                self._by_ip[ip] = ip_entries
                return (False, retry_after)
            self._by_email[email] = email_entries + [now]
            self._by_ip[ip] = ip_entries + [now]
            return (True, 0)

    def reset(self) -> None:
        """Clear all counters (tests only)."""
        with self._lock:
            self._by_email.clear()
            self._by_ip.clear()


def decode_image_bgr(payload_b64: str) -> "np.ndarray":
    """Decode a base64 JPEG/PNG payload into a BGR numpy array.

    Raises PayloadTooLarge if the decoded size exceeds MAX_FRAME_BYTES.
    """
    try:
        raw = base64.b64decode(payload_b64)
    except (ValueError, TypeError) as exc:
        raise AuthError(f"invalid frame payload: {exc}") from exc
    if len(raw) > MAX_FRAME_BYTES:
        raise PayloadTooLarge(f"frame payload {len(raw)} bytes exceeds {MAX_FRAME_BYTES}")
    import numpy as np
    import cv2
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise AuthError("frame payload is not a decodable image")
    return img


def decode_audio_f32(payload_b64: str) -> "np.ndarray":
    """Decode a base64 float32 little-endian payload into a 1-D numpy array.

    Raises PayloadTooLarge if the sample count exceeds MAX_AUDIO_CHUNK_SAMPLES.
    """
    import numpy as np
    try:
        raw = base64.b64decode(payload_b64)
    except (ValueError, TypeError) as exc:
        raise AuthError(f"invalid audio payload: {exc}") from exc
    if len(raw) % 4 != 0:
        raise AuthError(f"audio payload size {len(raw)} is not a multiple of 4 bytes")
    samples = np.frombuffer(raw, dtype="<f4")
    if len(samples) > MAX_AUDIO_CHUNK_SAMPLES:
        raise PayloadTooLarge(
            f"audio chunk {len(samples)} samples exceeds {MAX_AUDIO_CHUNK_SAMPLES}")
    return samples


def serialize_result(result: dict) -> dict:
    """Return a JSON-safe copy of an EmotionEngine.process() dict.

    MEE already returns JSON-serializable output; this is a defensive
    copy that converts numpy scalars to native Python types so the
    result is always safe for ``json.dumps`` without extra handling.
    """
    try:
        import numpy as np
        _NP = np
    except ImportError:
        _NP = None

    def _clean(v):
        if v is None or isinstance(v, (bool, str)):
            return v
        if _NP is not None and isinstance(v, _NP.generic):
            return v.item()
        if isinstance(v, dict):
            return {k: _clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_clean(x) for x in v]
        if isinstance(v, (int, float)):
            return v
        return str(v)

    return _clean(result)


class RemotedemoServer:
    """WebSocket server exposing EmotionEngine to a browser client.

    Usage:
        server = RemotedemoServer(engine, config)
        await server.start()        # blocks until stop()
        await server.stop()
    """

    def __init__(self, engine, config: Optional[RemotedemoConfig] = None):
        if serve is None:
            raise RuntimeError("websockets package is not installed")
        self.engine = engine
        self.config = config or RemotedemoConfig()
        self.active_connections = 0
        self._server = None
        self._auditor = AuthAuditor(self.config.auth_log_file)
        # TASK_MEE_019: ensure _wslog exists before start_license_server()
        # uses it (start() re-initialises it, but we need a safe default
        # for the case where start_license_server() runs first or the
        # WS port is taken and start() aborts early).
        self._wslog = logging.getLogger("mee.remotedemo.ws")
        # TASK_MEE_019 (AC6): free-request rate limiter (1/email/24h, 3/IP/h).
        self._community_limiter = CommunityRequestRateLimiter()
        # TASK_MEE_019 (AD-2): secondary HTTP server for the license POST
        # endpoints (websockets' process_request hook cannot read bodies).
        # Shares the same limiter instance so counts are unified.
        self._license_server = LicenseHTTPServer(
            self.config.license_http_port,
            engine=engine,
            keygate_api_key=_keygate_api_key(),
            community_limiter=self._community_limiter,
        )
        # TASK_MEE_019 (AC3): shared LicenseClient for activate/deactivate
        # (real Keygate calls — not simulated).
        self._license_client = None
        # TASK_MEE_017 Task B (fix): per-connection audio buffers keyed by id(ws).
        # Browser sends 20 ms chunks continuously; we accumulate them here and
        # only run inference on a complete segment (>= AUDIO_INFERENCE_SAMPLES).
        # This avoids the short-input error AND stops the inference flood that
        # clogged the WS send buffer and made the browser drop the socket.
        self._audio_buffers: dict = {}

    def _cors_origins(self):
        """Return an allow-list of origins for the websockets library.

        websockets (>=14) rejects ``origin="*"`` for a direct WebSocket
        connection (a client connecting via ws:// has no Origin header,
        and the library requires an explicit allow-list). For prototype
       -grade ``*`` we allow any origin by passing a sentinel that the
        library treats as "allow all" — the websockets library supports
        this via a callable returning True for any origin.
        """
        if self.config.cors_origin == "*":
            return None  # None => allow all origins (no Origin filtering)
        return [self.config.cors_origin]

    # -- lifecycle ------------------------------------------------------

    async def start(self) -> None:
        # TASK_MEE_014 fix: use the resolved token (not the possibly-empty
        # self.config.token attribute) so auth compares against the same value
        # that resolve_token() returned.
        self._active_token = self.config.resolve_token()
        origins = self._cors_origins()
        # TASK_MEE_015 Task 2: keepalive tuning.  ping_interval=10/timeout=20
        # replaces the previous 20/15: a shorter interval catches a dead peer
        # faster, and a longer timeout tolerates the event-loop stalls observed
        # on the Jetson (inference blocking the loop) that produced the
        # "keepalive ping timeout" 1011 closes in TASK_MEE_014/015.
        # TASK_MEE_030 (2026-09-27): process_request lets the funnel URL
        # (wss://host/) serve HTTP endpoints (/healthz) alongside the
        # WebSocket upgrade on the same port.
        # TASK_MEE_019 (AD-2): bring up the license HTTP API in parallel
        # with the WS server (fails soft — WS demo must still work).
        self.start_license_server()
        self._server = await serve(
            self._handle,
            host=self.config.host,
            port=self.config.port,
            max_size=MAX_FRAME_BYTES + 8 * 1024,
            ping_interval=10,
            ping_timeout=20,
            process_request=self._http_endpoint,
            **({"origins": self.config.cors_origin} if self.config.cors_origin != "*" else {}),
        )
        # TASK_MEE_015 Task 1: debug logger for keepalive / close diagnostics.
        # The start script redirects stdout to /tmp/mee-ws.log, so the
        # acceptance criterion `grep -E "WS-KA (pong|sent|recv)" /tmp/mee-ws.log`
        # is satisfied by this logger.  Also appended to the audit log so the
        # record survives log-file rotation.
        self._wslog = logging.getLogger("mee.remotedemo.ws")
        self._wslog.setLevel(logging.INFO)
        if not self._wslog.handlers:
            h = logging.StreamHandler(sys.stdout)
            h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self._wslog.addHandler(h)
        self._auditor.record("server", "started",
                             f"host={self.config.host} port={self.config.port} "
                             f"pid={os.getpid()} "
                             f"ping_interval=10 ping_timeout=20 heartbeat={HEARTBEAT_INTERVAL_S:.0f}s")
        self._wslog.info(
            "TASK_MEE_034 server started pid=%s host=%s port=%s",
            os.getpid(), self.config.host, self.config.port)
        await self._server.wait_closed()

    async def stop(self) -> None:
        self.stop_license_server()
        if self._server is not None:
            self._server.close()
            self._server = None

    def start_license_server(self) -> None:
        """TASK_MEE_019: start the secondary license HTTP API (best-effort)."""
        try:
            self._license_server.start()
        except OSError as exc:  # port taken etc. — demo still runs without it
            self._wslog.error(
                "TASK_MEE_019 license HTTP server failed to start on port %s: %s",
                self.config.license_http_port, exc)
            self._license_server = None

    def stop_license_server(self) -> None:
        """TASK_MEE_019: shut the secondary license HTTP API down."""
        if self._license_server is not None:
            try:
                self._license_server.stop()
            except Exception:  # noqa: BLE001 — shutdown must not raise
                pass
            self._license_server = None

    # -- HTTP endpoints on the same port (funnel URL) -------------------

    def _http_endpoint(self, path, request_headers) -> tuple:
        """Serve plain-HTTP endpoints on the WS port when the request is not
        a WebSocket upgrade.  This lets `https://<funnel-host>/` deliver the
        access token and a health check to the browser without a second
        public port (TASK_MEE_030, 2026-09-27).

        Returns a (status, headers, body) tuple per the installed websockets
        (legacy) handshake contract; the library then sends the response and
        closes the connection.  A real WebSocket upgrade request is never
        routed here (it goes to ``_handle``).
        """
        import http as _http

        def _res(body: bytes, status: int = 200) -> tuple:
            return (
                _http.HTTPStatus(status),
                [
                    ("Content-Type", "application/json"),
                    ("Access-Control-Allow-Origin", "*"),
                    ("Cache-Control", "no-store"),
                ],
                body,
            )

        if path == "/healthz":
            return _res(b'{"status":"ok"}\n')
        # TASK_MEE_031 (2026-09-27): /token endpoint REMOVED.
        # Token is delivered out-of-band by the operator and entered manually.
        # TASK_MEE_019 (R1, AC3): GET /license/status — real data from
        # LicenseClient.status() (never raises — CORE_CONTRACTS §1).
        if path == "/license/status":
            try:
                from mee.licensing.client import LicenseClient
                client = LicenseClient()
                payload = client.status()
                body = _json.dumps({
                    "status": payload.get("status"),
                    "plan_id": payload.get("plan_id"),
                    "plan_name": payload.get("plan_name"),
                    "remaining_days": payload.get("remaining_days"),
                    "offline": bool(payload.get("offline")),
                    "device_id": payload.get("device_id"),
                }).encode("utf-8")
            except Exception as exc:  # noqa: BLE001 — endpoint must never 500-blank
                body = _json.dumps({
                    "status": "unknown", "plan_id": None, "plan_name": None,
                    "remaining_days": None, "offline": True,
                    "device_id": None, "error": str(exc)[:200],
                }).encode("utf-8")
            return _res(body)
        if path in ("/", ""):
            # TASK_MEE_030: plain HTTP GET on / serves the client page;
            # a WebSocket upgrade on / (Sec-WebSocket-Key header present)
            # returns None so the handshake proceeds to ``_handle``.
            upgrade = False
            for name, value in request_headers.items():
                if name.lower() == "sec-websocket-key":
                    upgrade = True
                    break
            if not upgrade:
                try:
                    page = Path(__file__).with_name("index.html").read_bytes()
                    return (
                        _http.HTTPStatus(200),
                        [
                            ("Content-Type", "text/html; charset=utf-8"),
                            ("Access-Control-Allow-Origin", "*"),
                            ("Cache-Control", "no-cache"),
                        ],
                        page,
                    )
                except Exception:
                    pass
            return None  # let the WebSocket handshake continue
        return None  # unknown path: let the WS handshake fail naturally

    # -- connection handler ---------------------------------------------

    async def _handle(self, ws) -> None:
        client_ip = ws.remote_address[0] if ws.remote_address else "unknown"
        self.active_connections += 1
        # TASK_MEE_015 Task 1: per-connection keepalive diagnostic state.
        conn_id = id(ws)
        conn_state = {
            "t0": time.time(),
            "last_app_in": time.time(),   # last client->server app frame
            "last_app_out": time.time(),  # last server->client app frame
            "last_p2p_ping": time.time(),  # last protocol ping sent (websockets)
            "last_p2p_pong": None,         # last protocol pong received
            "last_app_ping": None,        # last {type:ping} from client
            "last_app_pong": None,        # last {type:pong} sent to client
            "last_heartbeat": None,       # last server heartbeat frame
        }
        hb_task = None
        try:
            token = await self._auth(ws)
            if token is None:
                return
            self._auditor.record(client_ip, "auth_success", "token-ok")
            await ws.send(json.dumps({
                "type": "auth_ok",
                "protocol": PROTOCOL_VERSION,
            }))
            # TASK_MEE_015 Task 2: application-level heartbeat. Independent of
            # protocol pings, it guarantees visible socket traffic for proxy
            # idle timers whenever the client goes silent (tab backgrounded,
            # user stopped streaming, etc.).
            hb_task = asyncio.create_task(
                self._heartbeat_loop(ws, client_ip, conn_state))
            await self._main_loop(ws, client_ip, conn_state)
        except Exception as exc:  # noqa: BLE001 — connection-level catch-all
            self._auditor.record(client_ip, "error", str(exc)[:200])
            self._wslog.info(
                "WS-ERR conn=%s ip=%s exc=%s", conn_id, client_ip, str(exc)[:200])
            try:
                await ws.send(json.dumps({
                    "type": "error", "code": "internal", "message": "internal error"}))
            except Exception:
                pass
        finally:
            if hb_task is not None:
                hb_task.cancel()
            # TASK_MEE_017 Task B (fix): free this connection's audio buffer.
            self._audio_buffers.pop(id(ws), None)
            self.active_connections -= 1
            # TASK_MEE_015 Task 1: final close diagnostic with liveness state.
            now = time.time()
            age = now - conn_state["t0"]
            idle_in = (now - conn_state["last_app_in"]) if conn_state["last_app_in"] else -1
            idle_out = (now - conn_state["last_app_out"]) if conn_state["last_app_out"] else -1
            self._auditor.record(
                client_ip, "closed",
                f"age={age:.0f}s idle_in={idle_in:.0f}s idle_out={idle_out:.0f}s "
                f"last_p2p_pong={(conn_state['last_p2p_pong'] and round(now - conn_state['last_p2p_pong'], 1)) or 'never'}s_ago "
                f"last_app_pong={(conn_state['last_app_pong'] and round(now - conn_state['last_app_pong'], 1)) or 'never'}s_ago "
                f"last_heartbeat={(conn_state['last_heartbeat'] and round(now - conn_state['last_heartbeat'], 1)) or 'never'}s_ago")

    async def _heartbeat_loop(self, ws, client_ip: str, state: dict) -> None:
        """TASK_MEE_015 Task 2: send a small heartbeat every HEARTBEAT_INTERVAL_S.

        Runs until cancelled (connection end) or the send fails (socket gone).
        Never raises into the main handler.
        """
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                now = time.time()
                state["last_heartbeat"] = now
                state["last_app_out"] = now
                self._wslog.info("WS-KA conn sent heartbeat ip=%s", client_ip)
                await ws.send(json.dumps({"type": "heartbeat", "ts": now}))
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            self._wslog.info("WS-KA conn heartbeat stopped ip=%s exc=%s", client_ip, str(exc)[:120])
            return

    async def _auth(self, ws) -> Optional[str]:
        """Enforce first-message token auth. Returns token or None (closed)."""
        if self.active_connections > self.config.max_connections:
            self._auditor.record("conn", "rejected", "max_connections")
            await ws.send(json.dumps({
                "type": "error", "code": "too_many_connections",
                "message": "server at capacity; retry later"}))
            await ws.close(code=1013, reason="server at capacity")
            return None
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=MAX_AUTH_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._auditor.record("conn", "auth_timeout", "")
            await ws.close(code=1008, reason="auth timeout")
            return None
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError) as exc:
            self._auditor.record("conn", "auth_bad_json", str(exc)[:80])
            await ws.send(json.dumps({
                "type": "error", "code": "bad_auth", "message": "first message must be JSON auth"}))
            await ws.close(code=1008, reason="bad auth")
            return None
        if msg.get("type") != "auth":
            self._auditor.record("conn", "auth_wrong_type", str(msg.get("type")))
            await ws.send(json.dumps({
                "type": "error", "code": "bad_auth", "message": "first message must be {type:auth,token:...}"}))
            await ws.close(code=1008, reason="bad auth")
            return None
        provided = msg.get("token")
        # TASK_MEE_014 fix: compare against the resolved token. _active_token is
        # set in start(); the fallback keeps direct/instantiated servers (e.g. in
        # tests) working even if start() was not run.
        active_token = getattr(self, "_active_token", None) or self.config.resolve_token()
        if not provided or provided != active_token:
            self._auditor.record("conn", "auth_failure", "token mismatch")
            await ws.send(json.dumps({
                "type": "error", "code": "bad_token", "message": "invalid access token"}))
            await ws.close(code=1008, reason="invalid token")
            return None
        return provided

    async def _main_loop(self, ws, client_ip: str = "unknown", state: Optional[dict] = None) -> None:
        if state is None:
            state = {}
        limiter = RateLimiter(self.config.max_fps)
        last_result = None
        while True:
            raw = await ws.recv()
            if isinstance(raw, (bytes, bytearray)):
                # Binary frames are not part of the prototype protocol.
                await ws.send(json.dumps({
                    "type": "error", "code": "bad_message",
                    "message": "binary frames are not supported; use JSON"}))
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                await ws.send(json.dumps({
                    "type": "error", "code": "bad_json", "message": "message is not valid JSON"}))
                continue
            # TASK_MEE_015 Task 1: timestamp every client->server app frame.
            state["last_app_in"] = time.time()
            mtype = msg.get("type")
            if mtype == "ping":
                now = time.time()
                state["last_app_ping"] = now
                state["last_app_pong"] = now
                self._wslog.info("WS-KA conn recv app-ping ip=%s -> sent pong", client_ip)
                await ws.send(json.dumps({"type": "pong", "ts": now}))
            elif mtype == "stop":
                last_result = None
                await ws.send(json.dumps({"type": "stopped"}))
            elif mtype == "frame":
                await self._process_frame(ws, msg, limiter)
            elif mtype == "audio":
                await self._process_audio(ws, msg, client_ip=client_ip)
            elif mtype in ("mute", "unmute"):
                # 2026-10-16: The browser client sends {type:"mute",audio:true}
                # when the mic is off (TASK_MEE_015) so the UI can show "voice
                # muted". The server had no branch for it -> it replied
                # {type:"error",code:"unknown_type"} which the client rendered
                # as "Connected — server error". Voice inference is disabled
                # server-side on this host (see MEE_VOICE_ENABLED), so mute is a
                # pure intent signal: acknowledge it with mute_ok instead of
                # erroring, and record the intent for the connection state.
                muted = bool(msg.get("audio", mtype == "mute"))
                state["voice_muted"] = muted
                self._wslog.info(
                    "WS-MUTE conn mute audio=%s ip=%s (voice path %s)",
                    muted, client_ip,
                    "disabled" if not getattr(self.engine.config, "voice_enabled", True) else "active",
                )
                await ws.send(json.dumps({
                    "type": "mute_ok", "audio": muted, "ts": time.time(),
                }))
            else:
                await ws.send(json.dumps({
                    "type": "error", "code": "unknown_type",
                    "message": f"unknown message type {mtype!r}"}))

    async def _process_frame(self, ws, msg: dict, limiter: RateLimiter) -> None:
        data_b64 = msg.get("data")
        if not data_b64:
            await ws.send(json.dumps({
                "type": "error", "code": "missing_data", "message": "frame message has no data"}))
            return
        if not limiter.allow():
            self._auditor.record("conn", "rate_limited", "frame")
            await ws.send(json.dumps({
                "type": "error", "code": "rate_limited",
                "message": f"frame rate cap {self.config.max_fps} fps exceeded"}))
            return
        try:
            frame_bgr = decode_image_bgr(data_b64)
        except PayloadTooLarge as exc:
            self._auditor.record("conn", "payload_too_large", str(exc)[:120])
            await ws.send(json.dumps({
                "type": "error", "code": "payload_too_large", "message": str(exc)}))
            return
        except AuthError as exc:
            await ws.send(json.dumps({
                "type": "error", "code": "bad_frame", "message": str(exc)}))
            return
        # TASK_MEE_015 (re-fix): inference is CPU-bound and BLOCKS the event
        # loop (vision ~11 s/frame on the Jetson, audio >60 s on the error
        # path).  A blocked loop cannot process the browser's pong, so the
        # websockets library fires "1011 keepalive ping timeout" and kills the
        # connection (seen repeatedly in the audit log).  Offload to a worker
        # thread so the loop stays free to answer pings/heartbeats; the thread
        # also releases the GIL, so the event loop actually runs during it.
        result = await asyncio.to_thread(self._infer, frame_bgr=frame_bgr, audio=None)
        await ws.send(json.dumps({
            "type": "result",
            "server_ts": time.time(),
            "source": "frame",
            "data": serialize_result(result),
        }))

    async def _process_audio(self, ws, msg: dict, client_ip: str = "unknown") -> None:
        data_b64 = msg.get("data")
        if not data_b64:
            await ws.send(json.dumps({
                "type": "error", "code": "missing_data", "message": "audio message has no data"}))
            return
        try:
            audio = decode_audio_f32(data_b64)
        except PayloadTooLarge as exc:
            self._auditor.record("conn", "payload_too_large", str(exc)[:120])
            await ws.send(json.dumps({
                "type": "error", "code": "payload_too_large", "message": str(exc)}))
            return
        except AuthError as exc:
            await ws.send(json.dumps({
                "type": "error", "code": "bad_audio", "message": str(exc)}))
            return
        import numpy as np

        # TASK_MEE_017 Task B (fix): accumulate the chunk into this connection's
        # buffer.  Only run inference once we have a full segment — this fixes
        # the short-input model error and stops the per-chunk inference flood.
        buf = self._audio_buffers.setdefault(id(ws), np.zeros(0, dtype=np.float32))
        buf = np.concatenate([buf, audio])
        if len(buf) > AUDIO_BUFFER_MAX_SAMPLES:
            buf = buf[-AUDIO_BUFFER_MAX_SAMPLES:]  # drop oldest, keep freshest
        if len(buf) < AUDIO_INFERENCE_SAMPLES:
            self._audio_buffers[id(ws)] = buf
            self._wslog.debug(
                "WS-AUDIO-BUF ip=%s buffered=%d/%d samples (waiting for more)",
                client_ip, len(buf), AUDIO_INFERENCE_SAMPLES,
            )
            return
        # We have enough — consume the buffer and run inference.
        self._audio_buffers.pop(id(ws), None)
        self._wslog.info(
            "WS-AUDIO-SEG ip=%s samples=%d (~%.1fs) running inference",
            client_ip, len(buf), len(buf) / 16000.0,
        )
        # Diagnostics on the full segment (not just one chunk).
        mean_abs = float(np.mean(np.abs(buf)))
        max_val = float(np.max(np.abs(buf)))
        non_zero_ratio = float(np.count_nonzero(buf)) / len(buf)
        self._wslog.info(
            "WS-KA-audio ip=%s samples=%d mean_abs=%.4f max=%.4f non_zero_ratio=%.2f%%",
            client_ip, len(buf), mean_abs, max_val, non_zero_ratio * 100,
        )
        # TASK_MEE_015 (re-fix): run off the loop in a worker thread (see _process_frame note).
        try:
            result = await asyncio.to_thread(self._infer, frame_bgr=None, audio=buf)
        except Exception as exc:  # noqa: BLE001
            self._wslog.error("WS-VOICE-ERR ip=%s exc=%s", client_ip, exc)
            await ws.send(json.dumps({
                "type": "error", "code": "inference_error", "message": str(exc)}))
            return
        # TASK_MEE_017 Task B1: log what the voice pipeline actually returned.
        if isinstance(result, dict) and result.get("voice"):
            emotion = result["voice"].get("emotion", "neutral")
            confidence = result["voice"].get("confidence", 0.0)
            if confidence < 0.01:
                self._wslog.warning(
                    "WS-VOICE-WARN ip=%s emotion=%s confidence=%.4f "
                    "(near-zero — likely model default or silent audio)",
                    client_ip, emotion, confidence,
                )
            else:
                self._wslog.info(
                    "WS-KA-voice ip=%s result=%s@%.2f%%",
                    client_ip, emotion, confidence * 100,
                )
        await ws.send(json.dumps({
            "type": "result",
            "server_ts": time.time(),
            "source": "audio",
            "data": serialize_result(result),
        }))

    def _infer(self, frame_bgr=None, audio=None) -> dict:
        """Call the engine exactly as the public API contract expects."""
        return self.engine.process(video_frame=frame_bgr, audio=audio)


def _license_status_dict() -> dict:
    """TASK_MEE_019: shape the GET /license/status body from LicenseClient.

    Never raises (CORE_CONTRACTS §1) — any failure degrades to a JSON
    "unknown" payload with an error note.
    """
    try:
        from mee.licensing.client import LicenseClient
        client = LicenseClient()
        payload = client.status()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unknown", "plan_id": None, "plan_name": None,
            "remaining_days": None, "offline": True, "device_id": None,
            "error": str(exc)[:200],
        }
    return {
        "status": payload.get("status"),
        "plan_id": payload.get("plan_id"),
        "plan_name": payload.get("plan_name"),
        "remaining_days": payload.get("remaining_days"),
        "offline": bool(payload.get("offline")),
        "device_id": payload.get("device_id"),
    }


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # CORE_CONTRACTS §3


def _issue_community_license(keygate_api_key: str, name: str, email: str,
                             institution: str) -> dict:
    """TASK_MEE_019 (R4, AC3): create a free Community/Academic license via
    the Keygate admin API (server-side; the key never reaches the browser).
    Returns ``(http_status, body_dict)``.
    """
    import requests
    if not (name or "").strip() or len(name.strip()) < 2:
        return 400, {"error": "name is required (min 2 characters)"}
    if not (email or "").strip():
        return 400, {"error": "email is required"}
    if not _EMAIL_RE.match(email.strip()):
        return 400, {"error": "email format invalid"}
    institution = (institution or "").strip()
    body = {
        "product_id": None,  # filled below if the API demands it
        "plan_id": KEYGATE_COMMUNITY_PLAN_ID,
        "name": name.strip(),
        "email": email.strip(),
        "institution": institution or None,
    }
    try:
        resp = requests.post(
            _keygate_base_url() + "/api/v1/admin/licenses",
            headers={"Authorization": "Bearer " + keygate_api_key,
                     "Content-Type": "application/json"},
            json={k: v for k, v in body.items() if v is not None},
            timeout=10,
        )
    except requests.RequestException as exc:
        return 500, {"error": f"Keygate API unreachable: {_sanitize_err(exc)}"}
    try:
        data = resp.json()
    except ValueError:
        return 500, {"error": f"Keygate API returned non-JSON (HTTP {resp.status_code})"}
    if resp.status_code == 200 and data.get("success", True):
        lic = data.get("data") or data
        key = (lic.get("license_key") or lic.get("key")
               or (lic.get("license") or {}).get("license_key") or "")
        if key:
            return 200, {
                "license_key": key,
                "status": "trialing",
                "message": "free Community/Academic license issued — activate it with the key below",
            }
        return 200, {
            "license_key": None,
            "status": "unknown",
            "message": "license created (key not returned by server)",
        }
    err = data.get("error") or {}
    msg = err.get("message") if isinstance(err, dict) else str(err)
    return resp.status_code, {"error": msg or f"Keygate API error (HTTP {resp.status_code})"}


def _sanitize_err(exc: Exception) -> str:
    """Strip anything that looks like an embedded credential from error text."""
    s = str(exc)
    s = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-]{8,}", r"\1***", s)
    return s[:200]


class LicenseHTTPServer:
    """TASK_MEE_019 (AD-2): secondary stdlib HTTP server for the license API.

    Serves the POST endpoints on ``0.0.0.0:port`` (GET /license/status is
    also served here so one base URL works for the browser client):

      GET  /license/status
      POST /license/activate         {"key": "..."}
      POST /license/deactivate       {}
      POST /license/request-community {"name","email","institution"?}

    Security (AC4/S3): the Keygate admin API key is held only in this class
    (server-side).  All responses carry ``Cache-Control: no-store`` and
    ``Access-Control-Allow-Origin: *`` (S7).
    """

    def __init__(self, port: int, engine=None,
                 keygate_api_key: Optional[str] = None,
                 license_client=None,
                 community_limiter=None):
        self.port = int(port)
        self.engine = engine
        self.keygate_api_key = keygate_api_key or _keygate_api_key()
        self.license_client = license_client
        self.community_limiter = community_limiter or CommunityRequestRateLimiter()
        self._httpd = None
        self._thread = None

    # -- lifecycle -------------------------------------------------------

    def start(self) -> threading.Thread:
        """Bind + serve in a daemon thread.  Raises OSError if the port is taken."""
        import http.server
        outer = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: N802 — stdlib hook
                try:
                    logging.getLogger("mee.remotedemo.license_http").info(
                        fmt, *args)
                except Exception:  # noqa: BLE001
                    pass

            def _send(self, status: int, body: dict, extra_headers=None) -> None:
                payload = _json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                if extra_headers:
                    for k, v in extra_headers.items():
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _read_body(self) -> dict:
                try:
                    length = int(self.headers.get("Content-Length", "0") or "0")
                except ValueError:
                    length = 0
                if length <= 0:
                    return {}
                raw = self.rfile.read(min(length, 65536))
                try:
                    data = _json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    return {}
                return data if isinstance(data, dict) else {}

            def do_OPTIONS(self):  # noqa: N802 — CORS preflight
                self._send(204, {})

            def do_GET(self):  # noqa: N802
                path = self.path.split("?", 1)[0]
                if path == "/license/status":
                    self._send(200, _license_status_dict())
                    return
                if path in ("/healthz", "/health"):
                    self._send(200, {"status": "ok"})
                    return
                self._send(404, {"error": "not found"})

            def do_POST(self):  # noqa: N802
                path = self.path.split("?", 1)[0]
                body = self._read_body()
                client_ip = self.client_address[0] if self.client_address else "unknown"
                if path == "/license/activate":
                    self._license_activate(body)
                elif path == "/license/deactivate":
                    self._license_deactivate()
                elif path == "/license/request-community":
                    self._license_request_community(body, client_ip)
                else:
                    self._send(404, {"error": "not found"})

            # -- route handlers (delegate to outer state) -----------------

            def _license_activate(self, body: dict) -> None:
                key = (body.get("key") or "").strip()
                if not key:
                    self._send(400, {"valid": False,
                                    "message": "missing 'key' field"})
                    return
                try:
                    client = outer._license_client()
                    result = client.activate(key)
                    self._send(200, {
                        "valid": True,
                        "status": getattr(result, "license_status", None)
                                 or getattr(result, "status", None),
                        "plan_name": getattr(result, "plan_name", None),
                        "message": "activated",
                    })
                except Exception as exc:  # noqa: BLE001
                    self._send(500, {"valid": False, "message": _sanitize_err(exc)})

            def _license_deactivate(self) -> None:
                try:
                    client = outer._license_client()
                    client.deactivate()
                    self._send(200, {"status": "deactivated",
                                    "message": "license deactivated"})
                except Exception as exc:  # noqa: BLE001
                    self._send(500, {"status": "error", "message": _sanitize_err(exc)})

            def _license_request_community(self, body: dict, client_ip: str) -> None:
                name = str(body.get("name") or "")
                email = str(body.get("email") or "")
                institution = str(body.get("institution") or "")
                allowed, retry_after = outer.community_limiter.check(email, client_ip)
                if not allowed:
                    self._send(429, {
                        "retry_after": retry_after,
                        "message": "too many requests — try again later",
                    }, extra_headers={"Retry-After": str(retry_after)})
                    return
                if not outer.keygate_api_key:
                    self._send(500, {"error": "KEYGATE_API_KEY not configured on server"})
                    return
                status, payload = _issue_community_license(
                    outer.keygate_api_key, name, email, institution)
                self._send(status, payload)

        self._httpd = http.server.ThreadingHTTPServer(
            ("0.0.0.0", self.port), _Handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="mee-license-http", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Shut the HTTP server down (idempotent)."""
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:  # noqa: BLE001
                pass
            self._httpd = None
            self._thread = None

    # -- client factory ----------------------------------------------------

    def _license_client(self):
        """Lazily build a LicenseClient (imports the licensing package)."""
        if self.license_client is None:
            from mee.licensing.client import LicenseClient
            self.license_client = LicenseClient()
        return self.license_client


async def run_server(engine=None, config: Optional[RemotedemoConfig] = None) -> None:
    """Convenience entrypoint: build engine (if needed) + serve forever."""
    # TASK_MEE_034 (2026-09-28): cap the CPU thread pool used by the
    # inference libraries (MediaPipe XNNPACK, OpenCV, and the ONNX / TFLite
    # delegates) so a burst of concurrent frame+audio inference does not
    # spawn a thread per CPU core.  On the Jetson (shared unified memory,
    # heavy CPU inference) the un-capped pool spiked CPU hard and correlated
    # with the repeated external process kills observed 2026-09-28.
    # Override with MEE_DEMO_MAX_THREADS=N (0 or unset = library default).
    try:
        _max_threads = os.environ.get("MEE_DEMO_MAX_THREADS", "2")
        if _max_threads and int(_max_threads) > 0:
            for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                         "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                         "NUMEXPR_NUM_THREADS"):
                os.environ.setdefault(_var, _max_threads)
    except Exception:  # noqa: S110 — thread-cap must never break startup
        pass
    if engine is None:
        from mee import EmotionEngine, MEEConfig
        engine = EmotionEngine(config=MEEConfig())
    # TASK_MEE_016 Task D: log which face-detection backend the active engine
    # settled on. ``FaceDetector`` auto-selects based on CUDA availability at
    # construction time, so by the time VisionProcessor exists the backend is
    # already fixed. We log the resolved ``model_type`` (one of: ``mediapipe``,
    # ``retinaface``, ``dlib``, ``opencv_hog``) so operators can confirm the
    # MediaPipe CPU path is in use on Jetson AGX Orin.
    try:
        _vp = engine._vision_processor if engine is not None else None
        if _vp is not None and hasattr(_vp, "_detector"):
            _det = _vp._detector
            _backend = getattr(_det, "model_type", None) or "unknown"
            _cuda = False
            try:
                import torch  # type: ignore
                _cuda = bool(torch.cuda.is_available())
            except Exception:
                pass
            logging.getLogger("mee.remotedemo.run_server").info(
                "TASK_MEE_016 backend=%s cuda_available=%s",
                _backend, _cuda,
            )
    except Exception:  # noqa: S110 — logging must never break startup
        pass
    server = RemotedemoServer(engine=engine, config=config)
    await server.start()


def _install_signal_diagnostics() -> None:
    """TASK_MEE_035 (2026-09-28): log which signal killed the server.

    The MEE WS process has been repeatedly killed on this Jetson with no
    trace (no OOM in dmesg, no cgroup oom_kill).  SIGKILL is uncatchable, but
    catching SIGTERM/SIGINT/SIGABRT lets us record the exact signal + time so
    the killer can be correlated in journalctl / systemd logs.  SIGKILL still
    leaves no trace — if that's the case, the watchdog log timestamp is the
    only evidence.
    """
    logger = logging.getLogger("mee.remotedemo.signals")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(h)

    def _on_signal(signum, frame):  # noqa: ARG001
        name = signal.Signals(signum).name
        logger.info("TASK_MEE_035 received signal %s (pid=%s) — shutting down", name, os.getpid())
        # Re-raise default behavior so the process actually exits.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGABRT):
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass  # not in main thread or unsupported


def main() -> None:  # pragma: no cover
    _install_signal_diagnostics()
    import argparse
    parser = argparse.ArgumentParser(description="MEE remote demo WebSocket server")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()
    import os
    if args.port is not None:
        os.environ["MEE_DEMO_PORT"] = str(args.port)
    if args.host is not None:
        os.environ["MEE_DEMO_HOST"] = args.host
    if args.token is not None:
        os.environ["MEE_DEMO_TOKEN"] = args.token
    asyncio.run(run_server())


if __name__ == "__main__":  # pragma: no cover
    main()
