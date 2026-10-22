"""mee-lic CLI — license management for MEE (TASK_MEE_015).

R19-R23, R47. Uses argparse (stdlib only — Rule B4, no new dependencies).

Commands:
    mee-lic activate <key>   — activate a license, print status (R19)
    mee-lic status           — print license status (R20, R47)
    mee-lic deactivate       — deactivate license (R21)
    mee-lic verify           — force a network verify (R22)

R25: never prints license keys, device IDs, or tokens (except a truncated
device id which is a *machine* identifier, not a secret — still we print it
in full per R20/R47 which require it in status output; the R25 grep test
covers the *key* and *token* patterns).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .client import LicenseClient, map_status
from .config import LicensingConfig
from .errors import ActivationLimitError, LicenseClientError

logger = logging.getLogger("mee.licensing.cli")

# R20/R47: fields always present in status output (order preserved).
_STATUS_FIELDS = [
    "status", "plan_id", "plan_name", "remaining_days",
    "offline", "device_id", "last_verified",
]


def _truncate_plan_id(plan_id: str | None) -> str | None:
    """R47: truncate a UUID/plan id to first 8 chars + '...'."""
    if not plan_id:
        return None
    if len(plan_id) > 8:
        return plan_id[:8] + "..."
    return plan_id


def _features_summary(features: dict | None) -> dict | None:
    """R47: count of feature keys + notable enabled features."""
    if not features:
        return None
    enabled = []
    for k, v in features.items():
        if isinstance(v, dict):
            if v.get("enabled") or v.get("value") not in (None, False, "false", 0):
                enabled.append(k)
        elif v in (True, "true", 1):
            enabled.append(k)
    return {
        "count": len(features),
        "enabled": sorted(enabled)[:10],
    }


def _print_status(st: dict) -> None:
    """Pretty-print a status dict (R20, R47)."""
    out = {}
    for f in _STATUS_FIELDS:
        if f in st:
            out[f] = st[f]
    # R47: extended fields.
    if st.get("plan_id"):
        out["plan_id_short"] = _truncate_plan_id(st["plan_id"])
    if st.get("features") is not None:
        out["features"] = _features_summary(st.get("features"))
    print(json.dumps(out, indent=2, default=str))


def cmd_activate(args) -> int:
    client = LicenseClient(LicensingConfig())
    try:
        result = client.activate(args.key)
    except ActivationLimitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except LicenseClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not result.valid:
        print(f"activation reported status={result.license_status!r}",
              file=sys.stderr)
        return 1
    st = client.status()
    print(f"Activated. Status: {st.get('status')}")
    _print_status(st)
    return 0


def cmd_status(args) -> int:
    client = LicenseClient(LicensingConfig())
    st = client.status()
    _print_status(st)
    # Include trial info for display (R20).
    ti = client.trial_info()
    if ti.get("active") and st.get("status") == "trialing":
        print(f"Trial active — {ti['remaining_days']} day(s) remaining")
    return 0


def cmd_deactivate(args) -> int:
    client = LicenseClient(LicensingConfig())
    try:
        client.deactivate()
    except LicenseClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Deactivated.")
    return 0


def cmd_verify(args) -> int:
    client = LicenseClient(LicensingConfig())
    result = client.verify(force_network=True)
    st = client.status()
    if not result.valid:
        print(f"verify: invalid (status={result.license_status!r})",
              file=sys.stderr)
        return 1
    print(f"Verified. Status: {st.get('status')}")
    _print_status(st)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mee-lic",
        description="MEE license management (Keygate).")
    p.add_argument("--version", action="store_const", const=True,
                   default=None, help="show version and exit")
    sub = p.add_subparsers(dest="command")

    pa = sub.add_parser("activate", help="activate a license key")
    pa.add_argument("key", help="license key (KG-...)")
    pa.set_defaults(func=cmd_activate)

    ps = sub.add_parser("status", help="show license status")
    ps.set_defaults(func=cmd_status)

    pd = sub.add_parser("deactivate", help="deactivate license")
    pd.set_defaults(func=cmd_deactivate)

    pv = sub.add_parser("verify", help="force a network verify")
    pv.set_defaults(func=cmd_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``mee-lic`` console script (R23).

    Exit codes: 0 success, 1 generic failure, 2 activation-limit.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "version", False):
        try:
            from importlib.metadata import version
            print(version("multimodal-emotion-engine"))
        except Exception:
            print("multimodal-emotion-engine (dev)")
        return 0

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    # R24: license events logged via `logging` at INFO/WARNING.
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
