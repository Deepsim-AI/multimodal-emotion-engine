"""Public licensing API surface (TASK_MEE_015, Gate C).

R14: re-export :func:`license_status` — a thin wrapper over
``LicenseClient.status()``. The contract (CORE_CONTRACTS §1.4) requires
that ``license_status()`` **never raises** — it returns a sensible default
dict when no license client is configured or an error occurs.

Also re-exports the exception classes so consumers can do::

    from mee.api import LicenseExpiredError, license_status
"""

from __future__ import annotations

import logging
from typing import Any

from ..licensing.client import LicenseClient
from ..licensing.config import LicensingConfig
from ..licensing.errors import (
    ActivationLimitError,
    LicenseClientError,
    LicenseExpiredError,
    LicenseIntegrityError,
)
from ..licensing.results import VerificationResult

logger = logging.getLogger(__name__)


def license_status() -> dict[str, Any]:
    """Return the current MEE license status (R14, R30, R46).

    Thin wrapper over ``LicenseClient.status()``. Never raises — on any
    error returns a ``{"status": "unknown", ...}`` dict so that callers
    (e.g. ``mee.api`` health checks) can rely on a dict being returned.

    Returns:
        dict with keys (Amendment C / R30):
            status, plan_id, plan_name, remaining_days, offline, features
        plus device_id, last_verified for display.
    """
    try:
        client = LicenseClient(LicensingConfig())
        return client.status()
    except Exception as exc:  # noqa: BLE001 - contract: never raise
        logger.debug("license_status() failed: %s", type(exc).__name__)
        return {
            "status": "unknown",
            "plan_id": None,
            "plan_name": None,
            "remaining_days": None,
            "offline": False,
            "features": None,
            "device_id": None,
            "last_verified": None,
        }


__all__ = [
    "license_status",
    "LicenseClient",
    "LicensingConfig",
    "LicenseClientError",
    "ActivationLimitError",
    "LicenseExpiredError",
    "LicenseIntegrityError",
    "VerificationResult",
]
