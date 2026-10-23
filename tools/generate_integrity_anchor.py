#!/usr/bin/env python3
"""Generate the MEE integrity anchor file (TASK_MEE_020, Decision #3).

Phase B (CTO_PLAN §8): the build pipeline invokes this to produce
``MEE_INTEGRITY_HASHES.txt`` (SHA-256 digests of the critical licensing
files) from the current source tree. The file is then:

- embedded in the wheel's ``<package>.dist-info/`` directory (secondary
  anchor — offline verification path, Decision #3), and/or
- the digest of its contents is published alongside the Sigstore-signed
  release manifest (primary anchor — external to the wheel, C9-compliant).

Usage::

    # From the repo root (default), write to the default location:
    python tools/generate_integrity_anchor.py

    # Explicit root + output path:
    python tools/generate_integrity_anchor.py --root /path/to/mee \
        --out /path/to/dist-info/MEE_INTEGRITY_HASHES.txt

The output is deterministic (sorted file order) so the same source tree
always yields the same anchor — required for reproducible builds.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly from a source checkout (repo on sys.path).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mee.licensing.integrity import (  # noqa: E402  (post sys.path tweak)
    ANCHOR_FILENAME,
    generate_anchor_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the MEE integrity anchor file "
                    f"({ANCHOR_FILENAME}).")
    parser.add_argument(
        "--root", type=Path, default=_REPO_ROOT,
        help="Root of the MEE source tree (default: repo root).")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output path for the anchor file (default: <root>/"
             "MEE_INTEGRITY_HASHES.txt).")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    out = (Path(args.out) if args.out else root / ANCHOR_FILENAME).resolve()

    if not (root / "mee" / "licensing").is_dir():
        print(f"error: {root!s} does not look like a MEE source tree "
              "(missing mee/licensing/)", file=sys.stderr)
        return 2

    generate_anchor_file(root, out)
    print(f"wrote {out}")
    print(out.read_text(encoding="utf-8").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
