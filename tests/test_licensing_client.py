"""R1, R3-R7, R17, R28-R30, R35-R39, R41, R42 — LicenseClient tests.

Uses the stub Keygate server from conftest_stub_keygate.
"""
from __future__ import annotations

import json
import time

import pytest

from mee.licensing.client import (
    HTTP_TIMEOUT_S,
    LicenseClient,
    map_status,
)
from mee.licensing.config import LicensingConfig
from mee.licensing.errors import (
    ActivationLimitError,
    LicenseClientError,
)
from mee.licensing.results import VerificationResult


def _client(stub, tmp_path, license_key="KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"):
    cfg = LicensingConfig(
        server_url=stub.url,
        license_key=license_key,
        home_dir=tmp_path,
    )
    return LicenseClient(cfg)


# ------------------------------------------------------------------
# R29 — verify() returns VerificationResult with correct fields
# ------------------------------------------------------------------

def test_verify_returns_verification_result(stub_keygate, tmp_path):
    stub_keygate.state["verify_response"] = (200, {
        "success": True,
        "data": {
            "status": "active",
            "plan_id": "plan-uuid-1",
            "plan_name": "Pro",
            "features": {"premium_support": True},
            "token": "tok.sig",
            "public_key": "pk",
        },
    })
    client = _client(stub_keygate, tmp_path)
    result = client.verify(force_network=True)
    assert isinstance(result, VerificationResult)
    assert result.valid is True
    assert result.license_status == "active"
    assert result.plan_id == "plan-uuid-1"
    assert result.plan_name == "Pro"
    assert result.features == {"premium_support": True}
    assert result.offline is False
    assert result.last_verified_at is not None


def test_verify_unknown_status_passthrough(stub_keygate, tmp_path):
    """R29: unknown/unmapped status strings are passed through literally."""
    stub_keygate.state["verify_response"] = (200, {
        "success": True,
        "data": {
            "status": "custom_future_state",
            "plan_id": "p", "plan_name": "X",
            "features": {}, "token": "t.s", "public_key": "pk",
        },
    })
    client = _client(stub_keygate, tmp_path)
    result = client.verify(force_network=True)
    assert result.license_status == "custom_future_state"
    # Forward-compatible: treated as valid because server sent a token.
    assert result.valid is True


# ------------------------------------------------------------------
# R30 — status() mapping
# ------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("active", "licensed"),
    ("trialing", "trialing"),
    ("past_due", "expired"),
    ("canceled", "expired"),
    ("expired", "expired"),
    ("suspended", "degraded"),
    ("revoked", "degraded"),
    ("unknown_state", "unknown_state"),  # passthrough
    (None, None),
])
def test_status_map(raw, expected):
    assert map_status(raw) == expected


# ------------------------------------------------------------------
# R42 — suspended / revoked are never valid
# ------------------------------------------------------------------

@pytest.mark.parametrize("state", ["suspended", "revoked"])
def test_suspended_revoked_not_valid(stub_keygate, tmp_path, state):
    stub_keygate.state["verify_response"] = (200, {
        "success": True,
        "data": {"status": state, "plan_id": "p", "plan_name": "X",
                 "features": {}, "token": "t.s", "public_key": "pk"},
    })
    client = _client(stub_keygate, tmp_path)
    result = client.verify(force_network=True)
    assert result.valid is False
    assert result.license_status == state


# ------------------------------------------------------------------
# R36 — unknown features stored but not crashing
# ------------------------------------------------------------------

def test_unknown_features_preserved(stub_keygate, tmp_path):
    stub_keygate.state["verify_response"] = (200, {
        "success": True,
        "data": {
            "status": "active", "plan_id": "p", "plan_name": "Pro",
            "features": {"unknown_feature_xyz": {"enabled": True}},
            "token": "t.s", "public_key": "pk",
        },
    })
    client = _client(stub_keygate, tmp_path)
    result = client.verify(force_network=True)
    assert result.features == {"unknown_feature_xyz": {"enabled": True}}


# ------------------------------------------------------------------
# R37 — missing entitlements default to disabled (documented behavior)
# ------------------------------------------------------------------

