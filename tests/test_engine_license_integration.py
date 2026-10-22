"""R12-R15, R40, R41, R46 — EmotionEngine licensing integration (TASK_MEE_015)."""
from __future__ import annotations

import pytest

from mee.api import (
    EmotionEngine,
    LicenseExpiredError,
    license_status,
)
from mee.licensing.client import LicenseClient
from mee.licensing.config import LicensingConfig


class _FakeLicenseClient:
    """Stub license client injected into EmotionEngine for integration tests."""

    def __init__(self, valid=True, license_status="active", features=None):
        self._valid = valid
        self._status = license_status
        self._features = features or {}
        self.verify_calls = 0

    def verify(self, force_network=False):
        self.verify_calls += 1
        from mee.licensing.results import VerificationResult
        import time
        return VerificationResult(
            valid=self._valid,
            license_status=self._status,
            plan_id="plan-1",
            plan_name="Pro",
            features=self._features,
            offline=False,
            last_verified_at=time.time(),
        )

    def status(self):
        return {
            "status": "licensed" if self._valid else "expired",
            "plan_id": "plan-1",
            "plan_name": "Pro",
            "remaining_days": 30 if self._valid else None,
            "offline": False,
            "features": self._features,
            "device_id": "device-test",
            "last_verified": None,
        }


def _engine_with_client(fake_client):
    engine = EmotionEngine()
    engine._license_client = fake_client
    return engine


def test_init_does_not_touch_licensing():
    """R12: EmotionEngine.__init__ performs NO license check."""
    engine = EmotionEngine()
    assert engine._license_client is None


def test_process_raises_on_invalid_license():
    """R10, R42: process() raises LicenseExpiredError when the license
    is in an invalid lifecycle state (e.g. revoked)."""
    engine = _engine_with_client(
        _FakeLicenseClient(valid=False, license_status="revoked"))
    with pytest.raises(LicenseExpiredError):
        engine.process()


def test_process_raises_on_suspended_license():
    """R42: suspended licenses are never valid — hard stop."""
    engine = _engine_with_client(
        _FakeLicenseClient(valid=False, license_status="suspended"))
    with pytest.raises(LicenseExpiredError):
        engine.process()


def test_process_works_when_license_valid():
    """R11, R12: process() proceeds when license is valid."""
    engine = _engine_with_client(_FakeLicenseClient(valid=True))
    result = engine.process()
    assert "face" in result
    assert "overall" in result


def test_health_license_block_when_client_initialized():
    """R13, R46: health() includes the license block whenever the
    license client has been initialized (by lazy process() init or by
    explicit injection). Omitted only when ``self._license_client`` is
    None (R46 backward compat — see test_health_license_block_omitted)."""
    engine = _engine_with_client(_FakeLicenseClient(valid=True))
    h = engine.health()
    assert "license" in h
    lic = h["license"]
    assert lic["status"] == "licensed"
    assert lic["plan_id"] == "plan-1"
    assert lic["plan_name"] == "Pro"
    assert lic["remaining_days"] == 30
    assert lic["features"] == {}


def test_health_license_block_omitted_when_no_client():
    """R46: if self._license_client is None, omit the license key entirely."""
    engine = EmotionEngine()
    h = engine.health()
    assert "license" not in h


def test_process_multiple_calls_reuse_client():
    """R12: multiple process() calls reuse the same license client."""
    fake = _FakeLicenseClient(valid=True)
    engine = _engine_with_client(fake)
    engine.process()
    engine.process()
    assert fake.verify_calls == 2
    assert engine._license_client is fake


def test_license_status_never_raises(monkeypatch, tmp_path):
    """R14: license_status() never raises — returns a default dict on error."""
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    result = license_status()
    assert isinstance(result, dict)
    assert "status" in result


def test_license_expired_error_is_importable_from_api():
    """R15: LicenseExpiredError is importable from mee.api."""
    from mee.api import LicenseExpiredError as LEE
    assert LEE is LicenseExpiredError
    # And from the errors module.
    from mee.licensing.errors import LicenseExpiredError as LEE2
    assert LEE is LEE2
