#!/usr/bin/env python3
"""E2E smoke test for MEE licensing (TASK_MEE_015, Gate C).

Runs the full chain against a stub Keygate server in an isolated temp
``$MEE_HOME``:

  1. ``mee-lic status`` → "trialing" (first run, no license)
  2. ``mee-lic activate KG-...`` → "licensed, active"
  3. ``EmotionEngine().process()`` → works (valid license)
  4. Network kill → ``process()`` → still works within token TTL (offline)
  5. Token TTL expired → ``process()`` → LicenseExpiredError
  6. ``mee-lic deactivate`` → ``process()`` → LicenseExpiredError

Exits 0 on success, 1 on any assertion failure.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.conftest_stub_keygate import StubKeygate  # noqa: E402
from mee.licensing.cli import main as cli_main  # noqa: E402
from mee.api import EmotionEngine, LicenseExpiredError  # noqa: E402


def _run_cli(argv, env):
    import io
    from contextlib import redirect_stdout, redirect_stderr
    old = {}
    for k, v in env.items():
        old[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main(argv)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return code, out.getvalue(), err.getvalue()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mee_smoke_"))
    env_home = {"MEE_HOME": str(tmp), "MEE_LICENSE_KEY": None,
                "MEE_DEVICE_ID": None}
    print(f"[smoke] MEE_HOME = {tmp}")

    stub = StubKeygate().start()
    env_server = {**env_home, "MEE_LICENSE_SERVER": stub.url}
    # Keep MEE_HOME + MEE_LICENSE_SERVER set in the real os.environ so the
    # in-process EmotionEngine() steps (3-6) read the same isolated state dir
    # as the CLI steps. Without this the engine falls back to
    # ~/.config/mee-licensing/licenses and the smoke test is not isolated.
    os.environ["MEE_HOME"] = str(tmp)
    os.environ["MEE_LICENSE_SERVER"] = stub.url
    os.environ.pop("MEE_LICENSE_KEY", None)
    os.environ.pop("MEE_DEVICE_ID", None)
    KEY = "KG-SMOKEKEY1-ABCDEFGH-IJKLMNOP-QRSTUVWX"
    failures = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)

    try:
        # 1. status → trialing
        print("\n[1] mee-lic status (first run)")
        code, out, err = _run_cli(["status"], env_server)
        check("exit 0", code == 0, f"code={code} err={err[:200]}")
        check("status=trialing", "trialing" in out, out[:200])

        # 2. activate
        print("\n[2] mee-lic activate")
        code, out, err = _run_cli(["activate", KEY], env_server)
        check("exit 0", code == 0, f"code={code} err={err[:200]}")
        check("status=licensed", "licensed" in out, out[:200])

        # 3. process() with valid license
        print("\n[3] EmotionEngine.process() (valid license)")
        engine = EmotionEngine()
        try:
            engine.process()
            check("process() succeeds", True)
        except Exception as e:
            check("process() succeeds", False, f"{type(e).__name__}: {e}")

        # 4. offline mode (network kill)
        print("\n[4] process() with network down (offline within TTL)")
        stub.state["fail_network"] = True
        engine2 = EmotionEngine()
        try:
            engine2.process()
            check("offline process() succeeds", True)
        except Exception as e:
            check("offline process() succeeds", False, f"{type(e).__name__}: {e}")
        stub.state["fail_network"] = False

        # 5. Server rejects the license (404 oracle-hardened) + no trial
        # → LicenseExpiredError. Use force_network=True to bypass the
        # cached-token shortcut and hit the 404 path.
        print("\n[5] token TTL lapsed + server rejects (404) + no trial → LicenseExpiredError")
        # Spec acceptance chain (Gate C): "Wait for token TTL (or mock time)
        # → process() → LicenseExpiredError". The cached-token fast path is
        # correct offline behavior (step 4 depends on it), so to exercise the
        # 404 reject path we lapse the cached token first (mock time), THEN
        # make the server reject. A signed token within TTL must still win.
        licenses_dir = tmp / "licenses"
        for sf in licenses_dir.glob("*.json"):
            sf.unlink()  # mock token TTL expiry
        stub.state["verify_response"] = (404, {"success": False, "error": "LICENSE_NOT_FOUND"})
        # R10: raise when the trial is EXPIRED and no valid license is present.
        # Deleting .trial is not enough — the no-key path (R8) would re-create a
        # fresh 14-day trial and allow the call (correctly). To exercise the
        # hard-stop we must write an *expired* marker (mock the 14 days elapsing).
        import json as _json
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        _exp = _dt.now(_tz.utc) - _td(days=1)
        (licenses_dir / ".trial").write_text(_json.dumps({
            "first_seen": (_exp - _td(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": _exp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }))
        engine3 = EmotionEngine()
        try:
            engine3.process()
            check("server-rejected + no trial raises", False, "no exception raised")
        except LicenseExpiredError:
            check("server-rejected + no trial raises LicenseExpiredError", True)
        except Exception as e:
            check("server-rejected + no trial raises LicenseExpiredError", False,
                  f"got {type(e).__name__}: {e}")
        stub.state["verify_response"] = None

        # 6. deactivate → no license state, no trial → LicenseExpiredError
        print("\n[6] mee-lic deactivate → process() raises")
        code, out, err = _run_cli(["deactivate"], env_server)
        check("deactivate exit 0", code == 0, f"code={code} err={err[:200]}")
        # Deactivate writes the .deactivated sentinel and removes .trial;
        # ensure no stray trial marker lets the call through.
        _trial6 = licenses_dir / ".trial"
        if _trial6.exists():
            _trial6.unlink()
        engine4 = EmotionEngine()
        try:
            engine4.process()
            check("post-deactivate raises", False, "no exception raised")
        except LicenseExpiredError:
            check("post-deactivate raises LicenseExpiredError", True)
        except Exception as e:
            check("post-deactivate raises LicenseExpiredError", False,
                  f"got {type(e).__name__}: {e}")

    finally:
        stub.stop()

    print(f"\n[smoke] {len(failures)} failure(s)")
    if failures:
        for f in failures:
            print(f"  FAILED: {f}")
        return 1
    print("[smoke] ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
