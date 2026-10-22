"""Stable device ID generation for MEE licensing (TASK_MEE_015).

R16: ``MEE_DEVICE_ID`` env var takes precedence. Otherwise a stable ID is
derived as ``sha256(machine_id + boot_uuid)`` → first 16 hex chars,
persisted at ``$MEE_HOME/device_id``.

R17: The device ID is sent as the ``identifier`` JSON field on all Keygate
SDK calls (CTO decision from Keygate 0.1.15 API docs — no separate
``X-Device-ID`` header).

R18: The same machine reports the same device ID across restarts (the file
is persisted; only ``/tmp``-transient state is lost).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

# /etc/machine-id is the standard stable machine identity on Linux.
_MACHINE_ID_PATH = "/etc/machine-id"
_BOOT_ID_PATH = "/proc/sys/kernel/random/boot_id"


def _read_machine_id() -> str:
    try:
        return Path(_MACHINE_ID_PATH).read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _read_boot_uuid() -> str:
    try:
        return Path(_BOOT_ID_PATH).read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _generate_device_id() -> str:
    """sha256(machine_id + boot_uuid) → first 16 hex chars (R16)."""
    h = hashlib.sha256((_read_machine_id() + _read_boot_uuid()).encode("utf-8"))
    return h.hexdigest()[:16]


def get_device_id(state_dir: Path | None = None) -> str:
    """Resolve the stable device ID (R16, R18).

    Precedence:
    1. ``MEE_DEVICE_ID`` env var
    2. ``$MEE_HOME/device_id`` file (persisted from a previous run)
    3. auto-generate via :func:`_generate_device_id` and persist

    The value is persisted to ``$MEE_HOME/device_id`` (or the given
    ``state_dir``) so it survives restarts (R18).
    """
    env_id = os.environ.get("MEE_DEVICE_ID", "").strip()
    if env_id:
        return env_id

    base = Path(state_dir) if state_dir is not None else Path(
        os.environ.get("MEE_HOME") or Path.home() / ".config" / "mee-licensing")
    path = base / "device_id"

    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    new_id = _generate_device_id()
    base.mkdir(parents=True, exist_ok=True)
    path.write_text(new_id + "\n", encoding="utf-8")
    return new_id
