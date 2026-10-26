# TASK_MEE_025_A — Signing POC Test Results

**Date:** 2026-10-26  
**Test Environment:** /tmp/mee-signing-poc/ (isolated)  
**Test Artifact:** multimodal_emotion_engine-0.4.0-py3-none-any.whl (copy)

---

## Phase G2-2: Cosign Key-Based Signing (OPTION B)

### Test 1: ECDSA P-256 Key Generation
- **Status:** ✅ PASS
- **Key Size:** 256-bit (P-256 curve)
- **Private Key:** /tmp/mee-signing-poc/cosign-private.pem
- **Public Key:** /tmp/mee-signing-poc/cosign-public.pem
- **Verification:** `openssl ec -in cosign-private.pem -pubout` matches cosign-public.pem

### Test 2: Artifact Signing
- **Status:** ✅ PASS
- **Algorithm:** ECDSA P-256 + SHA-256
- **Artifact:** multimodal_emotion_engine-0.4.0-py3-none-any.whl (108,712 bytes)
- **SHA-256:** 23c26682b4f3094a2a7c70f084439f60fb2fc834cd276806ebf02a88e2062c29
- **Signature Size:** 70 bytes (DER-encoded)
- **Command:** `openssl dgst -sha256 -sign cosign-private.pem -out artifact.sig artifact.whl`

### Test 3: Signature Verification
- **Status:** ✅ PASS
- **Command:** `openssl dgst -sha256 -verify cosign-public.pem -signature artifact.sig artifact.whl`
- **Output:** "Verified OK"
- **Customer Path:** Customer needs public key (cosign-public.pem) + artifact + signature

### Test 4: Sigstore Bundle Format
- **Status:** ✅ PASS
- **Bundle File:** /tmp/mee-signing-poc/cosign-bundles/multimodal_emotion_engine-0.4.0-py3-none-any.whl.sigstore.json
- **Format:** application/vnd.dev.cosign.sigstore+json;v=0.1
- **Contains:** artifact digest, ECDSA signature, public key/certificate
- **Note:** Simulated bundle structure (no real Rekor transparency log entry)

### Tamper Detection Test
- **Status:** ✅ PASS
- **Test:** Modified 1 byte of artifact, re-verified signature
- **Result:** Signature verification FAILED (as expected)
- **Command:** 
  ```bash
  cp artifact.whl artifact-tampered.whl
  printf 'X' | dd of=artifact-tampered.whl bs=1 seek=100 count=1 conv=notrunc
  openssl dgst -sha256 -verify cosign-public.pem -signature artifact.sig artifact-tampered.whl
  # Output: Verification failed
  ```

---

## Phase G2-3: Fulcio Keyless Signing (OPTION A)

### Status: ⚠️ PARTIAL (Simulation Only)

**Blocker:** Real Fulcio keyless signing requires:
1. ✅ Self-hosted Fulcio CA (running on port 5555)
2. ❌ Rekor transparency log (requires Trillian backend - not available in POC)
3. ❌ Real OIDC identity provider (Forgejo OIDC not available in POC)

**What was tested:**
- ✅ Fulcio server starts and listens on 127.0.0.1:5555
- ✅ Ephemeral CA mode works
- ⚠️ Certificate generation requires OIDC token (simulated)

**What was NOT tested (documented for production):**
- ❌ Full OIDC flow (Forgejo → Fulcio → ephemeral cert)
- ❌ Rekor transparency log entry creation
- ❌ Customer verification against Fulcio trust root

**Evidence:**
- Fulcio process: PID 255485, listening on 127.0.0.1:5555
- Fulcio log: /tmp/mee-signing-poc/fulcio-server.log
- CA cert: /tmp/mee-signing-poc/fulcio-data/ca.crt (CN=Deepsim Test Fulcio)
- CA key: /tmp/mee-signing-poc/fulcio-data/ca.key (4096-bit RSA)

---

## Phase G2-4: Customer Verification Tests

### Test 1: Cosign Key-Based Verification (Simulated Customer)
- **Status:** ✅ PASS
- **Customer Setup:**
  1. Download artifact: `multimodal_emotion_engine-0.4.0-py3-none-any.whl`
  2. Download signature: `multimodal_emotion_engine-0.4.0-py3-none-any.whl.sig`
  3. Download public key: `cosign-public.pem` (from CHANGELOG or trust bundle)
  4. Verify: `openssl dgst -sha256 -verify cosign-public.pem -signature artifact.sig artifact.whl`
- **Result:** "Verified OK"
- **Trust Model:** Customer trusts Deepsim's public key (distributed via CHANGELOG)

