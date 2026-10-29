#!/usr/bin/env bash
#
# publish_to_hub.sh — Publish a Python wheel + sdist to the Deepsim Hub pypi registry,
# under the **Deepsim org** namespace (the single canonical location for Hub packages).
#
# Why this script exists:
#   The Hub pypi registry owner is decided by the upload URL's namespace. If a publish is
#   done against a *user* namespace (e.g. `deepsim-admin`), the package lands under that
#   user and is NOT discoverable under the `Deepsim` org — which is the canonical, stable,
#   brand-consistent location customers should install from. This script hardcodes the org
#   namespace so every current and future product lands in the same place automatically.
#
# Usage:
#   tools/publish_to_hub.sh <wheel.whl> <sdist.tar.gz> [options]
#
# Required env (or --username/--password flags):
#   HUB_USERNAME      Forgejo user that is a MEMBER of the Deepsim org (default: deepsim-admin)
#   HUB_PASSWORD      That user's Forgejo password
#
# Options:
#   --org <name>          Deepsim org name (default: Deepsim)
#   --forgejo <url>       Forgejo base URL (default: https://forge.deepsim.ai:8443)
#   --hub <url>           Hub base URL used for the install self-check (default: https://hub.deepsim.ai:8443)
#   --username <name>     Override HUB_USERNAME
#   --password <pass>     Override HUB_PASSWORD
#   --package <name>      Package name for the self-check (default: read from the wheel's METADATA)
#   --skip-check          Skip the `pip install` self-check (faster, but less safe)
#   --dry-run             Show the twine command without uploading
#   -h | --help           Show this help
#
# Environment overrides (take precedence over flags for the URLs):
#   HUB_FORGEJO_URL, HUB_BASE_URL, HUB_ORG
#
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────
ORG="Deepsim"
FORGEJO_URL="https://forge.deepsim.ai:8443"
HUB_URL="https://hub.deepsim.ai:8443"
USERNAME="${HUB_USERNAME:-deepsim-admin}"
PASSWORD="${HUB_PASSWORD:-}"
PACKAGE=""
SKIP_CHECK=0
DRY_RUN=0
FILES=()

# ── Arg parsing ───────────────────────────────────────────────────────────
usage() { sed -n '2,40p' "$0"; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --org)        ORG="$2"; shift 2 ;;
    --forgejo)    FORGEJO_URL="$2"; shift 2 ;;
    --hub)        HUB_URL="$2"; shift 2 ;;
    --username)   USERNAME="$2"; shift 2 ;;
    --password)   PASSWORD="$2"; shift 2 ;;
    --package)    PACKAGE="$2"; shift 2 ;;
    --skip-check) SKIP_CHECK=1; shift ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)    usage ;;
    -*)           echo "ERROR: unknown option: $1" >&2; exit 2 ;;
    *)            FILES+=("$1"); shift ;;
  esac
done

# Env precedence for URLs (so CI can override without flags)
[ -n "${HUB_ORG:-}" ]        && ORG="$HUB_ORG"
[ -n "${HUB_FORGEJO_URL:-}" ]&& FORGEJO_URL="$HUB_FORGEJO_URL"
[ -n "${HUB_BASE_URL:-}" ]   && HUB_URL="$HUB_BASE_URL"

# ── Validation ────────────────────────────────────────────────────────────
if [ "${#FILES[@]}" -lt 1 ]; then
  echo "ERROR: provide at least one artifact (wheel and/or sdist)." >&2
  echo "Usage: $0 <wheel.whl> <sdist.tar.gz> [options]" >&2
  exit 2
fi

for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "ERROR: artifact not found: $f" >&2; exit 2; }
done

# Determine package name for the self-check (explicit > wheel METADATA)
if [ -z "$PACKAGE" ]; then
  WHEEL=""
  for f in "${FILES[@]}"; do case "$f" in *.whl) WHEEL="$f";; esac; done
  if [ -n "$WHEEL" ] && command -v python3 >/dev/null 2>&1; then
    PACKAGE=$(python3 - "$WHEEL" <<'PY' 2>/dev/null || echo ""
import sys, zipfile
w = sys.argv[1]
z = zipfile.ZipFile(w)
dist = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
for line in z.read(dist).decode().splitlines():
    if line.startswith("Name: "):
        print(line[6:].strip()); break
PY
)
  fi
fi

if [ -z "$PASSWORD" ] && [ "$DRY_RUN" -eq 0 ]; then
  echo "ERROR: no password. Set HUB_PASSWORD (or use --password) or --dry-run." >&2
  exit 2
fi

# ── Build the twine command ───────────────────────────────────────────────
REPO_URL="${FORGEJO_URL%/}/api/packages/${ORG}/pypi"
echo "==> Publishing to Deepsim Hub pypi registry"
echo "    org:           ${ORG}"
echo "    registry URL:  ${REPO_URL}"
echo "    user:          ${USERNAME}"
echo "    artifacts:     ${FILES[*]}"
[ -n "$PACKAGE" ] && echo "    package:       ${PACKAGE}"
echo ""

TWINE_ARGS=(upload --verbose
  --repository-url "$REPO_URL"
  --username "$USERNAME"
  --password "${PASSWORD:-<set-at-runtime>}"
  "${FILES[@]}")

if [ "$DRY_RUN" -eq 1 ]; then
  echo "==> DRY RUN — would run:"
  echo "    twine ${TWINE_ARGS[*]}"
  echo "    (self-check index: ${HUB_URL%/}/api/packages/${ORG}/pypi/simple/)"
  exit 0
fi

# ── Upload ────────────────────────────────────────────────────────────────
command -v twine >/dev/null 2>&1 || { echo "ERROR: twine not found. pip install twine" >&2; exit 3; }

# Pass the password via the flag (twine) so we don't rely on a stored .pypirc entry.
twine "${TWINE_ARGS[@]}"

echo ""
echo "==> Upload complete."

# ── Self-check: verify the package is installable from the org namespace ─
if [ "$SKIP_CHECK" -eq 0 ] && [ -n "$PACKAGE" ]; then
  echo "==> Self-check: pip install from the Deepsim org namespace..."
  INDEX="${HUB_URL%/}/api/packages/${ORG}/pypi/simple/"
  if pip install --dry-run --index-url "$INDEX" "$PACKAGE" 2>&1 | grep -qiE "Would install|ERROR"; then
    pip install --dry-run --index-url "$INDEX" "$PACKAGE" 2>&1 | grep -iE "Would install|ERROR|satisfies" | sed 's/^/    /'
  else
    echo "    ERROR: package '$PACKAGE' not resolvable at $INDEX" >&2
    echo "    The upload may have landed under a different namespace. Check the registry." >&2
    exit 4
  fi
  echo "==> Self-check PASSED: '$PACKAGE' is installable from the Deepsim org."
else
  echo "==> Self-check skipped."
fi
