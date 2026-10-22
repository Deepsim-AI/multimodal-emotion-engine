"""Shared stub Keygate server for licensing tests (TASK_MEE_015).

Uses stdlib ``http.server`` — no third-party dependency (TEST_STRATEGY §4).

The stub supports configurable per-endpoint behavior via a mutable
``state`` dict on the server instance so individual tests can script
responses (success, 404, ACTIVATION_LIMIT, network failure, etc.).
"""
from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from mee.licensing.offline import generate_test_keypair, sign_test_token

# Module-level test keypair (deterministic per import; tests can regenerate).
PRIV_KEY_HEX, PUB_KEY_HEX = generate_test_keypair()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


class StubKeygate:
    """In-process Keygate stub with scripted responses.

    Attributes:
        state: mutable dict with keys:
            - "activate_response": (status_code, body_dict) or None
            - "verify_response":   (status_code, body_dict) or None
            - "deactivate_response": (status_code, body_dict) or None
            - "fail_network": bool — if True, raise a connection-level error
    """

    def __init__(self):
        self.state: dict = {
            "activate_response": None,
            "verify_response": None,
            "deactivate_response": None,
            "fail_network": False,
        }
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.url: str = ""

    def start(self):
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def _read_body(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b""
                try:
                    return json.loads(raw) if raw else {}
                except Exception:
                    return {}

            def _send(self, code, body):
                payload = json.dumps(body).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                body = self._read_body()
                path = self.path
                if state["fail_network"]:
                    # Simulate a network-level failure by closing without a
                    # response (client sees a connection error).
                    self.close_connection = True
                    self.connection.close()
                    return
                if path == "/api/v1/license/activate":
                    code, resp = state["activate_response"] or (
                        200,
                        {"success": True, "data": self._ok_data(body)},
                    )
                elif path == "/api/v1/license/verify":
                    code, resp = state["verify_response"] or (
                        404, {"success": False, "error": "LICENSE_NOT_FOUND"},
                    )
                elif path == "/api/v1/license/deactivate":
                    code, resp = state["deactivate_response"] or (
                        200, {"success": True},
                    )
                else:
                    code, resp = 404, {"error": "not found"}
                self._send(code, resp)

            def _ok_data(self, body):
                import time
                now = int(time.time())
                payload = {
                    "lid": "11111111-2222-3333-4444-555555555555",
                    "pid": "product-mee",
                    "pln": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "sts": "active",
                    "did": body.get("identifier", ""),
                    "ftr": {"premium_support": True, "api_access": True},
                    "iat": now,
                    "exp": 604800,  # 7-day check-in window
                }
                token = sign_test_token(payload, PRIV_KEY_HEX)
                return {
                    "status": "active",
                    "plan_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "plan_name": "Pro",
                    "features": {"premium_support": True, "api_access": True},
                    "token": token,
                    "public_key": PUB_KEY_HEX,
                }

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None


import pytest


@pytest.fixture
def stub_keygate():
    server = StubKeygate().start()
    yield server
    server.stop()


@pytest.fixture
def test_pubkey():
    return PUB_KEY_HEX


@pytest.fixture
def test_privkey():
    return PRIV_KEY_HEX


def make_token(status="active", features=None, iat_offset=0, ttl=604800,
               plan_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"):
    """Build a signed token for tests (valid ed25519 signature)."""
    import time
    now = int(time.time()) + iat_offset
    payload = {
        "lid": "11111111-2222-3333-4444-555555555555",
        "pid": "product-mee",
        "pln": plan_id,
        "sts": status,
        "did": "device-xyz",
        "ftr": features or {"premium_support": True},
        "iat": now,
        "exp": ttl,
    }
    return sign_test_token(payload, PRIV_KEY_HEX)
