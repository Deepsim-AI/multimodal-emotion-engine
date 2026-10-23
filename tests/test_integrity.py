"""TASK_MEE_020 (Phase C/D) — bytecode integrity self-check fail-safe tests.

AC4: integrity check detects modification of a critical installed file and
blocks inference; fail-safe behaviour proven (never defaults to allow).

Binding rules (Decision #4, CTO_PLAN §5):
  C10: integrity-check error / cannot read anchor → block (raise
       LicenseIntegrityError)
  C11: missing manifest / anchor → block (never default to allow)
  C12: network down + valid offline token → allow (handled by the client,
       not the integrity check)

Fail-safe enforcement point: ``EmotionEngine._license_check()`` invokes
``verify_installed_integrity()`` **before** license verification
(CTO_PLAN §8 Phase C, step C2).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from mee.licensing.integrity import (
    ANCHOR_FILENAME,
    compute_critical_digests,
    file_sha256,
    is_enabled,
    read_anchor_digests,
    set_integrity_hardened,
    verify_installed_integrity,
)
from mee.licensing.errors import LicenseIntegrityError, LicenseExpiredError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo_root() -> Path:
    """The MEE repo root (parent of the ``mee`` package)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def anchor_file(tmp_path, repo_root) -> Path:
    """Write a correct anchor file (matching the current source tree)."""
    digests = compute_critical_digests(repo_root)
    p = tmp_path / ANCHOR_FILENAME
    p.write_text("\n".join(f"{k}  {v}" for k, v in sorted(digests.items())),
                 encoding="utf-8")
    return p


@pytest.fixture
def anchor_env(anchor_file, monkeypatch):
    """Point MEE_INTEGRITY_ANCHOR at the correct anchor file and enable the
    check (simulating a signed/production build)."""
    monkeypatch.setenv("MEE_INTEGRITY_ANCHOR", str(anchor_file))
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")  # force enabled
    return anchor_file


@pytest.fixture(autouse=True)
def _no_hardening_by_default():
    """Ensure the build-time hardening flag is off for all tests unless a
    test explicitly enables it (keeps the dev/posture default consistent)."""
    set_integrity_hardened(False)


# ---------------------------------------------------------------------------
# Unit tests — integrity module
# ---------------------------------------------------------------------------

def test_compute_critical_digests_deterministic(repo_root):
    """Same source tree → same digests (reproducible builds)."""
    d1 = compute_critical_digests(repo_root)
    d2 = compute_critical_digests(repo_root)
    assert d1 == d2
    # All four critical files present.
    assert len(d1) == 4
    for key in ("mee/api/engine.py", "mee/licensing/client.py",
                "mee/licensing/offline.py", "mee/licensing/errors.py"):
        assert key in d1
        # SHA-256 hex is 64 lowercase chars.
        assert len(d1[key]) == 64
        assert d1[key] == d1[key].lower()


def test_file_sha256_correct(repo_root):
    """file_sha256 matches hashlib for a known file."""
    p = repo_root / "mee" / "licensing" / "errors.py"
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    assert file_sha256(p) == expected


def test_verify_passes_with_correct_anchor(anchor_env, repo_root):
    """C10 inverse: all files match anchor → no exception raised."""
    verify_installed_integrity(repo_root)  # should not raise


def test_verify_blocks_on_tampered_file(anchor_env, repo_root, monkeypatch, tmp_path):
    """AC4 / C10: modifying a critical file → LicenseIntegrityError.

    We simulate tampering by writing a corrupted anchor (as if the file on
    disk was modified) — this is the same code path the real check uses."""
    # Create a tampered anchor (wrong digest for engine.py).
    tampered = tmp_path / "tampered_anchor"
    digests = compute_critical_digests(repo_root)
    lines = []
    for k, v in sorted(digests.items()):
        if k == "mee/api/engine.py":
            v = "0" * 64  # wrong digest
        lines.append(f"{k}  {v}")
    tampered.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setenv("MEE_INTEGRITY_ANCHOR", str(tampered))
    with pytest.raises(LicenseIntegrityError, match="[Ii]ntegrity check failed"):
        verify_installed_integrity(repo_root)


def test_verify_blocks_on_missing_anchor(repo_root, monkeypatch):
    """C11: anchor file missing → LicenseIntegrityError (never allow)."""
    monkeypatch.delenv("MEE_INTEGRITY_ANCHOR", raising=False)
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")
    with pytest.raises(LicenseIntegrityError):
        verify_installed_integrity(repo_root)


def test_verify_blocks_on_unparseable_anchor(repo_root, monkeypatch, tmp_path):
    """C11: anchor line that is not a valid <path> <digest> pair → block.

    A single unparseable token is treated as a file key, so it surfaces as
    a key not present in the anchor set — still a fail-safe block.
    A two-field malformed line (bad digest) raises the "Malformed" error."""
    bad = tmp_path / "bad_anchor"
    bad.write_text("not a valid line\n", encoding="utf-8")
    monkeypatch.setenv("MEE_INTEGRITY_ANCHOR", str(bad))
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")
    with pytest.raises(LicenseIntegrityError):
        verify_installed_integrity(repo_root)


