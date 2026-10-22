"""Rich verification result for MEE licensing (TASK_MEE_015).

TASK_MEE_015 R28 (Amendment A): ``LicenseClient.verify()`` returns a
``VerificationResult`` instead of a bare bool. All fields are sourced from
Keygate's ``/verify`` response ``data`` field or from the locally cached
signed token — the client never asserts what type of license it has
(Amendment F: no plan-name matching).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of ``LicenseClient.verify()`` (R28, R29).

    Attributes:
        valid: True when the license is currently usable (online within TTL
            or offline within the signed token's TTL). A suspended/revoked
            license is always ``valid=False`` (R42).
        license_status: The raw Keygate lifecycle status string
            (``active``, ``trialing``, ``past_due``, ``canceled``, ``expired``,
            ``suspended``, ``revoked``, or any future state — passed through
            literally, forward-compatible per R29). ``None`` when no license
            information is available at all.
        plan_id: Keygate plan UUID (or ``None``).
        plan_name: Keygate plan display name (or ``None``). Display-only —
            NEVER used in conditional logic (R35).
        features: Keygate entitlements map. Unknown keys are preserved but
            never grant implicit capabilities (R36); absent known keys
            default to disabled (R37).
        offline: True when the result was produced from the locally cached
            signed token (network unreachable), False when produced from a
            live Keygate response.
        last_verified_at: Unix timestamp (seconds) of the last successful
            verification, or ``None``.
    """

    valid: bool
    license_status: str | None = None
    plan_id: str | None = None
    plan_name: str | None = None
    features: dict | None = None
    offline: bool = False
    last_verified_at: float | None = None

    @property
    def ok(self) -> bool:
        """Backward-compatible alias for ``valid``."""
        return self.valid
