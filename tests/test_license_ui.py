"""TASK_MEE_019: License Plan Selection & Purchase UI — automated tests.

Covers:
  - CommunityRequestRateLimiter: basic policy, TTL expiry, IP limit,
    email/IP independence
  - LicenseHTTPServer: GET /license/status, POST /license/activate,
    POST /license/deactivate, POST /license/request-community (rate-limited)
  - Config: license_http_port default + env override
  - Security: KEYGATE_API_KEY resolution (server-side only)

No new runtime dependencies — uses stdlib `http.server` (already used by
LicenseHTTPServer) and `pytest` already in requirements.txt.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from unittest import mock

import pytest

# Ensure repo root is importable regardless of how pytest is invoked.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from mee.remotedemo.config import RemotedemoConfig
from mee.remotedemo.server import (
    COMMUNITY_EMAIL_WINDOW_S,
    COMMUNITY_IP_WINDOW_S,
    COMMUNITY_LIMIT_EMAIL,
    COMMUNITY_LIMIT_IP,
    CommunityRequestRateLimiter,
    LicenseHTTPServer,
    _keygate_api_key,
    _keygate_base_url,
    _license_status_dict,
    _sanitize_err,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg(tmp_path):
    """Isolated RemotedemoConfig with a free port for the license HTTP server."""
    return RemotedemoConfig(
        token="test-token",
        token_file=tmp_path / "token",
        auth_log_file=tmp_path / "auth.log",
        license_http_port=18999,  # high port unlikely to collide
    )


@pytest.fixture
def fake_engine():
    """Stand-in EmotionEngine (not used by license endpoints, but required
    by RemotedemoServer.__init__)."""
    class FakeEngine:
        def process(self, video_frame=None, audio=None):
            return {"face": {"emotion": "happy"}, "voice": {"emotion": "happy"},
                    "overall": {"emotion": "happy"}}
    return FakeEngine()


@pytest.fixture
def license_server():
    """A live LicenseHTTPServer on a high port, cleaned up after the test."""
    srv = LicenseHTTPServer(
        port=18999,
        engine=None,
        keygate_api_key="kg_test_123",
        community_limiter=CommunityRequestRateLimiter(),
    )
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture
def license_server_no_key():
    """LicenseHTTPServer without a Keygate API key (tests the 500 path)."""
    srv = LicenseHTTPServer(
        port=18998,
        engine=None,
        keygate_api_key=None,
        community_limiter=CommunityRequestRateLimiter(),
    )
    srv.start()
    yield srv
    srv.stop()


def _get(url: str) -> tuple:
    """HTTP GET helper. Returns (status_code, body_dict)."""
    import urllib.request
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: dict) -> tuple:
    """HTTP POST helper. Returns (status_code, body_dict)."""
    import urllib.request
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# CommunityRequestRateLimiter
# ---------------------------------------------------------------------------

class TestCommunityRequestRateLimiter:
    def test_first_request_allowed(self):
        rl = CommunityRequestRateLimiter()
        allowed, retry = rl.check("user@example.com", "1.2.3.4")
        assert allowed is True
        assert retry == 0

    def test_second_same_email_denied(self):
        """AC6: 1 request per email per 24h."""
        rl = CommunityRequestRateLimiter()
        rl.check("user@example.com", "1.2.3.4")
        allowed, retry = rl.check("user@example.com", "5.6.7.8")
        assert allowed is False
        assert retry > 0

    def test_email_ttl_expiry(self):
        """After 86401s the same email is allowed again."""
        rl = CommunityRequestRateLimiter()
        rl.check("user@example.com", "1.2.3.4")
        # Simulate time passing beyond the window
        with mock.patch("time.time", return_value=time.time() + COMMUNITY_EMAIL_WINDOW_S + 1):
            allowed, _ = rl.check("user@example.com", "5.6.7.8")
        assert allowed is True

    def test_ip_limit_3_emails(self):
        """AC6: 3 requests per IP per hour — 4th (different email) denied."""
        rl = CommunityRequestRateLimiter()
        for i in range(COMMUNITY_LIMIT_IP):
            allowed, _ = rl.check(f"user{i}@example.com", "10.0.0.1")
            assert allowed is True, f"request {i+1} should be allowed"
        # 4th email from same IP → denied
        allowed, retry = rl.check("user9@example.com", "10.0.0.1")
        assert allowed is False
        assert retry > 0

    def test_ip_ttl_expiry(self):
        """After 3601s a new email from the same IP is allowed again."""
        rl = CommunityRequestRateLimiter()
        for i in range(COMMUNITY_LIMIT_IP):
            rl.check(f"user{i}@example.com", "10.0.0.1")
        with mock.patch("time.time", return_value=time.time() + COMMUNITY_IP_WINDOW_S + 1):
            allowed, _ = rl.check("user_new@example.com", "10.0.0.1")
        assert allowed is True

    def test_email_ip_independent(self):
        """Same email from different IPs counts independently per IP.
        But the email limit (1/24h) is global — so a second request with
        the same email is always denied regardless of IP."""
        rl = CommunityRequestRateLimiter()
        allowed1, _ = rl.check("user@example.com", "1.1.1.1")
        assert allowed1 is True
        allowed2, _ = rl.check("user@example.com", "2.2.2.2")
        assert allowed2 is False  # email limit hit

    def test_different_emails_same_ip_allowed_up_to_limit(self):
        """3 different emails from the same IP are all allowed."""
        rl = CommunityRequestRateLimiter()
        for i in range(3):
            allowed, _ = rl.check(f"user{i}@example.com", "9.9.9.9")
            assert allowed is True

    def test_reset(self):
        rl = CommunityRequestRateLimiter()
        rl.check("a@b.com", "1.1.1.1")
        rl.reset()
        allowed, _ = rl.check("a@b.com", "2.2.2.2")
        assert allowed is True

    def test_empty_email_is_single_identity(self):
        """Empty email is treated as one identity — 2nd request denied.
        (The email limit is global: 1 per email per 24h, even if empty.)"""
        rl = CommunityRequestRateLimiter()
        allowed1, _ = rl.check("", "1.1.1.1")
        assert allowed1 is True
        allowed2, _ = rl.check("", "2.2.2.2")
        assert allowed2 is False  # same (empty) email → denied


# ---------------------------------------------------------------------------
# Config: license_http_port
# ---------------------------------------------------------------------------

class TestLicenseHttpPortConfig:
    def test_default_is_port_plus_1000(self, tmp_path):
        c = RemotedemoConfig(
            token_file=tmp_path / "token",
            auth_log_file=tmp_path / "auth.log",
        )
        assert c.license_http_port == c.port + 1000

    def test_env_override(self, tmp_path):
        old = os.environ.get("MEE_DEMO_HTTP_PORT")
        try:
            os.environ["MEE_DEMO_HTTP_PORT"] = "19999"
            c = RemotedemoConfig(
                token_file=tmp_path / "token",
                auth_log_file=tmp_path / "auth.log",
            )
            assert c.license_http_port == 19999
        finally:
            if old is None:
                os.environ.pop("MEE_DEMO_HTTP_PORT", None)
            else:
                os.environ["MEE_DEMO_HTTP_PORT"] = old

    def test_explicit_override(self, tmp_path):
        c = RemotedemoConfig(
            token_file=tmp_path / "token",
            auth_log_file=tmp_path / "auth.log",
            license_http_port=12345,
        )
        assert c.license_http_port == 12345


# ---------------------------------------------------------------------------
# Keygate API key resolution (S1: server-side only)
# ---------------------------------------------------------------------------

class TestKeygateApiKeyResolution:
    def test_env_var(self):
        old = os.environ.get("MEE_KEYGATE_API_KEY")
        try:
            os.environ["MEE_KEYGATE_API_KEY"] = "kg_test_from_env"
            assert _keygate_api_key() == "kg_test_from_env"
        finally:
            if old is None:
                os.environ.pop("MEE_KEYGATE_API_KEY", None)
            else:
                os.environ["MEE_KEYGATE_API_KEY"] = old

    def test_file_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MEE_KEYGATE_API_KEY", raising=False)
        monkeypatch.setenv("MEE_HOME", str(tmp_path))
        keyfile = tmp_path / "keygate_api_key"
        keyfile.write_text("kg_test_from_file\n")
        assert _keygate_api_key() == "kg_test_from_file"

    def test_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MEE_KEYGATE_API_KEY", raising=False)
        monkeypatch.setenv("MEE_HOME", str(tmp_path))
        # No file → None
        assert _keygate_api_key() is None

    def test_env_wins_over_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MEE_KEYGATE_API_KEY", "kg_env")
        monkeypatch.setenv("MEE_HOME", str(tmp_path))
        keyfile = tmp_path / "keygate_api_key"
        keyfile.write_text("kg_file\n")
        assert _keygate_api_key() == "kg_env"  # env wins


# ---------------------------------------------------------------------------
# LicenseHTTPServer endpoints (integration)
# ---------------------------------------------------------------------------

class TestLicenseHttpServerStatus:
    """GET /license/status — never raises, always returns valid JSON."""

    def test_status_returns_valid_shape(self, license_server):
        status, body = _get("http://127.0.0.1:18999/license/status")
        assert status == 200
        assert "status" in body
        assert "device_id" in body

    def test_status_has_expected_fields(self, license_server):
        _, body = _get("http://127.0.0.1:18999/license/status")
        for field in ("status", "plan_id", "plan_name",
                      "remaining_days", "offline", "device_id"):
            assert field in body, f"missing field: {field}"

    def test_404_for_unknown_path(self, license_server):
        status, _ = _get("http://127.0.0.1:18999/unknown-path")
        assert status == 404

    def test_healthz(self, license_server):
        status, body = _get("http://127.0.0.1:18999/healthz")
        assert status == 200
        assert body.get("status") == "ok"


class TestLicenseHttpServerActivate:
    """POST /license/activate — calls LicenseClient.activate()."""

    def test_missing_key_returns_400(self, license_server):
        status, body = _post("http://127.0.0.1:18999/license/activate", {})
        assert status == 400
        assert body.get("valid") is False
        assert "key" in body.get("message", "").lower()

    def test_empty_key_returns_400(self, license_server):
        status, body = _post("http://127.0.0.1:18999/license/activate", {"key": ""})
        assert status == 400
        assert body.get("valid") is False

    def test_valid_key_returns_200(self, license_server):
        """Mock LicenseClient.activate to return a successful result."""
        from mee.licensing.results import VerificationResult
        result = VerificationResult(
            valid=True, license_status="active", plan_name="Developer",
            plan_id="plan-123", features={"full": True},
            offline=False, last_verified_at=1761129600.0,
        )
        with mock.patch("mee.licensing.client.LicenseClient.activate",
                        return_value=result):
            status, body = _post(
                "http://127.0.0.1:18999/license/activate",
                {"key": "KG-TEST-KEY-123"},
            )
        assert status == 200
        assert body.get("valid") is True
        assert body.get("plan_name") == "Developer"
        assert body.get("status") == "active"


class TestLicenseHttpServerDeactivate:
    """POST /license/deactivate — calls LicenseClient.deactivate()."""

    def test_deactivate_returns_200(self, license_server):
        with mock.patch("mee.licensing.client.LicenseClient.deactivate") as mock_deact:
            status, body = _post("http://127.0.0.1:18999/license/deactivate", {})
            assert status == 200
            assert body.get("status") == "deactivated"
            mock_deact.assert_called_once()


class TestLicenseHttpServerCommunityRequest:
    """POST /license/request-community — rate-limited proxy to Keygate."""

    def test_missing_name_returns_400(self, license_server):
        status, body = _post(
            "http://127.0.0.1:18999/license/request-community",
            {"email": "test@example.com"},
        )
        assert status == 400
        assert "name" in body.get("error", "").lower()

    def test_missing_email_returns_400(self, license_server):
        status, body = _post(
            "http://127.0.0.1:18999/license/request-community",
            {"name": "John Doe"},
        )
        assert status == 400
        assert "email" in body.get("error", "").lower()

    def test_invalid_email_returns_400(self, license_server):
        status, body = _post(
            "http://127.0.0.1:18999/license/request-community",
            {"name": "John Doe", "email": "not-an-email"},
        )
        assert status == 400
        assert "email" in body.get("error", "").lower()

    def test_short_name_returns_400(self, license_server):
        status, body = _post(
            "http://127.0.0.1:18999/license/request-community",
            {"name": "A", "email": "valid@example.com"},
        )
        assert status == 400
        assert "name" in body.get("error", "").lower()

    def test_rate_limited_second_request(self, license_server):
        """AC6: second request from same email → 429."""
        url = "http://127.0.0.1:18999/license/request-community"
        # First request: valid fields → should reach Keygate (mocked) or 500
        # (no real Keygate). We just need to confirm it's NOT 429 on first hit.
        with mock.patch("requests.post") as mock_post:
            mock_resp = mock.Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "success": True,
                "data": {"license_key": "KG-TEST-001"},
            }
            mock_post.return_value = mock_resp
            status1, body1 = _post(url, {
                "name": "Alice", "email": "alice@university.edu",
            })
            # First request should succeed (mocked Keygate)
            assert status1 == 200
            assert body1.get("license_key") == "KG-TEST-001"

        # Second request with same email → 429 (rate limited)
        status2, body2 = _post(url, {
            "name": "Alice", "email": "alice@university.edu",
        })
        assert status2 == 429
        assert "retry_after" in body2
        assert "too many" in body2.get("message", "").lower()

    def test_ip_rate_limit_4th_email(self, license_server):
        """4th different email from same IP → 429."""
        url = "http://127.0.0.1:18999/license/request-community"
        for i in range(3):
            with mock.patch("requests.post") as mock_post:
                mock_resp = mock.Mock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "success": True,
                    "data": {"license_key": f"KG-TEST-{i}"},
                }
                mock_post.return_value = mock_resp
                status, body = _post(url, {
                    "name": f"User {i}",
                    "email": f"user{i}@example.com",
                })
                assert status == 200, f"email {i} should be allowed"
        # 4th email → 429
        status, body = _post(url, {
            "name": "User 4",
            "email": "user4@example.com",
        })
        assert status == 429

    def test_no_keygate_key_returns_500(self, license_server_no_key):
        """Without KEYGATE_API_KEY the endpoint returns 500 (S1)."""
        status, body = _post(
            "http://127.0.0.1:18998/license/request-community",
            {"name": "Alice", "email": "alice@example.com"},
        )
        assert status == 500
        assert "KEYGATE_API_KEY" in body.get("error", "")


# ---------------------------------------------------------------------------
# _license_status_dict (shared helper)
# ---------------------------------------------------------------------------

class TestLicenseStatusDict:
    @mock.patch("mee.licensing.client.LicenseClient.status")
    def test_returns_expected_shape(self, mock_status):
        mock_status.return_value = {
            "status": "licensed",
            "plan_id": "plan-123",
            "plan_name": "Developer",
            "remaining_days": 365,
            "offline": False,
            "device_id": "dev-abc",
            "features": ["full"],
            "last_verified": "2026-10-22T00:00:00Z",
        }
        result = _license_status_dict()
        assert result["status"] == "licensed"
        assert result["plan_name"] == "Developer"
        assert result["remaining_days"] == 365
        assert result["offline"] is False
        assert result["device_id"] == "dev-abc"

    @mock.patch("mee.licensing.client.LicenseClient.status",
                side_effect=RuntimeError("boom"))
    def test_error_returns_unknown(self, mock_status):
        result = _license_status_dict()
        assert result["status"] == "unknown"
        assert result["offline"] is True
        assert "error" in result


# ---------------------------------------------------------------------------
# _sanitize_err
# ---------------------------------------------------------------------------

class TestSanitizeErr:
    def test_strips_bearer_token(self):
        s = _sanitize_err(Exception("error Bearer kg_secret_12345678 detail"))
        assert "kg_secret_12345678" not in s
        assert "***" in s

    def test_truncates_long_errors(self):
        s = _sanitize_err(Exception("x" * 500))
        assert len(s) <= 200

    def test_short_error_unchanged(self):
        s = _sanitize_err(Exception("simple error"))
        assert "simple error" in s
