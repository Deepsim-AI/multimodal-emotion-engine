"""API submodule — re-exports for public use.

TASK_MEE_015 (Gate C): re-export licensing surface (R14).
"""

from mee.api.engine import EmotionEngine, MEEConfig
from mee.api.license import (
    ActivationLimitError,
    LicenseClient,
    LicenseClientError,
    LicenseExpiredError,
    LicenseIntegrityError,
    LicensingConfig,
    VerificationResult,
    license_status,
)

__all__ = [
    "EmotionEngine",
    "MEEConfig",
    # Licensing (TASK_MEE_015)
    "license_status",
    "LicenseClient",
    "LicensingConfig",
    "LicenseClientError",
    "ActivationLimitError",
    "LicenseExpiredError",
    "LicenseIntegrityError",
    "VerificationResult",
]