def test_missing_features_default_to_none(stub_keygate, tmp_path):
    stub_keygate.state["verify_response"] = (200, {
        "success": True,
        "data": {"status": "active", "plan_id": "p", "plan_name": "Pro",
                 "features": {}, "token": "t.s", "public_key": "pk"},
    })
    client = _client(stub_keygate, tmp_path)
    result = client.verify(force_network=True)
    assert result.features == {}
    # A consumer checking an absent key gets a falsy default.
    assert result.features.get("api_access") is None
    assert bool((result.features or {}).get("api_access", {}).get("enabled", False)) is False


# ------------------------------------------------------------------
# R38, R39 — ACTIVATION_LIMIT handling
# ------------------------------------------------------------------

def test_activate_activation_limit(stub_keygate, tmp_path):
    stub_keygate.state["activate_response"] = (403, {
        "success": False, "error": "ACTIVATION_LIMIT",
        "message": "max_activations reached",
    })
    client = _client(stub_keygate, tmp_path)
    with pytest.raises(ActivationLimitError) as excinfo:
        client.activate("KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX")
    assert excinfo.value.limit_hit is True


def test_activate_success_caches_state(stub_keygate, tmp_path):
    # Default activate_response returns a valid signed token.
    client = _client(stub_keygate, tmp_path)
    result = client.activate("KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX")
    assert result.valid is True
    assert result.license_status == "active"
    # State file written under $MEE_HOME/licenses/
    import glob
    files = glob.glob(str(tmp_path / "licenses" / "*.json"))
    assert len(files) == 1
    state = json.loads(open(files[0]).read())
    assert state["license_key"] == "KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"
    assert state["token"]  # cached token present


# ------------------------------------------------------------------
# R6 — deactivate removes local state
# ------------------------------------------------------------------

def test_deactivate_removes_state(stub_keygate, tmp_path):
    client = _client(stub_keygate, tmp_path)
    client.activate("KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX")
    import glob
    assert glob.glob(str(tmp_path / "licenses" / "*.json"))
    client.deactivate()
    assert not glob.glob(str(tmp_path / "licenses" / "*.json"))


# ------------------------------------------------------------------
# R41 — offline fallback on network failure
# ------------------------------------------------------------------

def test_verify_offline_fallback_on_network_error(stub_keygate, tmp_path, test_pubkey):
    from mee.licensing.offline import sign_test_token
    # First, do a successful verify to cache a valid token.
    client = _client(stub_keygate, tmp_path)
    client.activate("KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX")
    # Now simulate a network failure on verify.
    stub_keygate.state["fail_network"] = True
    result = client.verify(force_network=True)
    # The cached (valid, within-TTL) token should let it pass offline.
    assert result.valid is True
    assert result.offline is True


def test_verify_network_error_no_token_falls_to_trial(stub_keygate, tmp_path):
    """R41: network error + no cached token + no license key → trial
    evaluation. The _trial_result(allow_create=True) path creates a
    fresh marker on first run."""
    stub_keygate.state["fail_network"] = True
    client = _client(stub_keygate, tmp_path, license_key=None)
    result = client.verify(force_network=True)
    # No key present → trial path with allow_create=True.
    assert result.valid is True
    assert result.license_status == "trialing"
    assert (tmp_path / "licenses" / ".trial").exists()


def test_verify_network_error_with_key_and_no_token_is_invalid(stub_keygate, tmp_path):
    """R41: network error + license key present + no valid cached token
    + no active trial → invalid (hard stop). The key's invalidity is
    the real signal — no trial marker is created."""
    stub_keygate.state["fail_network"] = True
    client = _client(stub_keygate, tmp_path,
                     license_key="KG-SOMEKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX")
    result = client.verify(force_network=True)
    # Key present, no token, no trial → invalid.
    assert result.valid is False
    # No trial marker should have been created.
    assert not (tmp_path / "licenses" / ".trial").exists()


# ------------------------------------------------------------------
# R7 — timeout constant
# ------------------------------------------------------------------

def test_http_timeout_is_5s():
    assert HTTP_TIMEOUT_S == 5.0
