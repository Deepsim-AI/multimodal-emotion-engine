"""Exception hierarchy for MEE licensing (TASK_MEE_015).

TASK_MEE_015 R15: ``LicenseExpiredError`` is the public exception raised from
``EmotionEngine.process()`` when no valid license is available. It is
importable via ``from mee.api import LicenseExpiredError`` (re-exported) as
well as ``from mee.licensing.errors import LicenseExpiredError``.
"""

from __future__ import annotations


class LicenseClientError(Exception):
    """Base class for Keygate client errors (R1)."""


class ActivationLimitError(LicenseClientError):
    """Raised when Keygate rejects activation due to the plan's
    ``max_activations`` cap (R38, R39).

    The device limit is enforced server-side by Keygate only — the client
    never counts or enforces device limits itself. This exception is the
    client-visible effect of the server-side cap.
    """

    def __init__(self,
                 message: str = (
                     "Device activation limit reached. Deactivate another "
                     "device in the Keygate portal or contact support.")):
        super().__init__(message)
        self.limit_hit: bool = True


class LicenseExpiredError(Exception):
    """Raised from ``EmotionEngine.process()`` when no valid license is
    available (expired trial, or no valid online/offline license) (R10, R15).
    """