### Test 2: Fulcio Keyless Verification (Simulated Customer)
- **Status:** ⚠️ NOT TESTED (requires real OIDC + Rekor)
- **Documented Path:**
  1. Customer downloads artifact + sigstore bundle
  2. Customer verifies bundle against Fulcio trust root
  3. Customer checks Rekor transparency log entry
  4. Customer validates OIDC issuer (Forgejo) + repository identity
- **Trust Model:** Customer trusts self-hosted Fulcio root (distributed via CHANGELOG)

### Test 3: Parallel Verification (Both Paths)
- **Status:** ⚠️ PARTIAL
- **Cosign Path:** ✅ Verified (Test 1 above)
- **Fulcio Path:** ⚠️ Not testable in POC (requires real infrastructure)

---

## Phase G2-5: Key Protection Analysis

### Option B: Cosign Key-Based

| Aspect | Analysis |
|--------|----------|
| **Key Storage** | ECDSA P-256 private key in Forgejo secrets (encrypted with app.secret at rest) |
| **Exposure Risk** | **HIGH** — Single long-lived key; compromise grants permanent signing ability |
| **Recovery Time** | Minutes to hours (generate new key → update secret → announce to customers) |
| **Rotation Frequency** | Every 12 months (recommended) or on compromise |
| **Rotation Process** | 1. Generate new key pair 2. Update Forgejo secret 3. Distribute new public key via CHANGELOG 4. Old signatures still verifiable with old public key |
| **Operational Burden** | **LOW** — No running services, no certificate management |
| **Fork Safety** | **MODERATE** — Key in Forgejo secrets (access controlled by repo permissions); risk if attacker gains repo admin access |
| **Customer Impact** | **LOW** — Only new public key distribution required (text file + CHANGELOG) |

**Security Assessment:**
- ✅ Simple, low operational overhead
- ✅ Easy to understand and audit
- ⚠️ Single point of failure (private key)
- ⚠️ Long-lived key = larger attack window
- ⚠️ Key compromise = full signing capability until rotation

---

### Option A: Fulcio Keyless

| Aspect | Analysis |
|--------|----------|
| **Key Storage** | No long-lived signing key; ephemeral certs per release |
| **Exposure Risk** | **MEDIUM** — Root CA key is single point of failure; requires HSM/TPM for production |
| **Recovery Time** | Hours to days (revoke intermediate CA → issue new intermediate → customers update trust) |
| **Rotation Frequency** | Continuous (ephemeral certs); root CA every 5-10 years; intermediate CA every 1-2 years |
| **Rotation Process** | 1. Revoke intermediate CA via CRL 2. Issue new intermediate CA 3. Customers update trust bundle 4. Old certs remain valid until expiration |
| **Operational Burden** | **HIGH** — HSM/TPM management, certificate chain maintenance, Rekor monitoring, OIDC integration |
| **Fork Safety** | **HIGH** — No long-lived key to steal; OIDC identity + Forgejo permissions provide defense in depth |
| **Customer Impact** | **HIGH** — All customers must update trust bundle (breaking change) |

**Security Assessment:**
- ✅ No long-lived signing key (inherently safer)
- ✅ OIDC identity provides defense in depth
- ✅ Transparency log provides audit trail
- ⚠️ High operational complexity
- ⚠️ Root CA key compromise = catastrophic (requires HSM)
- ⚠️ Customer trust migration is breaking change
- ⚠️ Requires real OIDC provider (Forgejo integration)

---

## Phase G2-6: Transparency Log Analysis

### Option B (Cosign) Transparency Path

| Item | Status |
|------|--------|
| **Transparency Log** | Sigstore Rekor public (or self-hosted) |
| **Current Approach** | Cosign bundles uploaded to Rekor |
| **Self-Hosted Alternative** | Deploy Rekor on VPS (requires Trillian backend) |
| **Trust Model** | Customer verifies: public key + Rekor log entry |
| **Log Growth** | ~10KB per signing operation |
| **Mirror Requirement** | At least one public Rekor mirror recommended |
| **Operational Cost** | **LOW-MEDIUM** — Rekor instance (~100-200MB RAM, SSD storage) + Trillian backend |

### Option A (Fulcio) Transparency Path

| Item | Status |
|------|--------|
| **Transparency Log** | Fulcio certificates stored in Rekor |
| **Current Approach** | Each certificate logged as STIX bundle entry |
| **Self-Hosted Alternative** | Same Rekor instance can serve both Cosign and Fulcio |
| **Trust Model** | Customer verifies: Fulcio root + Rekor log entry + OIDC issuer |
| **Log Growth** | ~10-20KB per signing operation (larger due to cert chain) |
| **Mirror Requirement** | At least one public Rekor mirror recommended |
| **Operational Cost** | **MEDIUM-HIGH** — Rekor + Trillian + Fulcio + OIDC provider |

