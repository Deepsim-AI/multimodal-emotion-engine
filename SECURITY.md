# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✅ Yes    |
| 0.3.x and earlier | ❌ No |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Email: **security@deepsim.com**

We aim to acknowledge receipt of valid reports within **2 business days** and
provide a fix timeline where possible.

### What to include

- Description of the vulnerability and its potential impact
- Steps to reproduce (or a proof-of-concept)
- Affected version(s)
- Any relevant configuration or environment details

### What is in scope

- `mee/` package code (licensing, API, vision/voice pipelines)
- `tools/` scripts (integrity anchor generation, release verification)
- `.github/workflows/` (CI/CD supply chain)

### What is out of scope

- Third-party model weights (retina-face, EmotiEffLib, SpeechBrain) — report to their respective projects
- Keygate license server (`licenses.deepsim.ai`) — report to security@deepsim.com separately
- Social engineering, phishing, or physical security

## Response Timeline

| Step | Target |
|------|--------|
| Acknowledgment | 2 business days |
| Triage + severity assessment | 5 business days |
| Fix developed + tested | Depends on severity (7–30 days) |
| Public disclosure | After fix is released (or with your consent earlier) |

## Security Features

MEE includes the following security mechanisms:

- **Bytecode integrity self-check** (`mee/licensing/integrity.py`): SHA-256
  digests over critical licensing files, verified against a signed release
  anchor. Tampered code → `LicenseIntegrityError` (inference blocked).
- **Sigstore keyless signing** (CI/CD): all release artifacts are signed via
  Fulcio OIDC. Customers can verify provenance with `tools/verify_release.sh`.
- **No telemetry**: MEE makes no outbound network calls except to the
  Keygate license server (for license verification) and model download URLs
  (only during explicit `tools/download_models.py` invocation). See
  `docs/licensing/privacy.md`.
- **Offline grace window**: the license client supports a bounded offline
  period after last successful verification. No silent perpetual use.

## Key Rotation

License keys are managed via the Keygate server. If you believe a key has
been compromised, contact security@deepsim.com and the key will be revoked
server-side.