def test_verify_blocks_on_two_field_malformed_line(repo_root, monkeypatch, tmp_path):
    """C10: a two-token line with a non-hex digest is malformed → block."""
    bad = tmp_path / "bad_anchor"
    bad.write_text("mee/api/engine.py  NOT_A_DIGEST\n", encoding="utf-8")
    monkeypatch.setenv("MEE_INTEGRITY_ANCHOR", str(bad))
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")
    # This passes the split check (2 fields) but then mismatches → block.
    with pytest.raises(LicenseIntegrityError):
        verify_installed_integrity(repo_root)


def test_verify_blocks_on_empty_anchor(repo_root, monkeypatch, tmp_path):
    """C11: anchor file exists but contains no digests → block."""
    empty = tmp_path / "empty_anchor"
    empty.write_text("# only comments\n", encoding="utf-8")
    monkeypatch.setenv("MEE_INTEGRITY_ANCHOR", str(empty))
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")
    with pytest.raises(LicenseIntegrityError):
        verify_installed_integrity(repo_root)


def test_integrity_disabled_by_default_in_source(repo_root, monkeypatch):
    """Posture: in a source checkout (no anchor, hardening flag off) the check
    is disabled by default, so verify is a no-op (dev-friendly)."""
    monkeypatch.delenv("MEE_INTEGRITY_ANCHOR", raising=False)
    monkeypatch.delenv("MEE_INTEGRITY_CHECK", raising=False)
    set_integrity_hardened(False)
    assert is_enabled() is False
    verify_installed_integrity(repo_root)  # no exception (disabled)


def test_integrity_enabled_by_default_when_hardened(repo_root, monkeypatch):
    """Posture: a hardened (signed) build enables the check by default; with
    no anchor present it must then block (C11) — never silently allow."""
    monkeypatch.delenv("MEE_INTEGRITY_ANCHOR", raising=False)
    monkeypatch.delenv("MEE_INTEGRITY_CHECK", raising=False)
    set_integrity_hardened(True)
    assert is_enabled() is True
    with pytest.raises(LicenseIntegrityError):
        verify_installed_integrity(repo_root)


def test_integrity_disabled_via_env(repo_root, monkeypatch):
    """MEE_INTEGRITY_CHECK=0 disables the check even in a hardened build
    (recovery escape hatch)."""
    set_integrity_hardened(True)      # simulate signed build
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "0")
    assert is_enabled() is False
    monkeypatch.delenv("MEE_INTEGRITY_ANCHOR", raising=False)
    verify_installed_integrity(repo_root)  # no exception (runtime override off)


def test_license_integrity_error_is_license_expired_subclass():
    """R4: LicenseIntegrityError is a subclass of LicenseExpiredError,
    so existing ``except LicenseExpiredError`` paths remain valid."""
    assert issubclass(LicenseIntegrityError, LicenseExpiredError)
    exc = LicenseIntegrityError()
    assert exc.integrity_failure is True


def test_license_integrity_error_importable_from_api():
    """LicenseIntegrityError is importable from mee.api and mee.licensing."""
    from mee.api import LicenseIntegrityError as A
    from mee.licensing import LicenseIntegrityError as L
    from mee.licensing.errors import LicenseIntegrityError as E
    assert A is L is E


# ---------------------------------------------------------------------------
# Engine gate integration
# ---------------------------------------------------------------------------

def test_engine_gate_blocks_on_integrity_failure(repo_root, monkeypatch, tmp_path):
    """AC4 (engine level): process() raises LicenseIntegrityError when the
    integrity check is active and fails, BEFORE any license verification runs.

    We enable the check (signed-build posture) and monkeypatch the check to
    raise (simulating a real tamper), then confirm the engine gate propagates
    the exception."""
    import mee.licensing.integrity as integrity_mod

    def _raise(*a, **kw):
        raise LicenseIntegrityError("simulated tamper detection")

    integrity_mod.set_integrity_hardened(True)
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")
    monkeypatch.setattr(integrity_mod, "verify_installed_integrity", _raise)

    from mee.api import EmotionEngine, LicenseIntegrityError as LIE
    engine = EmotionEngine()
    with pytest.raises(LIE):
        engine.process()
    integrity_mod.set_integrity_hardened(False)


def test_engine_gate_passes_when_integrity_ok(repo_root, monkeypatch):
    """When the integrity check is active and passes, the gate proceeds to
    license verification (signed-build posture)."""
    import mee.licensing.integrity as integrity_mod

    def _pass(*a, **kw):
        pass  # integrity check passes

    integrity_mod.set_integrity_hardened(True)
    monkeypatch.setenv("MEE_INTEGRITY_CHECK", "1")
    monkeypatch.setattr(integrity_mod, "verify_installed_integrity", _pass)

    from mee.api import EmotionEngine
    from mee.licensing.results import VerificationResult

    class _FakeClient:
        def __init__(self):
            self.verify_calls = 0
        def verify(self, force_network=False):
            self.verify_calls += 1
            return VerificationResult(
                valid=True, license_status="active", plan_id="p1",
                plan_name="Pro", features={}, offline=False,
                last_verified_at=time.time())
        def status(self):
            return {"status": "licensed", "plan_id": "p1", "plan_name": "Pro",
                    "remaining_days": 30, "offline": False, "features": {},
                    "device_id": "d", "last_verified": None}

    engine = EmotionEngine()
    engine._license_client = _FakeClient()
    result = engine.process()
    assert "face" in result
    assert "overall" in result
    integrity_mod.set_integrity_hardened(False)
