"""Configuration for MEE licensing (TASK_MEE_015).

R2: env-var driven configuration:
- ``MEE_LICENSE_SERVER`` (default ``https://licenses.deepsim.ai:8443``)
- ``MEE_LICENSE_KEY`` (optional — auto-activate on first verify)
- ``MEE_DEVICE_ID`` (optional — overrides auto-generation)
- ``MEE_HOME`` (default ``~/.config/mee-licensing/``)
- ``MEE_TRIAL_DAYS`` (optional — trial duration override, R31)

Per CTO decision (CTO_PLAN §3.4), licensing config is **separate** from
``MEEConfig`` (SRP) — the core engine config is not polluted with license
concerns.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LICENSE_SERVER = "https://licenses.deepsim.ai:8443"
DEFAULT_HOME = "~/.config/mee-licensing"


def _default_home() -> Path:
    env = os.environ.get("MEE_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path(os.path.expanduser(DEFAULT_HOME))


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@dataclass(frozen=False)
class LicensingConfig:
    """Configuration for the MEE license client (R2)."""

    server_url: str | None = None      # MEE_LICENSE_SERVER
    license_key: str | None = None     # MEE_LICENSE_KEY
    device_id: str | None = None       # MEE_DEVICE_ID
    home_dir: Path | None = None       # MEE_HOME

    def __post_init__(self) -> None:
        if self.server_url is None:
            self.server_url = os.environ.get(
                "MEE_LICENSE_SERVER", "").strip() or DEFAULT_LICENSE_SERVER
        if self.license_key is None:
            self.license_key = os.environ.get("MEE_LICENSE_KEY", "").strip() or None
        if self.home_dir is None:
            self.home_dir = _default_home()

    @property
    def home_dir_resolved(self) -> Path:
        """``$MEE_HOME`` resolved to an absolute Path (R3)."""
        return Path(self.home_dir).expanduser()

    @property
    def state_dir(self) -> Path:
        """The ``licenses/`` subdirectory, created if needed (R3)."""
        d = self.home_dir_resolved / "licenses"
        d.mkdir(parents=True, exist_ok=True)
        return d


@dataclass(frozen=False)
class TrialConfig:
    """Trial configuration — defaults are configurable, not assumptions
    (R31, Amendment B).

    Resolution precedence for :meth:`get_trial_days` (R31):

    1. Keygate plan feature ``trial_period_days`` — server-authoritative,
       the only source that can differ per plan.
    2. ``MEE_TRIAL_DAYS`` env var — operator override.
    3. ``TrialConfig.trial_days`` default (14 days).

    :meth:`can_trial` honours the ``trial_enabled`` plan feature (R32): a
    plan that sets ``trial_enabled`` to a falsy value disables trials
    entirely (e.g. Enterprise/OEM tiers).
    """

    trial_days: int = 14
    _trial_enabled_default: bool = True

    def __post_init__(self) -> None:
        # Honour MEE_TRIAL_DAYS env var as the baseline (overridable by
        # plan features at resolution time).
        env = _env_int("MEE_TRIAL_DAYS")
        if env is not None:
            self.trial_days = env

    def get_trial_days(self,
                       plan_name: str | None = None,
                       features: dict | None = None) -> int:
        """Resolve the trial duration (R31).

        Precedence (highest first):
        1. Keygate plan feature ``trial_period_days`` (if present and
           parseable as int)
        2. ``MEE_TRIAL_DAYS`` env var (already applied in ``__post_init__``
           to ``self.trial_days``)
        3. the ``trial_days`` field default (14)

        Note: ``plan_name`` is accepted for interface completeness but is
        **never** used in any conditional decision (R35 / Amendment F).
        """
        if features and "trial_period_days" in features:
            val = features["trial_period_days"]
            if isinstance(val, dict):
                # Keygate feature envelope: {enabled, value_type, value,...}
                val = val.get("value")
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return self.trial_days

    def can_trial(self, features: dict | None = None) -> bool:
        """Check whether trials are allowed for this plan (R32).

        Returns False when the plan's ``trial_enabled`` feature is
        explicitly falsy; otherwise True. This is the mechanism by which
        Enterprise/OEM plans can disable trials entirely.
        """
        if features and "trial_enabled" in features:
            val = features["trial_enabled"]
            if isinstance(val, dict):
                val = val.get("enabled", val.get("value"))
            if val is False or val == "false" or val == 0:
                return False
        return self._trial_enabled_default
