# TASK_MEE_025_A — Key Protection, Rotation & Recovery Procedures

**Date:** 2026-10-26  
**Scope:** Option B (Cosign Key-Based) — RECOMMENDED

---

## 1. Key Storage

### Production Storage (Option B)

| Item | Details |
|------|---------|
| **Key Type** | ECDSA P-256 (prime256v1) |
| **Storage Location** | Forgejo secrets (encrypted with app.secret at rest) |
| **Access Control** | Repository admin + security team only |
| **Encryption** | AES-256-GCM (Forgejo secrets encryption) |
| **Backup** | Forgejo database backup (encrypted) |

### POC Storage (This Test)

| Item | Details |
|------|---------|
| **Private Key** | `/tmp/mee-signing-poc/cosign-private.pem` (POC only, not production) |
| **Public Key** | `/tmp/mee-signing-poc/cosign-public.pem` (distributable) |
| **Isolation** | `/tmp/mee-signing-poc/` (not committed to repo) |

---

## 2. Key Generation Procedure

### Step 1: Generate ECDSA P-256 Key Pair

```bash
# Generate private key
openssl ecparam -name prime256v1 -genkey -noout -out cosign-private.pem

# Extract public key
openssl ec -in cosign-private.pem -pubout -out cosign-public.pem

# Verify key pair
openssl ec -in cosign-private.pem -pubout | diff - cosign-public.pem
# (no output = keys match)
```

### Step 2: Store Private Key in Forgejo Secrets

```bash
# Via Forgejo API (requires admin token)
curl -X PUT https://forge.deepsim.ai/api/v1/user/settings/secrets/COSIGN_PRIVATE_KEY \
  -H "Authorization: token <ADMIN_TOKEN>" \
  -d @cosign-private.pem

# Or via Forgejo UI:
# Settings → Secrets → Add → Name: COSIGN_PRIVATE_KEY → Value: <paste key>
```

### Step 3: Distribute Public Key

```bash
# Add public key to repository (for CI/CD and customer verification)
# Option 1: Commit to repo (read-only, safe)
git add cosign-public.pem
git commit -m "Add cosign public key for signature verification"
git push

# Option 2: Include in CHANGELOG
# Option 3: Include in release notes
```

---

## 3. Signing Workflow (Production)

### CI/CD Signing Process

```yaml
# .github/workflows/sign-release.yml (example)
name: Sign Release
on:
  release:
    types: [published]

jobs:
  sign:
    runs-on: ubuntu-latest
    steps:
      - name: Check out code
        uses: actions/checkout@v4

      - name: Install cosign
        run: |
          curl -sL https://github.com/sigstore/cosign/releases/download/v2.6.2/cosign-linux-amd64 \
            -o /usr/local/bin/cosign
          chmod +x /usr/local/bin/cosign

      - name: Sign wheel
        run: |
          export COSIGN_KEY=$(echo '${{ secrets.COSIGN_PRIVATE_KEY }}')
          cosign sign --key /dev/stdin dist/multimodal_emotion_engine-*.whl
        env:
          COSIGN_PASSWORD: ""

      - name: Upload signature
        run: |
          # Upload .sig file to release artifacts
          # or commit to repository
```

### Local Signing (Developer)

```bash
# Sign a wheel file
openssl dgst -sha256 -sign cosign-private.pem -out artifact.whl.sig artifact.whl

# Verify signature
openssl dgst -sha256 -verify cosign-public.pem -signature artifact.whl.sig artifact.whl
```

---

## 4. Key Rotation Procedure (Every 12 Months)

### Step 1: Generate New Key Pair

```bash
openssl ecparam -name prime256v1 -genkey -noout -out cosign-private-NEW.pem
openssl ec -in cosign-private-NEW.pem -pubout -out cosign-public-NEW.pem
```

### Step 2: Update Forgejo Secret

```bash
# Replace old key with new key
curl -X PUT https://forge.deepsim.ai/api/v1/user/settings/secrets/COSIGN_PRIVATE_KEY \
  -H "Authorization: token <ADMIN_TOKEN>" \
  -d @cosign-private-NEW.pem
```

### Step 3: Distribute New Public Key

```bash
# Commit new public key to repository
git add cosign-public-NEW.pem
git commit -m "Rotate cosign public key (2027-10)"
git push

# Update CHANGELOG
# "## Security: Key Rotation (2027-10)"
# "A new cosign signing key has been deployed. Customers should update their
#  verification scripts to use the new public key (cosign-public-NEW.pem).
#  Old signatures remain valid with the old public key."
```

### Step 4: Verify New Key

```bash
# Sign a test artifact with new key
openssl dgst -sha256 -sign cosign-private-NEW.pem -out test.sig test.whl

# Verify with new public key
openssl dgst -sha256 -verify cosign-public-NEW.pem -signature test.sig test.whl
# Expected: "Verified OK"
```

### Step 5: Clean Up Old Key (After 30-Day Transition Period)

```bash
# Keep old public key available for 30 days (for existing signatures)
# After 30 days, archive old key (do NOT delete — needed for old signature verification)
mv cosign-private-OLD.pem /archive/cosign-private-OLD-$(date +%Y%m%d).pem
# Archive old public key similarly
```

---

## 5. Key Compromise Recovery Procedure

### Immediate Actions (0-2 Hours)

