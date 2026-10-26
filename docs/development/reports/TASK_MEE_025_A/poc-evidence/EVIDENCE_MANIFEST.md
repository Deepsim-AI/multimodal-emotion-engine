# POC Evidence Manifest

**Task:** TASK_MEE_025_A
**Date:** 2026-10-26
**Isolation:** All artifacts generated in /tmp/mee-signing-poc/ (not committed to production repo)

## Files

| File | Purpose | Sensitive? |
|------|---------|------------|
| `TEST_RESULTS.md` | Complete test results and comparison analysis | No |
| `KEY_PROTECTION.md` | Key storage, rotation, recovery procedures | No |
| `cosign-public.pem` | ECDSA P-256 public key (distributable) | No (public) |
| `multimodal_emotion_engine-0.4.0-py3-none-any.whl.sig` | ECDSA signature (70 bytes, DER) | No |
| `multimodal_emotion_engine-0.4.0-py3-none-any.whl.sigstore.json` | Sigstore bundle format | No |
| `fulcio-test-ca-cert.pem` | Self-signed Fulcio CA cert (POC only) | No (self-signed test) |
| `fulcio-server.log` | Fulcio server startup log (evidence of service) | No |
| `rekor-server.log` | Rekor server startup log (evidence of attempt) | No |

## NOT Included (intentionally excluded)

| Item | Reason |
|------|--------|
| `cosign-private.pem` | **PRIVATE KEY** — must never be committed to any repository |
| `cosign-bin` (127MB) | Binary — not needed for evidence |
| `fulcio-bin` (47MB) | Binary — not needed for evidence |
| `rekor-server` (94MB) | Binary — not needed for evidence |
| `rekor-cli` (49MB) | Binary — not needed for evidence |
| `fulcio-data/ca.key` | **CA PRIVATE KEY** — must never be committed |

## Verification Commands (for reviewer)

```bash
# Verify signature against public key (requires the test wheel)
# Note: test wheel is in /tmp/mee-signing-poc/test-artifacts/ (not in this directory)
# To reproduce:
cp /home/deepsim/multimodal-emotion-engine/dist/multimodal_emotion_engine-0.4.0-py3-none-any.whl /tmp/test-wheel.whl
openssl dgst -sha256 -verify cosign-public.pem -signature multimodal_emotion_engine-0.4.0-py3-none-any.whl.sig /tmp/test-wheel.whl
# Expected: "Verified OK"

# Tamper test:
cp /tmp/test-wheel.whl /tmp/test-tampered.whl
printf 'X' | dd of=/tmp/test-tampered.whl bs=1 seek=100 count=1 conv=notrunc 2>/dev/null
openssl dgst -sha256 -verify cosign-public.pem -signature multimodal_emotion_engine-0.4.0-py3-none-any.whl.sig /tmp/test-tampered.whl
# Expected: "Verification failure" (exit code 1)
```
