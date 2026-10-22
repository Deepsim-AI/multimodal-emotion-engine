"""R19-R23, R47 — mee-lic CLI tests (TASK_MEE_015)."""
from __future__ import annotations

import io
import json
import re
import sys
from contextlib import redirect_stdout, redirect_stderr

import pytest

from mee.licensing.cli import build_parser, main


def _run_cli(argv, tmp_path, monkeypatch):
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    monkeypatch.delenv("MEE_LICENSE_KEY", raising=False)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def test_help(tmp_path, monkeypatch):
    # argparse's --help prints and raises SystemExit(0) — catch it.
    import pytest
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    with redirect_stdout(out), redirect_stderr(err):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
    assert exc.value.code == 0
    assert "usage" in out.getvalue().lower()


def _extract_json(text: str) -> dict:
    """Parse the first JSON object from CLI output (ignoring trailing
    human-readable lines like the trial-remaining notice)."""
    # Find the first '{' and matching '}'.
    start = text.index("{")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("no JSON object found in CLI output")


def test_status_trial_mode(tmp_path, monkeypatch):
    code, out, err = _run_cli(["status"], tmp_path, monkeypatch)
    assert code == 0
    data = _extract_json(out)
    assert data["status"] in ("trialing", "expired")
    # R20 required fields present.
    for f in ("status", "remaining_days", "offline", "device_id", "last_verified"):
        assert f in data


def test_activate_success(stub_keygate, tmp_path, monkeypatch):
    monkeypatch.setenv("MEE_LICENSE_SERVER", stub_keygate.url)
    code, out, err = _run_cli(
        ["activate", "KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"],
        tmp_path, monkeypatch)
    assert code == 0
    assert "Activated" in out
    data = _extract_json(out)
    assert data["status"] == "licensed"
    # R47: extended fields.
    assert "plan_id_short" in data
    assert "features" in data
    assert data["features"]["count"] >= 1


def test_status_after_activate(stub_keygate, tmp_path, monkeypatch):
    monkeypatch.setenv("MEE_LICENSE_SERVER", stub_keygate.url)
    _run_cli(["activate", "KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"],
             tmp_path, monkeypatch)
    code, out, err = _run_cli(["status"], tmp_path, monkeypatch)
    assert code == 0
    data = _extract_json(out)
    assert data["status"] == "licensed"
    assert data["plan_name"] == "Pro"


def test_deactivate(stub_keygate, tmp_path, monkeypatch):
    monkeypatch.setenv("MEE_LICENSE_SERVER", stub_keygate.url)
    _run_cli(["activate", "KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"],
             tmp_path, monkeypatch)
    code, out, err = _run_cli(["deactivate"], tmp_path, monkeypatch)
    assert code == 0
    assert "Deactivated" in out


def test_verify_forces_network_no_license_falls_to_trial(stub_keygate, tmp_path, monkeypatch):
    """R22 + R41: verify forces a network call. With no license
    activated the server returns 404 (oracle-hardened). Per R41 the
    client falls through to trial evaluation — a fresh trial marker is
    created and the result is valid (trialing). The CLI reports success
    with status=trialing."""
    monkeypatch.setenv("MEE_LICENSE_SERVER", stub_keygate.url)
    code, out, err = _run_cli(["verify"], tmp_path, monkeypatch)
    assert code == 0
    assert "Verified" in out
    assert "trialing" in out


def test_verify_succeeds_when_activated(stub_keygate, tmp_path, monkeypatch):
    """R22: with a valid license, verify returns success.

    A real Keygate returns 200 + token on /verify for an *active* license.
    The stub's /verify default is 404 (the oracle "no license" case), so we
    script a success response here to model the active-license path.
    """
    from tests.conftest_stub_keygate import (
        PUB_KEY_HEX, make_token)
    token = make_token(status="active")
    stub_keygate.state["verify_response"] = (
        200, {"success": True, "data": {
            "status": "active",
            "plan_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "plan_name": "Pro",
            "features": {"premium_support": True},
            "token": token,
            "public_key": PUB_KEY_HEX,
        }})
    monkeypatch.setenv("MEE_LICENSE_SERVER", stub_keygate.url)
    _run_cli(["activate", "KG-TESTKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"],
             tmp_path, monkeypatch)
    code, out, err = _run_cli(["verify"], tmp_path, monkeypatch)
    stub_keygate.state["verify_response"] = None
    assert code == 0
    assert "Verified" in out


def test_no_key_in_output(stub_keygate, tmp_path, monkeypatch):
    """R25: license key must never appear in CLI stdout/stderr."""
    monkeypatch.setenv("MEE_LICENSE_SERVER", stub_keygate.url)
    key = "KG-SECRETKEY-ABCDEFGH-IJKLMNOP-QRSTUVWX"
    code, out, err = _run_cli(["activate", key], tmp_path, monkeypatch)
    combined = out + err
    assert key not in combined
    # General KG- pattern should not leak either.
    assert not re.search(r"\bKG-[A-Za-z0-9]{4,}(?:-[A-Za-z0-9]{4,})+\b", combined)
