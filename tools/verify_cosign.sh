#!/usr/bin/env bash
# verify_cosign.sh — customer-facing key-based (Option B) verification (TASK_MEE_029).
#
# This is the Cosign key-based signing path chosen by the owner 2026-10-26
# (Option B, proven in MEE_025_A POC). It runs PARALLEL to the keyless Sigstore
# (Fulcio) path — both coexist during migration; no customer breakage.
#
# Method (proven in POC): ECDSA P-256 + SHA-256 via `openssl dgst`. No Rekor,
# no registry, no network calls — fully offline verification.
#
# Usage:
#   ./tools/verify_cosign.sh <artifact> [public-key.pem]
#
#   <artifact>       Path to the signed artifact (.whl, .tar.gz, .json, .txt).
#   [public-key.pem] Path to cosign-public.pem (default: cosign-public.pem in CWD
#                    or repo root). Customers get this from the release assets
#                    or the repository root.
#
# The signature file is expected at <artifact>.sig (e.g. wheel.whl -> wheel.whl.sig).
#
# Exit codes:
#   0  PASS  — signature verifies against the public key
#   1  FAIL  — signature invalid (tamper or wrong key)
#   2  ERROR — missing input, no signature file, or no openssl
#
# Requirements (customer-side): only `openssl` (universal). No network, no sigstore CLI.

set -euo pipefail

ARTIFACT="${1:-}"
if [[ -z "$ARTIFACT" ]]; then
  echo "usage: $0 <artifact> [public-key.pem]" >&2
  exit 2
fi
if [[ ! -f "$ARTIFACT" ]]; then
  echo "ERROR: artifact not found: $ARTIFACT" >&2
  exit 2
fi

SIGFILE="${ARTIFACT}.sig"
PUBKEY="${2:-cosign-public.pem}"
# Fallback: repo root (when run from within the MEE checkout).
if [[ ! -f "$PUBKEY" && -f "cosign-public.pem" ]]; then
  PUBKEY="cosign-public.pem"
fi

if [[ ! -f "$SIGFILE" ]]; then
  echo "ERROR: signature file not found: $SIGFILE" >&2
  echo "       Download it from the release assets (.sig next to the artifact)." >&2
  exit 2
fi
if [[ ! -f "$PUBKEY" ]]; then
  echo "ERROR: public key not found: $PUBKEY" >&2
  echo "       Download it from the release assets (cosign-public.pem) or repo root." >&2
  exit 2
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl not found (required for verification)." >&2
  exit 2
fi

echo "=== MEE Option B (Cosign key-based) verification ==="
echo "  artifact:   ${ARTIFACT}"
echo "  signature:  ${SIGFILE}"
echo "  public key: ${PUBKEY}"
echo "  sha256:     $(sha256sum "$ARTIFACT" | awk '{print $1}')"
echo ""

if openssl dgst -sha256 -verify "$PUBKEY" -signature "$SIGFILE" "$ARTIFACT" 2>/dev/null; then
  echo ""
  echo "RESULT: PASS — artifact signature verified against Deepsim's public key."
  exit 0
else
  echo ""
  echo "RESULT: FAIL — signature verification FAILED." >&2
  echo "        The artifact may have been tampered with, or the signature was" >&2
  echo "        produced by a different key than $PUBKEY." >&2
  exit 1
fi
