"""TASK_MEE_020 (Phase D, Decision #5) — offline license grace-window matrix.

AC5: offline behaviour is documented + tested. Binding rule C12 (Decision #4,
CTO_PLAN §5): **network down + valid offline token → allow** (the only
permitted pass-through); expired/invalid + offline → **block**.

These tests exercise the REAL ``LicenseClient`` against the in-process stub
Keygate (``tests/conftest_stub_keygate.py``) and assert the four-case matrix.
They do not touch ``EmotionEngine`` / model runtimes, so they are hermetic
and run offline.

Test matrix (Decision #5 / C12):
  | case | license state | network | outcome            |
  |------|---------------|---------|--------------------|
  V1   | valid (active)| online  | verify → valid     |
  V2   | valid (cached)| offline | verify → valid (C12) |
  V3   | expired/offline|offline | verify → invalid/block |
  V4   | invalid status| online  | verify → invalid   |
"""
from __future__ import annotations

import time

import pytest

from mee.licensing.client import LicenseClient
from mee.licensing.config import LicensingConfig
from mee.licensing.offline import sign_test_token
from mee.licensing.results import VerificationResult


def _client(tmp_path, server_url):
    cfg = LicensingConfig(
        server_url=server_url,
        license_key="KG-TEST-KEY-001",
        home_dir=tmp_path,
    )
    return LicenseClient(cfg), cfg


def test_valid_license_online_verify(stub_keygate, tmp_path):
    """V1: valid license + network reachable → verify is valid (online)."""
    client, cfg = _client(tmp_path, stub_keygate.url)
    client.activate("KG-TEST-KEY-001")          # online activate → cache token
    result = client.verify()
    assert result.valid is True
    assert result.license_status == "active"


def test_valid_license_offline_allow(stub_keygate, tmp_path):
    """V2 / C12: cached valid token + network DOWN → verify still valid.

    This is the only permitted pass-through (offline grace window)."""
    client, cfg = _client(tmp_path, stub_keygate.url)
    client.activate("KG-TEST-KEY-001")          # cache a signed token
    # Now simulate the network going down.
    stub_keygate.state["fail_network"] = True
    result = client.verify()
    assert result.valid is True, "C12: valid offline token must allow inference"


def test_expired_token_offline_blocks(stub_keygate, tmp_path, test_pubkey):
    """V3: token EXPIRED + network down → verify invalid (block)."""
    from tests.conftest_stub_keygate import PRIV_KEY_HEX
    client, cfg = _client(tmp_path, stub_keygate.url)
    # Seed a signed-but-expired token directly into the state file.
    now = int(time.time())
    expired_token = sign_test_token(
        {"sts": "active", "iat": now - 10_000_000, "exp": 600, "pln": "plan-1"},
        PRIV_KEY_HEX)
    import json
    state_path = client._state_path("KG-TEST-KEY-001")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "license_key": "KG-TEST-KEY-001",
        "device_id": "device-xyz",
        "token": expired_token,
        "public_key": test_pubkey,
        "status": "active",
    }), encoding="utf-8")
    stub_keygate.state["fail_network"] = True
    result = client.verify()
    assert result.valid is False, "expired offline token must block"


def test_invalid_status_online_blocks(stub_keygate, tmp_path):
    """V4: license in an invalid lifecycle state → verify invalid (block)."""
    client, cfg = _client(tmp_path, stub_keygate.url)
    stub_keygate.state["verify_response"] = (
        200,
        {"success": True, "data": {"status": "revoked", "plan_name": "Pro"}},
    )
    # Seed a license key so verify takes the licensed (not trial) path.
    import json
    state_path = client._state_path("KG-TEST-KEY-001")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "license_key": "KG-TEST-KEY-001",
        "device_id": "device-xyz",
        "status": "revoked",
    }), encoding="utf-8")
    result = client.verify(force_network=True)
    assert result.valid is False, "revoked license must block"


def test_verification_result_shape():
    """Guardrail: VerificationResult carries the fields the matrix relies on."""
    r = VerificationResult(valid=False, license_status="revoked", offline=False)
    assert r.valid is False
    assert r.license_status == "revoked"
    assert r.offline is False