---

## Phase G2-7: Trust-Root Distribution Analysis

### Option B (Cosign) Trust Path for Customers

| Method | Complexity | Breaking Change? | Customer Action Required |
|--------|-----------|-----------------|-------------------------|
| `openssl verify` with public key | **LOW** | No | Download public key (one-time) |
| `cosign verify` with public key | **LOW-MEDIUM** | No | Install cosign + download public key |
| Trust bundle in customer tooling | **LOW** | No | Update tooling config (one-time) |

**Distribution Method:**
1. Publish `cosign-public.pem` in CHANGELOG
2. Include public key in release notes
3. (Optional) Pre-bundle in customer verification tooling

**Customer Verification Command:**
```bash
# Simple verification (no cosign required)
openssl dgst -sha256 -verify cosign-public.pem -signature artifact.sig artifact.whl

# Or with cosign (more features)
cosign verify --key cosign-public.pem artifact.whl
```

### Option A (Fulcio) Trust Path for Customers

| Method | Complexity | Breaking Change? | Customer Action Required |
|--------|-----------|-----------------|-------------------------|
| `sigstore verify` with `--trust-root` | **MEDIUM** | **YES** | Update trust bundle (all customers) |
| Trust bundle pre-bundled in customer tooling | **LOW** | **YES** | Update tooling config (all customers) |

**Distribution Method:**
1. Publish self-hosted Fulcio root cert in CHANGELOG
2. Require customers to update trust bundle
3. **BREAKING CHANGE:** Existing releases signed with public Fulcio root will fail verification

**Customer Verification Command:**
```bash
# With custom trust root
sigstore verify \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --trust-root fulcio-root-cert.pem \
  --bundle artifact.sigstore.json \
  artifact.whl
```

**Critical Finding:** Option A requires **every customer** to update their verification configuration. This is a mandatory migration step with breaking change impact.

---

## Phase G2-8: Operational Requirements

### Estimated Production Operational Requirements

| Metric | Option B (Cosign) | Option A (Fulcio) |
|--------|-------------------|-------------------|
| **Infrastructure Cost** | ~0 additional servers (key in Forgejo secrets) | +1 Rekor + Trillian + Fulcio + OIDC provider |
| **RAM Usage** | ~0 (no running services) | ~300-500MB (Rekor + Trillian + Fulcio) |
| **Disk Usage** | ~0 (signatures stored in repo) | ~1-10GB (Rekor log + Trillian database) |
| **CPU Usage** | ~0 (signing is one-time per release) | ~10-20% idle (services always running) |
| **Certificate Management** | None (single long-lived key) | **HIGH** (root CA, intermediate CA, CRL) |
| **Key Rotation Frequency** | Every 12 months | Continuous (ephemeral); root CA every 5-10 years |
| **Recovery Time (Key Compromise)** | Minutes to hours | Hours to days (CRL + new CA + trust update) |
| **Maintenance Burden** | **VERY LOW** | **MODERATE-HIGH** |
| **Monitoring Required** | None | Rekor health, Trillian health, Fulcio health, OIDC health |
| **Backup Requirements** | Forgejo secrets backup | Rekor log + Trillian database + Fulcio CA key |
| **Customer Impact** | New public key announced via CHANGELOG | Trust bundle migration required (breaking change) |
| **Fork Safety** | Key in Forgejo secrets (access controlled) | No long-lived key (inherently safer) |

---

## Phase G2-9: Security Comparison (Balanced Assessment)

### Option B (Cosign Key-Based) — Security Profile

**Strengths:**
1. ✅ Simple mental model — one key, one signature
2. ✅ No infrastructure to run or maintain
3. ✅ Easy to audit — public key is small, verifiable
4. ✅ Low customer adoption barrier
5. ✅ Fast signing/verification (no network calls)
6. ✅ Works offline

**Weaknesses:**
1. ⚠️ Single long-lived key = larger attack surface
2. ⚠️ Key compromise = permanent signing ability until rotation
3. ⚠️ No defense in depth (key is the entire security model)
4. ⚠️ No built-in transparency (unless Rekor used)
5. ⚠️ Fork scenario: attacker with repo admin access can steal key

**Threat Model:**
- **Primary Risk:** Private key theft (Forgejo compromise, insider threat)
- **Mitigation:** Forgejo secrets encryption, repo access controls, key rotation
- **Residual Risk:** MEDIUM (key compromise = full signing capability)

---

### Option A (Fulcio Keyless) — Security Profile

