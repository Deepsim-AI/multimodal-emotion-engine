"""R8-R11, R31-R34 — trial marker tests (TASK_MEE_015)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mee.licensing.trial import (
    ensure_trial_marker,
    is_trial_expired,
    trial_active,
    trial_remaining_days,
    write_trial_marker,
)


def test_marker_created_with_iso8601(tmp_path):
    write_trial_marker(tmp_path)
    data = json.loads((tmp_path / ".trial").read_text())
    assert "first_seen" in data and "expires_at" in data
    # ISO8601 with Z suffix (R34).
    assert data["first_seen"].endswith("Z")
    assert data["expires_at"].endswith("Z")
    # 14-day window by default.
    fs = datetime.fromisoformat(data["first_seen"].replace("Z", "+00:00"))
    ex = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    assert (ex - fs) == timedelta(days=14)


def test_marker_is_noop_if_exists(tmp_path):
    write_trial_marker(tmp_path, trial_days=7)
    first = json.loads((tmp_path / ".trial").read_text())
    # Attempt a second write with a different duration — must be a no-op (R33).
    write_trial_marker(tmp_path, trial_days=30)
    second = json.loads((tmp_path / ".trial").read_text())
    assert first == second


def test_is_trial_expired_false_when_active(tmp_path):
    write_trial_marker(tmp_path)
    assert is_trial_expired(tmp_path) is False


def test_is_trial_expired_true_when_missing(tmp_path):
    assert is_trial_expired(tmp_path) is True


def test_is_trial_expired_true_when_past(tmp_path):
    # Write a marker already in the past.
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=1)
    expires = now - timedelta(days=1)
    (tmp_path / ".trial").write_text(json.dumps({
        "first_seen": past.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))
    assert is_trial_expired(tmp_path) is True


def test_trial_active_reflects_marker(tmp_path):
    assert trial_active(tmp_path) is False
    write_trial_marker(tmp_path)
    assert trial_active(tmp_path) is True


def test_remaining_days_ceil(tmp_path):
    write_trial_marker(tmp_path, trial_days=14)
    days = trial_remaining_days(tmp_path)
    assert days is not None
    # Just under 14 days (a few ms elapsed since write) → ceil = 14.
    assert days == 14


def test_remaining_days_none_when_expired(tmp_path):
    now = datetime.now(timezone.utc)
    (tmp_path / ".trial").write_text(json.dumps({
        "first_seen": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now - timedelta(days=16)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))
    assert trial_remaining_days(tmp_path) is None


def test_ensure_trial_marker_respects_can_trial_false(tmp_path):
    # R32: plan feature disables trials → no marker written.
    ensure_trial_marker(tmp_path, features={"trial_enabled": False})
    assert not (tmp_path / ".trial").exists()


def test_ensure_trial_marker_uses_feature_days(tmp_path, monkeypatch):
    monkeypatch.delenv("MEE_TRIAL_DAYS", raising=False)
    ensure_trial_marker(tmp_path, features={"trial_period_days": "30"})
    data = json.loads((tmp_path / ".trial").read_text())
    fs = datetime.fromisoformat(data["first_seen"].replace("Z", "+00:00"))
    ex = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
    assert (ex - fs) == timedelta(days=30)
