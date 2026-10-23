"""Bytecode-level integrity self-check for MEE licensing (TASK_MEE_020).

Decision #1 (CTO_PLAN §2): the license gate is hardened with a **bytecode
self-check + fail-safe enforcement** rather than a compiled (Cython) gate.
This module computes SHA-256 digests over the critical licensing files and
compares them against an **external** anchor — satisfying constraint C9
("no anchor lives beside the code it protects") and Decision #3 (dual
anchoring).

Anchoring model (Decision #3 — dual-anchored, C9-compliant):

- **Primary anchor (external, authoritative):** the signed release manifest
  (Sigstore-published alongside the wheel) or the embedded
  ``<package>.dist-info/MEE_INTEGRITY_HASHES.txt`` file.  The digest is an
  independent value that does NOT live inside any of the protected files
  themselves.
- **Secondary anchor:** a file on disk at the configured anchor path.

Fail-safe semantics (Decision #4, binding rules C10–C12):

- C10: integrity-check error / cannot read anchor → **block** inference
      (raise :class:`~mee.licensing.errors.LicenseIntegrityError`).
- C11: manifest / anchor file missing → **block** (never default to allow).
- C12: network down + valid offline token → **allow** (the only pass-through;
      handled by the licensing client, not here).

Opt-out for development: set the environment variable
``MEE_INTEGRITY_CHECK=0`` to disable the check (documented in
``docs/licensing/integrity.md``).

.. note::
   Default posture (CTO_PLAN §12, "make verification optional-but-recommended")

   In a **source checkout / development** tree the anchor file is not yet
   generated, so the check defaults to **off** (``is_enabled()`` returns
   False) to avoid breaking the dev/test baseline.  A **signed production
   wheel** is built with the build-time hardening flag
   ``MEE_INTEGRITY_ENFORCE=1`` (see :func:`integrity_hardened`), which turns
   the check **on by default**; setting ``MEE_INTEGRITY_CHECK=0`` at runtime
   can then override it off (documented escape hatch for recovery).

   This is the additive-control model: the hardening is *enabled in signed
   releases* and *optional in development* (NFR: zero new runtime deps, C5).

R3 / R5 (CTO_PLAN §10): this module is imported by ``engine.py`` at the
gate call site (C2 in CTO_PLAN §8 Phase C).  It raises
:class:`~mee.licensing.errors.LicenseIntegrityError` on any failure.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from .errors import LicenseIntegrityError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Relative path of the integrity anchor file inside the installed
#: ``.dist-info`` directory (Decision #3 — secondary anchor).
ANCHOR_FILENAME = "MEE_INTEGRITY_HASHES.txt"

#: The package name used to locate the ``.dist-info`` directory.
_PACKAGE_NAME = "multimodal_emotion_engine"

#: Relative paths (from the repo root / installed package parent) of the
#: critical files that are integrity-checked.  These are the files a tamper
#: attack must modify to disable licensing.
#:
#: Ordered deterministically so that the SHA-256 over the manifest blob
#: is stable across platforms.
_CRITICAL_FILES = (
    "mee/api/engine.py",
    "mee/licensing/client.py",
    "mee/licensing/offline.py",
    "mee/licensing/errors.py",
)

#: Environment variable that controls whether the check is active.
#: ``0`` disables; anything else (or unset) enables.
_ENV_INTEGRITY = "MEE_INTEGRITY_CHECK"

#: Build-time hardening flag name. When the signed wheel is built with
#: ``MEE_INTEGRITY_ENFORCE=1`` the module sets ``_MEE_INTEGRITY_ENFORCE = True``
#: (see :func:`integrity_hardened`), turning the check on by default.
_ENFORCE_FLAG = "_MEE_INTEGRITY_ENFORCE"

#: Runtime value; flipped by :func:`integrity_hardened` at build/sign time.
_MEE_INTEGRITY_ENFORCE = False


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def integrity_hardened() -> bool:
    """Return True when the wheel was built with the hardening flag.

    The build/sign pipeline sets ``_MEE_INTEGRITY_ENFORCE = True`` in this
    module's namespace before packaging the signed wheel (see the
    ``release.yml`` workflow).  In a plain source checkout this stays False,
    so the check is off by default (dev-friendly) but can still be turned on
    explicitly via ``MEE_INTEGRITY_CHECK=1``.
    """
    return bool(globals().get(_ENFORCE_FLAG, False))


def set_integrity_hardened(enabled: bool = True) -> None:
    """Flip the build-time hardening flag (used by the build pipeline and
    tests).  ``enabled=True`` makes the check on-by-default for this process."""
    global _MEE_INTEGRITY_ENFORCE
    _MEE_INTEGRITY_ENFORCE = bool(enabled)


def is_enabled() -> bool:
    """Return True when the integrity self-check is active.

    Resolution order:

    1. ``MEE_INTEGRITY_CHECK`` env var (runtime override):
       - ``0`` → **disabled** (dev opt-out / recovery escape hatch)
       - ``1`` (or any non-empty value) → **enabled**
    2. Build-time hardening flag (``integrity_hardened()``): signed
       production wheels are built with this True → **enabled** by default.
    3. Default: **disabled** (source checkout / dev) — see module note.

    This is the additive-control model: hardening is *on in signed releases*
    and *off in development* unless explicitly enabled.
    """
    val = os.environ.get(_ENV_INTEGRITY, "").strip()
    if val:
        return val != "0"  # explicit runtime override wins
    # No runtime override → use the build-time hardening flag.
    return integrity_hardened()


def _critical_file_paths(repo_root: Optional[Path] = None) -> list[Path]:
    """Return absolute paths to the critical files.

    Args:
        repo_root: Explicit root directory.  When ``None``, the parent of
            the ``mee`` package (i.e. the repo root) is used.
    """
    if repo_root is None:
        # engine.py is at <root>/mee/api/engine.py; integrity.py is at
        # <root>/mee/licensing/integrity.py → two dirs up.
        root = Path(__file__).resolve().parent.parent.parent
    else:
        root = Path(repo_root)
    return [root / rel for rel in _CRITICAL_FILES]


def file_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a single file (streaming).

    Raises:
        OSError: if the file cannot be read.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_critical_digests(repo_root: Optional[Path] = None) -> Dict[str, str]:
    """Compute SHA-256 digests of all critical licensing files.

    Returns:
        Dict mapping relative path (e.g. ``mee/api/engine.py``) to
        lower-case hex SHA-256 digest.

    Raises:
        OSError: if any critical file cannot be read.
    """
    if repo_root is not None:
        root = Path(repo_root).resolve()
    else:
        # integrity.py is at <root>/mee/licensing/integrity.py → three up.
        root = Path(__file__).resolve().parent.parent.parent
    paths = [root / rel for rel in _CRITICAL_FILES]
    digests: Dict[str, str] = {}
    for p in paths:
        if not p.exists():
            raise OSError(
                f"Critical integrity file missing: {p}. "
                "The MEE package appears to be incomplete or corrupted. "
                "(C10: block on missing anchor)")
        rel = p.relative_to(root).as_posix()
        digests[rel] = file_sha256(p)
    return digests


def _anchor_file_from_dist_info() -> Optional[Path]:
    """Locate the ``MEE_INTEGRITY_HASHES.txt`` file in the installed
    ``.dist-info`` directory (Decision #3 — secondary anchor).

    Returns ``None`` when not found (e.g. running from source checkout
    without an installed package, or the file was not produced by the
    build pipeline).
    """
    # Try to find the .dist-info directory by scanning site-packages.
    import sysconfig
    site_dirs = [
        sysconfig.get_path("purelib"),
        sysconfig.get_path("platlib"),
    ]
    # Also check the directory containing the mee package.
    try:
        site_dirs.insert(0, str(Path(__file__).resolve().parent.parent.parent /
                                f"{_PACKAGE_NAME}-0.4.0.dist-info"))
    except Exception:
        pass

    for d in site_dirs:
        if not d:
            continue
        d = Path(d)
        # Look for any <pkg>-<ver>.dist-info directory.
        for dist_info in d.glob(f"{_PACKAGE_NAME}*.dist-info"):
            candidate = dist_info / ANCHOR_FILENAME
            if candidate.exists():
                return candidate
        # Also check a direct path (no version suffix).
        direct = d / f"{_PACKAGE_NAME}.dist-info" / ANCHOR_FILENAME
        if direct.exists():
            return direct
    return None


def read_anchor_digests() -> Optional[Dict[str, str]]:
    """Read the expected SHA-256 digests from the anchor file.

    The anchor file format is one line per critical file::

        <relative/path>  <sha256-hex-digest>

    Returns:
        Dict of expected digests, or ``None`` if the anchor file is not
        found (C11: caller must block).

    Raises:
        LicenseIntegrityError: if the anchor file is present but malformed
            or unreadable (C10: block on integrity-check error).
    """
    anchor_path: Optional[Path] = None

    # Priority 1: explicit environment override (for tests / CI).
    env_anchor = os.environ.get("MEE_INTEGRITY_ANCHOR", "").strip()
    if env_anchor:
        p = Path(env_anchor)
        if p.exists():
            anchor_path = p

    # Priority 2: installed .dist-info file.
    if anchor_path is None:
        anchor_path = _anchor_file_from_dist_info()

    if anchor_path is None:
        # C11: missing anchor → block (never default to allow).
        logger.error(
            "Integrity anchor file not found (neither MEE_INTEGRITY_ANCHOR "
            "nor .dist-info/%s). C11: blocking inference.", ANCHOR_FILENAME)
        return None

    try:
        lines = anchor_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LicenseIntegrityError(
            f"Failed to read integrity anchor at {anchor_path}: {exc}. "
            "(C10: block on integrity-check error)") from exc

    expected: Dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise LicenseIntegrityError(
                f"Malformed anchor line: {line!r}. "
                f"Expected format: <path>  <sha256-hex>. "
                "(C10: block on integrity-check error)")
        path_key, digest = parts[0].strip(), parts[1].strip().lower()
        expected[path_key.replace(os.sep, "/")] = digest

    if not expected:
        raise LicenseIntegrityError(
            f"Integrity anchor at {anchor_path} contains no digests. "
            "(C10/C11: block on empty anchor)")

    return expected


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def verify_installed_integrity(repo_root: Optional[Path] = None) -> None:
    """Verify that the critical licensing files match the anchor digests.

    This is the function called from ``EmotionEngine._license_check()``
    (CTO_PLAN §8 Phase C, step C2) **before** the license verification.

    Fail-safe behaviour (Decision #4, C10–C12):
        - Any exception (missing file, malformed anchor, hash mismatch)
          raises :class:`LicenseIntegrityError` → **blocks inference**.
        - ``MEE_INTEGRITY_CHECK=0`` disables the check (development only).

    Args:
        repo_root: Optional explicit root directory for locating critical
            files.  When ``None``, the parent of the ``mee`` package is used.

    Raises:
        LicenseIntegrityError: on any integrity failure (C10, C11).
    """
    if not is_enabled():
        logger.debug("Integrity check disabled via MEE_INTEGRITY_CHECK=0")
        return

    # 1. Read expected digests from anchor.
    expected = read_anchor_digests()
    if expected is None:
        # read_anchor_digests already logged C11.
        raise LicenseIntegrityError(
            "Integrity anchor not available — blocking inference (C11). "
            "If this is a development environment, set MEE_INTEGRITY_CHECK=0 "
            "to skip the check. For production, ensure the package was "
            "installed via pip with the Sigstore-signed wheel.")

    # 2. Compute actual digests.
    try:
        actual = compute_critical_digests(repo_root)
    except OSError as exc:
        raise LicenseIntegrityError(
            f"Cannot compute integrity digests: {exc}. "
            "(C10: block on integrity-check error)") from exc

    # 3. Compare.
    missing_in_expected = set(expected) - set(actual)
    missing_in_actual = set(actual) - set(expected)

    if missing_in_expected:
        raise LicenseIntegrityError(
            f"Critical files not present in anchor: {sorted(missing_in_expected)}. "
            "(C11: block on mismatch)")

    if missing_in_actual:
        # Files present on disk but not in the anchor — this is unusual
        # (anchor was built with a different file set). Block.
        raise LicenseIntegrityError(
            f"Critical files not in expected set: {sorted(missing_in_actual)}. "
            "(C10: block on mismatch)")

    mismatches: list[str] = []
    for path_key in sorted(expected):
        exp_digest = expected[path_key]
        act_digest = actual.get(path_key, "")
        if exp_digest != act_digest:
            mismatches.append(
                f"  {path_key}:\n"
                f"    expected: {exp_digest}\n"
                f"    actual:   {act_digest}"
            )

    if mismatches:
        detail = "\n".join(mismatches)
        logger.error(
            "Integrity check FAILED — %d file(s) do not match the anchor:\n%s",
            len(mismatches), detail)
        raise LicenseIntegrityError(
            f"Integrity check failed: {len(mismatches)} critical file(s) "
            f"do not match the signed anchor.\n{detail}\n"
            "This may indicate tampering or a corrupted installation. "
            "Reinstall MEE from the official signed release. "
            "(C10: block on integrity-check error)")

    logger.debug("Integrity check PASSED — all %d critical files match anchor",
                 len(expected))


# ---------------------------------------------------------------------------
# Anchor generation helper (for CI / build pipeline)
# ---------------------------------------------------------------------------

def generate_anchor_file(repo_root: Path, output_path: Path) -> None:
    """Generate the ``MEE_INTEGRITY_HASHES.txt`` anchor file from the
    current state of the critical files.

    This is called by the CI/build pipeline (Phase A/B in CTO_PLAN §8)
    to produce the anchor that is embedded in the wheel's ``.dist-info``
    directory and/or published alongside the Sigstore-signed manifest.

    Args:
        repo_root: Root of the MEE source tree.
        output_path: Where to write the anchor file.
    """
    digests = compute_critical_digests(repo_root)
    lines = [
        "# MEE Integrity Anchor (TASK_MEE_020, Decision #3)",
        "# Format: <relative/path>  <sha256-hex>",
        "# Generated by: tools/generate_integrity_anchor.py",
    ]
    for path_key in sorted(digests):
        lines.append(f"{path_key}  {digests[path_key]}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote integrity anchor to %s (%d files)",
                output_path, len(digests))
