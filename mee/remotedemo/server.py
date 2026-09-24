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

Design constraints (from CTO_PLAN.md + G3_RESPONSE.md):
  - Thin wrapper: every inference result is exactly EmotionEngine.process() output.
  - Single-threaded inference per connection; global max_connections cap.
  - Rate limiting: max_fps per connection; oversized payloads rejected.
  - Auth: token as first WS text message; failure closes the connection.
  - Audit log: every auth outcome (success/failure) appended to auth_log_file.
  - CORS: Access-Control-Allow-Origin header on the WebSocket upgrade.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Optional

try:
    import websockets
    from websockets.server import serve
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore[assignment]
    serve = None  # type: ignore[assignment]

from .config import RemotedemoConfig

PROTOCOL_VERSION = "mee-remotedemo-v1"
MAX_AUTH_TIMEOUT_S = 5.0
MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_AUDIO_CHUNK_SAMPLES = 16000


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
        self.config.resolve_token()
        origins = self._cors_origins()
        self._server = await serve(
            self._handle,
            host=self.config.host,
            port=self.config.port,
            max_size=MAX_FRAME_BYTES + 8 * 1024,
            **({"origins": self.config.cors_origin} if self.config.cors_origin != "*" else {}),
        )
        self._auditor.record("server", "started",
                             f"host={self.config.host} port={self.config.port}")
        await self._server.wait_closed()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    # -- connection handler ---------------------------------------------

    async def _handle(self, ws) -> None:
        client_ip = ws.remote_address[0] if ws.remote_address else "unknown"
        self.active_connections += 1
        try:
            token = await self._auth(ws)
            if token is None:
                return
            self._auditor.record(client_ip, "auth_success", "token-ok")
            await ws.send(json.dumps({
                "type": "auth_ok",
                "protocol": PROTOCOL_VERSION,
            }))
            await self._main_loop(ws)
        except Exception as exc:  # noqa: BLE001 — connection-level catch-all
            self._auditor.record(client_ip, "error", str(exc)[:200])
            try:
                await ws.send(json.dumps({
                    "type": "error", "code": "internal", "message": "internal error"}))
            except Exception:
                pass
        finally:
            self.active_connections -= 1
            self._auditor.record(client_ip, "closed", "")

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
        if not provided or provided != self.config.token:
            self._auditor.record("conn", "auth_failure", "token mismatch")
            await ws.send(json.dumps({
                "type": "error", "code": "bad_token", "message": "invalid access token"}))
            await ws.close(code=1008, reason="invalid token")
            return None
        return provided

    async def _main_loop(self, ws) -> None:
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
            mtype = msg.get("type")
            if mtype == "ping":
                await ws.send(json.dumps({"type": "pong", "ts": time.time()}))
            elif mtype == "stop":
                last_result = None
                await ws.send(json.dumps({"type": "stopped"}))
            elif mtype == "frame":
                await self._process_frame(ws, msg, limiter)
            elif mtype == "audio":
                await self._process_audio(ws, msg)
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
        result = self._infer(frame_bgr=frame_bgr, audio=None)
        await ws.send(json.dumps({
            "type": "result",
            "server_ts": time.time(),
            "source": "frame",
            "data": serialize_result(result),
        }))

    async def _process_audio(self, ws, msg: dict) -> None:
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
        result = self._infer(frame_bgr=None, audio=audio)
        await ws.send(json.dumps({
            "type": "result",
            "server_ts": time.time(),
            "source": "audio",
            "data": serialize_result(result),
        }))

    def _infer(self, frame_bgr=None, audio=None) -> dict:
        """Call the engine exactly as the public API contract expects."""
        return self.engine.process(video_frame=frame_bgr, audio=audio)


async def run_server(engine=None, config: Optional[RemotedemoConfig] = None) -> None:
    """Convenience entrypoint: build engine (if needed) + serve forever."""
    if engine is None:
        from mee import EmotionEngine, MEEConfig
        engine = EmotionEngine(config=MEEConfig())
    server = RemotedemoServer(engine=engine, config=config)
    await server.start()


def main() -> None:  # pragma: no cover
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
