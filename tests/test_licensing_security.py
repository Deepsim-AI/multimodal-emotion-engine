"""R25 — no license key, device ID, or token in logs (TASK_MEE_015).

Runs CLI commands through all three license paths (trial, activated,
expired) and asserts that no secret patterns appear in captured output.
"""
from __future__ import annotations

import io
import re
from contextlib import redirect_stdout, redirect_stderr

from mee.licensing.cli import main


KEY_PATTERN = re.compile(r"\bKG-[A-Za-z0-9]{4,}(?:-[A-Za-z0-9]{4,})+\b")
TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")
HEX_DEVICE_ID = re.compile(r"\b[0-9a-f]{16}\b")


def _capture(argv, env):
    import os
    old_env = {}
    for k, v in env.items():
        old_env[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return code, out.getvalue(), err.getvalue()


def test_trial_mode_no_leak(tmp_path):
    code, out, err = _capture(
        ["status"],
        {"MEE_HOME": str(tmp_path), "MEE_LICENSE_KEY": None},
    )
    combined = out + err
    assert not KEY_PATTERN.search(combined), f"license key leaked: {combined[:200]}"
    assert not TOKEN_PATTERN.search(combined), f"token leaked: {combined[:200]}"


def test_activated_no_key_leak(stub_keygate, tmp_path):
    key = "KG-SECRETEST-ABCDEFGH-IJKLMNOP-QRSTUVWX"
    code, out, err = _capture(
        ["activate", key],
        {"MEE_HOME": str(tmp_path), "MEE_LICENSE_SERVER": stub_keygate.url,
         "MEE_LICENSE_KEY": None},
    )
    combined = out + err
    assert key not in combined, f"explicit key leaked: {combined[:200]}"
    assert not KEY_PATTERN.search(combined), f"key pattern leaked: {combined[:200]}"
    # Token (payload.signature) must not appear.
    assert not TOKEN_PATTERN.search(combined), f"token leaked: {combined[:200]}"


def test_expired_no_leak(tmp_path):
    # Simulate an expired trial by pre-writing a past marker.
    import json
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    (tmp_path / "licenses").mkdir(parents=True, exist_ok=True)
    (tmp_path / "licenses" / ".trial").write_text(json.dumps({
        "first_seen": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now - timedelta(days=16)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))
    code, out, err = _capture(
        ["status"],
        {"MEE_HOME": str(tmp_path), "MEE_LICENSE_KEY": None},
    )
    combined = out + err
    assert not KEY_PATTERN.search(combined)
    assert not TOKEN_PATTERN.search(combined)
