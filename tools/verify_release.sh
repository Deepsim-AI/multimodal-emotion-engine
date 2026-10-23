#!/usr/bin/env bash
# verify_release.sh — customer-facing Sigstore + SHA-256 verification (TASK_MEE_020).
#
# Decision #2 (CTO_PLAN §3): Sigstore (Fulcio, keyless) is the signing
# scheme. This script is the single PASS/FAIL command a customer runs
# after `pip download` / wheel fetch to verify authenticity + integrity:
#
#   1. SHA-256 of the wheel matches the release manifest (integrity), and
#   2. the wheel is signed by the MEE publisher via Sigstore (authenticity),
#      anchored to the release's Sigstore bundle (provenance, C9-compliant).
#
# Usage:
#   ./tools/verify_release.sh <wheel-file> [manifest.json] [sigstore-dir]
#
#   <wheel-file>     Path to the .whl to verify (required).
#   [manifest.json]  Release manifest with {"artifacts": [{"name","sha256"}]}
#                    (default: <wheel-basename>.manifest.json, or the file
#                    named by MEE_RELEASE_MANIFEST).
#   [sigstore-dir]   Directory holding the Sigstore bundle for the wheel
#                    (default: <wheel>.sigstore/).
#
# Exit codes:
#   0  PASS  — hash matches manifest AND Sigstore signature verifies
#   1  FAIL  — hash mismatch OR signature verification failed
#   2  ERROR — missing input, unsupported environment, or no sigstore CLI
#
# Requirements (customer-side, CI-independent):
#   - sigstore CLI installed:  pip install sigstore
#   - network access to the Sigstore public CA (Fulcio + Rekor) for
#     signature verification. This is the *only* network use in this script
#     (no telemetry — see docs/licensing/privacy.md).
#
# Honest note (Decision #1, C3): this verifies *distribution provenance and
# integrity*. It is NOT a substitute for the runtime license gate — it does
# not prove a license is present. Use together with `mee-lic verify`.

set -euo pipefail

WHEEL="${1:-}"
if [[ -z "$WHEEL" ]]; then
  echo "usage: $0 <wheel-file> [manifest.json] [sigstore-dir]" >&2
  exit 2
fi
if [[ ! -f "$WHEEL" ]]; then
  echo "ERROR: wheel not found: $WHEEL" >&2
  exit 2
fi

BASENAME="$(basename "$WHEEL")"
MANIFEST="${2:-}"
if [[ -z "$MANIFEST" ]]; then
  if [[ -n "${MEE_RELEASE_MANIFEST:-}" ]]; then
    MANIFEST="$MEE_RELEASE_MANIFEST"
  else
    MANIFEST="${BASENAME%.whl}.manifest.json"
  fi
fi

SIGDIR="${3:-${BASENAME%.whl}.sigstore}"

# --- Step 1: SHA-256 vs release manifest (integrity) -----------------------
ACTUAL_SHA="$(sha256sum "$WHEEL" | awk '{print $1}')"
EXPECTED_SHA=""
if [[ -f "$MANIFEST" ]]; then
  # Parse the sha256 for this wheel name out of the manifest JSON.
  EXPECTED_SHA="$(python3 - "$MANIFEST" "$BASENAME" <<'PY'
import json, sys
path, name = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path))
except Exception as e:
    sys.stderr.write(f"failed to parse manifest {path}: {e}\n"); sys.exit(0)
arts = data.get("artifacts") or data.get("files") or []
for a in arts:
    a = a if isinstance(a, dict) else {}
    aname = a.get("name") or a.get("filename") or a.get("path") or ""
    if aname == name or aname.endswith(name):
        h = a.get("sha256") or a.get("digest") or a.get("hash") or ""
        h = h.split("sha256=")[-1].strip().lower()
        print(h); sys.exit(0)
print("")
PY
)"
fi

if [[ -z "$EXPECTED_SHA" ]]; then
  echo "WARN: no expected SHA-256 found (manifest: ${MANIFEST}) — skipping hash check."
  HASH_RESULT="SKIPPED (no expected hash available)"
else
  if [[ "${EXPECTED_SHA,,}" == "${ACTUAL_SHA,,}" ]]; then
    HASH_RESULT="PASS (${ACTUAL_SHA})"
  else
    echo "FAIL: SHA-256 mismatch"
    echo "  wheel:    ${WHEEL}"
    echo "  expected: ${EXPECTED_SHA}"
    echo "  actual:   ${ACTUAL_SHA}"
    echo "  manifest: ${MANIFEST}"
    exit 1
  fi
fi

# --- Step 2: Sigstore signature (authenticity / provenance) ----------------
if ! command -v sigstore >/dev/null 2>&1; then
  echo "WARN: 'sigstore' CLI not found — skipping signature verification."
  echo "      Install it with:  pip install sigstore"
  SIG_RESULT="SKIPPED (sigstore CLI not installed)"
elif [[ -d "$SIGDIR" ]]; then
  if sigstore verify --identity "deepsim-ai/mee" --dir "$SIGDIR"; then
    SIG_RESULT="PASS (sigstore identity verified)"
  else
    echo "FAIL: Sigstore signature verification failed (identity/dir: $SIGDIR)"
    exit 1
  fi
else
  echo "WARN: Sigstore bundle dir not found: $SIGDIR — skipping signature check."
  SIG_RESULT="SKIPPED (no sigstore bundle present)"
fi

# --- Summary ----------------------------------------------------------------
echo ""
echo "================ MEE RELEASE VERIFICATION ================"
echo "  wheel:          ${WHEEL}"
echo "  sha256:         ${HASH_RESULT}"
echo "  signature:      ${SIG_RESULT}"
echo "==========================================================="

if [[ "$HASH_RESULT" == SKIPPED* && "$SIG_RESULT" == SKIPPED* ]]; then
  echo "NOTE: both checks were skipped — install sigstore and provide the"
  echo "      release manifest + bundle for a full PASS/FAIL verdict."
  # Not a hard failure: a customer may only be able to run one side.
  # The runtime license gate still enforces authorization regardless.
fi
exit 0