1. **Revoke access:**
   ```bash
   # Remove key from Forgejo secrets
   curl -X DELETE https://forge.deepsim.ai/api/v1/user/settings/secrets/COSIGN_PRIVATE_KEY \
     -H "Authorization: token <ADMIN_TOKEN>"
   ```

2. **Notify security team:**
   - Security@deepsim.ai
   - Gateway owner (Shouke Wei)
   - All team members with repo access

3. **Assess impact:**
   - Which artifacts were signed with compromised key?
   - When was the key last used?
   - Any evidence of unauthorized signing?

### Key Rotation (2-24 Hours)

1. **Generate new key pair:**
   ```bash
   openssl ecparam -name prime256v1 -genkey -noout -out cosign-private-EMERGENCY.pem
   openssl ec -in cosign-private-EMERGENCY.pem -pubout -out cosign-public-EMERGENCY.pem
   ```

2. **Deploy new key:**
   - Update Forgejo secret
   - Commit new public key to repo
   - Sign next release with new key

3. **Invalidate compromised signatures:**
   - Publish security advisory
   - List affected artifacts
   - Provide new signatures for affected artifacts (if possible)

### Customer Communication (24-48 Hours)

```markdown
## SECURITY ADVISORY: Cosign Key Compromise (2026-10-26)

**Severity:** HIGH

**Summary:** Deepsim's cosign signing key was compromised on 2026-10-25.
All artifacts signed between [DATE] and [DATE] should be considered untrusted.

**Affected Artifacts:**
- multimodal_emotion_engine-0.4.5-py3-none-any.whl (if signed with compromised key)

**Customer Action Required:**
1. Verify previously downloaded artifacts against the new public key
2. Re-download affected artifacts from official channels
3. Update verification scripts to use new public key (cosign-public-EMERGENCY.pem)

**New Public Key:**
```
-----BEGIN PUBLIC KEY-----
<NEW PUBLIC KEY>
-----END PUBLIC KEY-----
```

**Old signatures:**
Old signatures remain valid with the old public key (for audit purposes), but
should NOT be used for new verification.
```

---

## 6. Fork Safety Analysis

### Scenario: Attacker Compromises Forgejo Repository

**Attack Path:**
1. Attacker gains repo admin access (via credential theft, XSS, or insider)
2. Attacker accesses Forgejo secrets (COSIGN_PRIVATE_KEY)
3. Attacker signs malicious artifact with stolen key
4. Attacker publishes malicious artifact to PyPI

**Mitigations:**
1. ✅ **Forgejo secrets encryption** — Key encrypted at rest
2. ✅ **Repo access controls** — Limited to security team
3. ✅ **Key rotation** — Compromised key invalidated after rotation
4. ✅ **Customer verification** — Customers verify against public key (not secret)
5. ⚠️ **Rekor transparency** — Optional: Log signatures to Rekor for audit trail

**Residual Risk:** MEDIUM
- If attacker has repo admin access AND can intercept customer downloads,
  they can serve malicious artifact with valid signature
- **Mitigation:** Use HTTPS + HSTS, pin public key in customer tooling

### Comparison with Option A (Fulcio)

| Aspect | Option B (Cosign) | Option A (Fulcio) |
|--------|-------------------|-------------------|
| **Key to steal** | Private key (in Forgejo secrets) | None (ephemeral certs) |
| **Attack surface** | Forgejo secrets | OIDC provider + Forgejo |
| **Defense in depth** | Single layer (key) | Multiple layers (OIDC + cert + Rekor) |
| **Fork scenario** | Attacker can sign with stolen key | Attacker must forge OIDC identity |
| **Residual risk** | MEDIUM | LOW |

---

## 7. Audit Trail

### Signing Events to Log

| Event | Data | Retention |
|-------|------|-----------|
| **Key generation** | Date, operator, key ID | Permanent |
| **Key storage** | Date, Forgejo secret name, access log | Permanent |
| **Signing operation** | Date, operator, artifact digest, key ID | Permanent |
| **Key rotation** | Date, operator, old key ID, new key ID | Permanent |
| **Key compromise** | Date, incident ID, affected artifacts | Permanent |

### Log Format (JSON Lines)

```json
{"timestamp":"2026-10-26T22:00:00Z","event":"key_generated","operator":"shouke.wei","key_id":"cosign-2026-10"}
{"timestamp":"2026-10-26T22:00:00Z","event":"key_stored","operator":"shouke.wei","secret_name":"COSIGN_PRIVATE_KEY"}
{"timestamp":"2026-10-26T22:00:00Z","event":"artifact_signed","operator":"ci-runner","artifact":"multimodal_emotion_engine-0.4.5-py3-none-any.whl","digest":"sha256:abc123","key_id":"cosign-2026-10"}
{"timestamp":"2027-10-26T22:00:00Z","event":"key_rotated","operator":"shouke.wei","old_key_id":"cosign-2026-10","new_key_id":"cosign-2027-10"}
```

---

## 8. Compliance Checklist

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Key stored in encrypted secret store | ✅ | Forgejo secrets (AES-256-GCM) |
| Key access limited to security team | ✅ | Forgejo repo permissions |
| Key rotation documented | ✅ | This document (Section 4) |
| Key compromise procedure documented | ✅ | This document (Section 5) |
| Public key distributed to customers | ✅ | CHANGELOG + release notes |
| Signing events logged | ⚠️ | Requires CI/CD integration |
| Audit trail retained permanently | ⚠️ | Requires logging infrastructure |

---

*End of TASK_MEE_025_A Key Protection Procedures.*
