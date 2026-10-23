"""MEE licensing package (TASK_MEE_015, Gate C).

Public exports (re-exported by ``mee.api`` for the public API surface):
- :class:`LicenseClient` — Keygate HTTP client (R1)
- :class:`VerificationResult` — rich verify() return (R28)
- :class:`LicenseClientError` / :class:`ActivationLimitError` (R1, R38)
- :class:`LicenseExpiredError` — raised from ``EmotionEngine.process()`` (R10, R15)
- :class:`LicenseIntegrityError` — raised on tamper detection (TASK_MEE_020, C10/C11)
- :class:`LicensingConfig` / :class:`TrialConfig` (R2, R31)
"""

from __future__ import annotations

from .client import LicenseClient
from .config import LicensingConfig, TrialConfig
from .errors import (
    ActivationLimitError,
    LicenseClientError,
    LicenseExpiredError,
    LicenseIntegrityError,
)
from .results import VerificationResult

__all__ = [
    "LicenseClient",
    "LicensingConfig",
    "TrialConfig",
    "ActivationLimitError",
    "LicenseClientError",
    "LicenseExpiredError",
    "LicenseIntegrityError",
    "VerificationResult",
]