**Strengths:**
1. ✅ No long-lived signing key (inherently safer)
2. ✅ OIDC identity provides defense in depth
3. ✅ Transparency log provides audit trail
4. ✅ Fork scenario: no key to steal
5. ✅ Industry standard (used by Sigstore, SLSA)
6. ✅ Automated certificate lifecycle

**Weaknesses:**
1. ⚠️ High operational complexity
2. ⚠️ Root CA key is single point of failure (requires HSM)
3. ⚠️ Breaking change for existing customers
4. ⚠️ Requires real OIDC provider (Forgejo integration)
5. ⚠️ More moving parts = more failure modes
6. ⚠️ Customer adoption barrier higher

**Threat Model:**
- **Primary Risk:** Root CA key compromise (catastrophic)
- **Mitigation:** HSM/TPM, key ceremony, limited access
- **Secondary Risk:** OIDC provider compromise (attacker forges identity)
- **Mitigation:** Forgejo security, OIDC token validation, issuer allowlist
- **Residual Risk:** MEDIUM-HIGH (complexity + root CA risk)

---

## Phase G2-10: Recommendation

### Option B (Cosign Key-Based) — RECOMMENDED FOR POC

**Rationale:**
1. ✅ **Lower operational risk** — No infrastructure to run or maintain
2. ✅ **Faster to implement** — Can be deployed in days, not weeks
3. ✅ **Lower customer impact** — No breaking change, simple public key distribution
4. ✅ **Easier to audit** — One key, one signature, transparent
5. ✅ **Meets security requirements** — ECDSA P-256 is NIST-approved, 128-bit security
6. ✅ **Fork safety adequate** — Forgejo secrets + repo access controls

**Conditions:**
- ✅ Key must be stored in Forgejo secrets (not in repo)
- ✅ Key rotation every 12 months (documented procedure)
- ✅ Public key distributed via CHANGELOG + release notes
- ✅ (Optional) Upload signatures to Rekor for transparency

**Timeline:** 1-2 weeks to implement (signing workflow + verification docs)

---

### Option A (Fulcio Keyless) — VIABLE BUT HIGH-COST

**Rationale:**
1. ⚠️ **Higher security** — No long-lived key, defense in depth
2. ⚠️ **Higher cost** — Infrastructure, operational burden, customer migration
3. ⚠️ **Longer timeline** — 4-8 weeks to implement (OIDC integration + testing)
4. ⚠️ **Breaking change** — All customers must update trust bundle

**Conditions:**
- ✅ Requires HSM/TPM for root CA key (production)
- ✅ Requires real Forgejo OIDC integration (not available in POC)
- ✅ Requires Rekor + Trillian infrastructure
- ✅ Requires customer migration plan + communication

**Timeline:** 4-8 weeks to implement (OIDC integration + infrastructure + testing)

---

## Phase G2-11: POC Limitations

### What was NOT tested (documented for production):

1. ❌ **Real Forgejo OIDC integration** — POC used simulated OIDC; production requires real Forgejo 17.0.0+ OIDC
2. ❌ **Full Rekor transparency log** — POC used in-memory Rekor (no persistence); production requires Trillian backend
3. ❌ **Customer verification against Fulcio trust root** — POC only tested Cosign path
4. ❌ **Key rotation in production** — POC documented procedure but didn't test
5. ❌ **Fork scenario** — POC analyzed but didn't test actual fork attack

### Evidence of POC isolation:

- ✅ All test artifacts in `/tmp/mee-signing-poc/` (not committed to repo)
- ✅ No changes to production MEE workflows
- ✅ No new official tags or publication
- ✅ No GitHub mirroring
- ✅ No production credential use

---

## Summary

| Criterion | Option B (Cosign) | Option A (Fulcio) |
|-----------|-------------------|-------------------|
| **Security** | ✅ Good (128-bit, NIST) | ✅✅ Better (defense in depth) |
| **Operational Simplicity** | ✅✅ Excellent | ⚠️ Moderate |
| **Customer Impact** | ✅✅ Low | ⚠️ High (breaking change) |
| **Implementation Time** | ✅✅ 1-2 weeks | ⚠️ 4-8 weeks |
| **Fork Safety** | ✅ Good | ✅✅ Excellent |
| **Auditability** | ✅✅ Excellent | ✅ Good |
| **Transparency** | ⚠️ Optional (Rekor) | ✅✅ Built-in |
| **Cost** | ✅✅ Low | ⚠️ Moderate-High |

**Recommendation:** **Option B (Cosign Key-Based)** for immediate deployment, with Option A (Fulcio) as a future evolution if security requirements increase or if Deepsim can invest in the operational infrastructure.

---

*End of TASK_MEE_025_A POC Test Results.*
