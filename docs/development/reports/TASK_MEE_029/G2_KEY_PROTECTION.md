# TASK_MEE_029 — Option B (Cosign Key-Based) Key Protection, Rotation & Recovery

**Task ID:** TASK_MEE_029
**Gate:** G2 — Implementer (Option B key-protection procedures, AC #7)
**Date:** 2026-10-26 (PDT)
**Supersedes:** the MEE_025_A `KEY_PROTECTION.md` (which was written for the then-current plan);
this document reflects the **Option B as deployed** in `.github/workflows/release-sigstore.yml`.

---

## 1. Key Inventory

| Item | Value | Location |
|------|-------|----------|
| Algorithm | ECDSA P-256 (prime256v1), SHA-256 | — |
| Public key (distributable) | `cosign-public.pem` | Repo root (committed) + release assets |
| Public key fingerprint | `sha256 a1d2cdf68302839b6643331c2170c3a7c2cefb6b0985d3532aa5f4edf1f0bfbf` | — |
| Private key (SECRET) | EC P-256 (227 bytes, SEC1 `# EC PRIVATE KEY`) | Forgejo secret `COSIGN_PRIVATE_KEY` — **never committed** |
| Generated | 2026-10-26 (PDT) | This task |

**Security posture:** Option B has **no long-lived key exposure in the repo or CI runner at rest**.
The private key exists only as an encrypted Forgejo secret, materialized to a `0600` temp file inside
the signing step, and deleted via `trap … EXIT` at the end of that step. There is no persistent
on-disk private key in CI.

---

## 2. Key Generation Procedure (reproducible)

```bash
# ECDSA P-256 key pair (SEC1 EC format — the format the CI signing step expects)
openssl ecparam -name prime256v1 -genkey -noout -out cosign-private.pem
openssl ec -in cosign-private.pem -pubout -out cosign-public.pem

# Verify the pair matches
openssl ec -in cosign-private.pem -pubout | diff - cosign-public.pem   # (no output = match)
```

> **Note on the POC:** MEE_025_A's POC used the identical `openssl dgst -sha256 -sign/-verify`
> method (its "Cosign" path was openssl ECDSA, not the OCI `cosign` CLI). This task reuses that
> proven, dependency-free method — no Rekor, no registry, fully offline verification.

---

## 3. Storing the Private Key as a Forgejo Secret

**Do NOT commit `cosign-private.pem`.** Store it as the repository/organization secret
`COSIGN_PRIVATE_KEY`.

- **Forgejo UI:** Repository → Settings → Secrets → Add → Name `COSIGN_PRIVATE_KEY` → Value `<paste the full PEM>`.
- **Or Forgejo API (admin token):**
  ```bash
  curl -X PUT https://forge.deepsim.ai:8443/api/v1/repos/deepsim/multimodal-emotion-engine/secrets/COSIGN_PRIVATE_KEY \
    -H "Authorization: token <ADMIN_TOKEN>" \
    -d @cosign-private.pem
  ```

The workflow reads it via `${{ secrets.COSIGN_PRIVATE_KEY }}` (referenced as the `COSIGN_PRIVATE_KEY`
env in the signing step). If the secret is absent, the step **fails fast** with a clear error
(the pipeline never silently skips signing).

---

## 4. Customer Verification Path (Option B)

1. Download the artifact (e.g. `multimodal_emotion_engine-0.5.0-py3-none-any.whl`) and its
   `.sig` file from the release assets.
2. Download `cosign-public.pem` (attached to the release, or from the repo root).
3. Run:
   ```bash
   ./tools/verify_cosign.sh <artifact>.whl cosign-public.pem
   ```
   or, without the helper:
   ```bash
   openssl dgst -sha256 -verify cosign-public.pem -signature <artifact>.whl.sig <artifact>.whl
   ```
   Expected: `Verified OK`.

**Trust model:** the customer trusts Deepsim's public key (distributed via CHANGELOG + release assets).
This is a **parallel** trust path to the existing keyless Sigstore (Fulcio) verification, which
continues to work unchanged.

---

## 5. Key Rotation (recommended every 12 months, or on compromise)

1. **Generate** a new key pair (Section 2).
2. **Deploy** the new private key to the `COSIGN_PRIVATE_KEY` secret (replaces the old).
3. **Distribute** the new `cosign-public.pem`:
   - Commit it to the repo root (replaces the old) and attach to the next release.
   - Add a CHANGELOG entry: *"Security: signing key rotation (YYYY-MM). Customers should verify
     new releases against the new public key. Old signatures remain valid with the old key."*
4. **Archive** the old private key (do **not** delete — old signatures must remain verifiable).
   Keep the old `cosign-public.pem` available for at least the migration window.
5. **Verify** the next release signs + verifies with the new key.

> **Transition note:** during rotation, releases signed before the rotation verify with the old key;
> releases after verify with the new key. Customers keep both public keys until the migration window
> closes.

---

## 6. Key Compromise Recovery

**Immediate (0–2 h):**
1. Revoke: delete the `COSIGN_PRIVATE_KEY` secret (UI or `DELETE …/secrets/COSIGN_PRIVATE_KEY`).
2. Notify: Security@deepsim.ai, gateway owner, all repo admins.
3. Assess: which artifacts were signed with the compromised key; last-used timestamp; any evidence
   of unauthorized signing.

**Recovery (2–24 h):**
1. Generate a **new** key pair (fresh, unrelated to the compromised key).
2. Deploy the new key to `COSIGN_PRIVATE_KEY`; commit the new `cosign-public.pem`.
3. Sign the next release; publish a security advisory listing affected artifacts.
4. Customers re-download affected artifacts and verify against the new public key.

**Customer advisory (24–48 h):**
```
## SECURITY ADVISORY: MEE Signing Key Compromise (YYYY-MM-DD)
Severity: HIGH
Deepsim's MEE signing key was compromised on <DATE>. Artifacts signed between <A> and <B>
should be considered untrusted.
Customer action: re-download affected artifacts and verify with the NEW public key
(cosign-public.pem, published <DATE>). Old signatures are NO LONGER trusted for new verification.
```

---

## 7. Fork / Supply-Chain Safety Analysis

| Aspect | Option B (Cosign key-based) |
|--------|------------------------------|
| Key to steal | EC P-256 private key (Forgejo secret, encrypted at rest) |
| Attack path | Attacker gains repo admin → reads secret → signs malicious artifact |
| Mitigation | Secret encryption at rest; least-privilege repo admin; key rotation; customer pins public key |
| Fork scenario | Attacker **cannot** sign validly without the private key (unlike a stolen CI env) |
| Residual risk | **MEDIUM** (single long-lived key; mitigated by rotation + secret access control) |
| Transparency log | Optional (Rekor) — **not required** by this path; the key-based signature is self-contained |

**Why not Option A (Fulcio keyless)?** Option A removes the long-lived key (stronger fork safety)
but requires a Rekor transparency log, which in turn requires a Trillian server (no publicly pullable
image) or the unreleased Rekor-v2/Tessera backend. Not deployable in this environment as of 2026-10-26.
Option B is the shippable, proven choice; Option A can be revisited when a Rekor/Trillian image is
available.

---

## 8. Audit Trail

Signing events to retain (permanent):
- Key generation (date, operator, key id)
- Key storage (date, secret name)
- Artifact signing (date, artifact digest, key id)
- Key rotation (date, old/new key id)
- Key compromise (incident id, affected artifacts)

Suggested JSON-lines:
```json
{"ts":"2026-10-26T22:00:00Z","event":"key_generated","operator":"shouke.wei","alg":"ecdsa-p256"}
{"ts":"2026-10-26T22:05:00Z","event":"key_stored","secret":"COSIGN_PRIVATE_KEY"}
{"ts":"2026-10-26T22:10:00Z","event":"artifact_signed","operator":"ci-runner","artifact":"...whl","sha256":"...","key_id":"mee-2026-10"}
```

---

## 9. Compliance Checklist

| Requirement | Status |
|-------------|--------|
| Private key never committed to repo | ✅ (secret only) |
| Private key materialized to 0600 temp, deleted after step | ✅ (workflow `trap … EXIT`) |
| Public key distributed to customers | ✅ (repo root + release assets + CHANGELOG) |
| Rotation procedure documented | ✅ (Section 5) |
| Compromise recovery documented | ✅ (Section 6) |
| Parallel to existing Sigstore path (no breakage) | ✅ (additive step) |
| Customer offline verification (`openssl`) | ✅ (`tools/verify_cosign.sh`) |

---

*End of TASK_MEE_029 Option B key-protection procedures.*
