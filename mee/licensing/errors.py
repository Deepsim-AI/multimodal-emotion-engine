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


class LicenseIntegrityError(LicenseExpiredError):
    """Raised from ``EmotionEngine.process()`` when the bytecode integrity
    self-check detects a tampered or corrupted installation (TASK_MEE_020).

    Subclass of :class:`LicenseExpiredError` so that existing error-handling
    paths (``except LicenseExpiredError``) remain valid — the two failure
    modes are indistinguishable to the caller (inference is blocked either
    way). Fail-safe binding rules C10/C11 (Decision #4, CTO_PLAN §5):

    - C10: integrity-check error / cannot read anchor → **block**
    - C11: missing manifest / anchor → **block** (never default to allow)

    The only permitted pass-through is C12: network down + valid offline
    token (handled by the licensing client, not by the integrity check).
    """

    def __init__(self,
                 message: str = (
                     "License integrity check failed. The installation may be "
                     "tampered or corrupted. Reinstall MEE from the official "
                     "signed release.")):
        super().__init__(message)
        self.integrity_failure: bool = True
