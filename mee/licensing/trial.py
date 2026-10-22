"""Trial marker logic for MEE licensing (TASK_MEE_015).

TASK_MEE_015 R8-R11 (amended by R31-R34): client-local trial. The trial
marker is a best-effort courtesy gate — commercial enforcement is via the
Keygate activation cap + Stripe, not by this file.

R33: once a marker is written it CANNOT be reset or extended.
``write_trial_marker`` is a no-op if the file already exists. The only
way to start a new trial is to delete the ``.trial`` file.

R34: marker format uses ISO8601 (not unix timestamps) to prevent
timezone ambiguity.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import TrialConfig

logger = logging.getLogger(__name__)

_TRIAL_FILENAME = ".trial"
# A device that has deactivated a license must not silently re-enter a fresh
# trial on the next no-key process() call — that would let a user "borrow
# the trial back" by activate→deactivate. Spec acceptance chain (Gate C, line
# 163/363): `deactivate` → process() → LicenseExpiredError. The sentinel
# enforces that; `activate()` clears it so re-activation is normal.
_DEACTIVATED_FILENAME = ".deactivated"
# Rate limit for R9 warning: once per 10 minutes.
_WARNING_INTERVAL_S = 600.0
_last_warn_ts: float = 0.0


def _trial_path(state_dir: Path) -> Path:
    return Path(state_dir) / _TRIAL_FILENAME


def _deactivated_path(state_dir: Path) -> Path:
    return Path(state_dir) / _DEACTIVATED_FILENAME


def is_deactivated(state_dir: Path) -> bool:
    """True when a license was deactivated on this device and the sentinel
    is still present. A deactivated device does NOT get a fresh trial (see
    spec acceptance chain: deactivate → process() → LicenseExpiredError).
    """
    return _deactivated_path(state_dir).exists()


def mark_deactivated(state_dir: Path) -> None:
    """Record that a license was deactivated on this device (Gate C)."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    _deactivated_path(state_dir).write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        encoding="utf-8")


def clear_deactivated(state_dir: Path) -> None:
    """Clear the deactivation sentinel (called by ``activate()`` so a
    re-activation restores normal first-run / trial behavior)."""
    path = _deactivated_path(state_dir)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def write_trial_marker(state_dir: Path,
                       trial_days: int | None = None) -> Path:
    """Write the trial marker if it does not already exist (R8, R33).

    If the marker file already exists this is a **no-op** — the original
    ``first_seen`` and ``expires_at`` are preserved unchanged (R33).

    ``trial_days`` resolution precedence (R31, documented in
    :class:`~mee.licensing.config.TrialConfig.get_trial_days`):

    1. Keygate plan feature ``trial_period_days`` (server-authoritative)
    2. ``MEE_TRIAL_DAYS`` env var
    3. ``TrialConfig.trial_days`` default (14)

    Args:
        state_dir: Directory that will hold the ``.trial`` file
            (usually ``$MEE_HOME/licenses/``). Created if missing.
        trial_days: Optional explicit day count (used by callers that
            already resolved the value via ``TrialConfig``). If ``None``,
            the default 14-day window is used.

    Returns:
        Path to the ``.trial`` file.
    """
    state_dir = Path(state_dir)
    path = _trial_path(state_dir)
    if path.exists():
        # R33: marker is immutable once written — no reset, no extension.
        logger.debug("Trial marker already exists at %s — write is a no-op (R33)",
                     path)
        return path

    state_dir.mkdir(parents=True, exist_ok=True)
    days = int(trial_days) if trial_days is not None else TrialConfig().trial_days
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    marker = {
        "first_seen": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    logger.info("Trial started: first_seen=%s expires_at=%s (%d days)",
                marker["first_seen"], marker["expires_at"], days)
    return path


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO8601 timestamp (Z suffix or offset) to an aware UTC
    datetime (R34)."""
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_trial_expired(state_dir: Path) -> bool:
    """Return True when the trial has expired or no marker exists (R10).

    A missing marker is treated as **expired** so that the engine gate
    blocks usage until a marker is created (by
    :func:`ensure_trial_marker`) or a valid license is present.
    """
    path = _trial_path(state_dir)
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        expires_at = _parse_iso(data["expires_at"])
    except Exception:
        logger.warning("Trial marker unreadable — treating trial as expired")
        return True
    return datetime.now(timezone.utc) > expires_at


def trial_remaining_days(state_dir: Path) -> int | None:
    """Return the ceiling of fractional days remaining in the trial (R34).

    Returns ``None`` when no marker exists or the trial is expired.
    """
    path = _trial_path(state_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        expires_at = _parse_iso(data["expires_at"])
    except Exception:
        return None
    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return None
    return max(1, math.ceil(remaining / 86400.0))


def ensure_trial_marker(state_dir: Path,
                        features: dict | None = None) -> None:
    """Create the trial marker if it does not exist (R8, R31).

    Uses :class:`~mee.licensing.config.TrialConfig` to resolve the trial
    duration with the documented precedence (Keygate feature > env > default)
    and honours the ``trial_enabled`` feature flag (R32).

    This is the function called by the engine gate when no valid license
    is present. It is safe to call repeatedly.
    """
    tc = TrialConfig()
    if not tc.can_trial(features):
        # R32: this plan explicitly disables trials — no marker written.
        logger.debug("trial_enabled feature is False — trial not started (R32)")
        return
    days = tc.get_trial_days(features=features)
    write_trial_marker(state_dir, trial_days=days)


def _warn_trial_usage() -> None:
    """R9: log a warning on every process() call during an active trial,
    rate-limited to once per 10 minutes."""
    global _last_warn_ts
    import time
    now = time.monotonic()
    if now - _last_warn_ts >= _WARNING_INTERVAL_S:
        _last_warn_ts = now
        logger.warning(
            "MEE is running on a free trial. Activate a license to keep "
            "using MEE after the trial expires.")


def trial_active(state_dir: Path) -> bool:
    """True when a trial marker exists and has not expired."""
    path = _trial_path(state_dir)
    if not path.exists():
        return False
    return not is_trial_expired(state_dir)
