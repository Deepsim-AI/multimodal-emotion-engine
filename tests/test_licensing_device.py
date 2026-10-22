"""R16, R17, R18 — device ID tests (TASK_MEE_015)."""
from __future__ import annotations

import os
from pathlib import Path

from mee.licensing.device import get_device_id, _generate_device_id


def test_env_var_precedence(monkeypatch):
    monkeypatch.setenv("MEE_DEVICE_ID", "my-fixed-device-001")
    assert get_device_id() == "my-fixed-device-001"


def test_generated_id_is_16_hex_chars(tmp_path, monkeypatch):
    monkeypatch.delenv("MEE_DEVICE_ID", raising=False)
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    dev = get_device_id()
    assert len(dev) == 16
    int(dev, 16)  # must be valid hex


def test_id_persisted_and_stable(tmp_path, monkeypatch):
    monkeypatch.delenv("MEE_DEVICE_ID", raising=False)
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    first = get_device_id()
    second = get_device_id()
    assert first == second
    # File exists on disk.
    assert (tmp_path / "device_id").exists()


def test_stable_after_state_reuse(tmp_path, monkeypatch):
    """R18: same machine → same device ID across 'restarts' (new process
    would re-read the persisted file; here we simulate by deleting the
    in-memory cache is not possible at module scope, so we verify the
    file is the source of truth)."""
    monkeypatch.delenv("MEE_DEVICE_ID", raising=False)
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    a = get_device_id()
    # Manually wipe any cached value the test may have set on the module
    # (not present here, but defensive) and re-read from disk.
    assert (tmp_path / "device_id").read_text().strip() == a


def test_generate_deterministic_within_process():
    # _generate_device_id is deterministic on a given host (same machine-id
    # + boot_id within a single boot). Two calls in the same process must
    # agree.
    assert _generate_device_id() == _generate_device_id()
