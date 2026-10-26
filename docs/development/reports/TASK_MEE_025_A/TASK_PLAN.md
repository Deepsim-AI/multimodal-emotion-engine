# TASK_MEE_025_A — CTO PLAN (G1)

**Gate:** G1 — Planning  
**Date:** 2026-10-26  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)  
**Task ID:** TASK_MEE_025_A  
**Title:** MEE Signing Proof of Concept — Key-based Cosign vs Self-hosted Fulcio  

---

## Objective

Run a bounded proof of concept comparing two signing approaches for Deepsim's independent release infrastructure:
1. **Option B (Cosign key-based)** — ECDSA P-256 key pair in local secret store
2. **Option A (Fulcio keyless)** — Self-hosted Fulcio CA + Rekor with Forgejo-compatible OIDC

Deliverables: reproducible test evidence, security comparison, operational analysis, and recommendation.

---

## Environment Setup (Verified on this host)

| Resource | Available | Notes |
|----------|-----------|-------|
| Docker Engine | 29.9.2 | ✅ Can run Fulcio + Rekor containers |
| Docker Compose | v5.6.1 | ✅ Can orchestrate multi-container POC stack |
| sigstore CLI | 3.6.7 | ✅ Installed for verification tests |
| OpenSSL | 3.0.2 | ✅ Available for key generation, cert management |
| Disk space | 658G free | ✅ More than sufficient |
| RAM | ~17Gi available (system idle) | ✅ Fulcio (~50MB) + Rekor (~200MB) fit easily |
| CPU | 12 cores | ✅ Adequate for build/signing operations |
| cosign binary | **NOT installed** | ❌ Must be installed as a POC dependency |

### Pre-requisite: Install cosign

```bash
# Install cosign (POC dependency only — not committed to production)
COSIGN_VERSION="1.13"  # latest stable at time of planning
curl -L https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64 -o /usr/local/bin/cosign
chmod +x /usr/local/bin/cosign
cosign version  # verify installation
```

### Pre-requisite: Create isolated test repository on Forgejo

```bash
# This requires a Forgejo API call — only for the POC environment, not production
# Owner must authorize creating this repo as part of G1-G2 transition
# Suggested name: deepsim-hub-test-signing-poc (private)
```

---

## Phase G2-1: Environment Setup (Implementer)

### Step 1: Install POC Dependencies

| # | Action | Details |
|---|--------|---------|
| 1 | Install cosign binary | From sigstore/cosign releases v1.13+ |
| 2 | Create isolated test directory | `/tmp/mee-signing-poc/` — all POC artifacts live here, never committed to repo |
| 3 | Generate ECDSA P-256 key pair for Cosign | `openssl ecparam -name prime256v1 -genkey -noout -out cosign-private.pem` + public key extraction |
| 4 | Create test Forgejo repo (private) | Via API: create empty private repo named `deepsim-hub-test-signing-poc` — only for POC testing |

**Exact file locations:**

| File | Path | Purpose |
|------|------|---------|
| cosign key pair | `/tmp/mee-signing-poc/cosign-private.pem` + `.pub` | Signing identity (local, not committed) |
| self-signed Fulcio root cert | `/tmp/mee-signing-poc/fulcio-root-cert.pem` | Self-hosted trust anchor |
| Rekor public key | `/tmp/mee-signing-poc/rekor-key.pub` | Transparency log integrity verification |
| OIDC test certificate | `/tmp/mee-signing-poc/fake-oidc-certificate.pem` | For Fulcio testing with simulated Forgejo identity |

### Step 2: Deploy Self-hosted Fulcio + Rekor Stack

**Docker Compose configuration for POC:**

```yaml
# /tmp/mee-signing-poc/docker-compose.yml (POC only)
version: "3.8"

services:
  rekor:
    image: ghcr.io/sigstore/rekor:v1.2.0
    ports:
      - "3447:3447"
    volumes:
      - ./rekor-data:/data  # persistent log storage (POC only)
    environment:
      - STORAGE_DRIVER=filesystem

  fulcio:
    image: ghcr.io/sigstore/fulcio:v1.6.0
    ports:
      - "5555:5555"
    volumes:
      - ./fulcio-data:/data
    environment:
      - FULCIO_CA_PRIVATE_KEY_FILE=/data/ca.key
      - FULCIO_ISSUER=https://localhost:8443  # simulated Forgejo OIDC issuer for POC
```

**Initial setup commands:**

```bash
# Generate self-signed Fulcio CA key pair (POC only)
mkdir -p /tmp/mee-signing-poc/fulcio-data
openssl genrsa -out /tmp/mee-signing-poc/fulcio-data/ca.key 4096
openssl req -new -x509 -key /tmp/mee-signing-poc/fulcio-data/ca.key \
  -out /tmp/mee-signing-poc/fulcio-data/ca.crt \
  -days 365 -subj "/CN=Deepsim Test Fulcio"

# Start POC stack
cd /tmp/mee-signing-poc
docker compose up -d
```

### Step 3: Simulate Forgejo OIDC Issuer for POC

Since we cannot use real Forgejo in the POC (it would require connecting to production infrastructure):

```bash
# Option 1: Use a local self-signed OIDC issuer
# Option 2: Use sigstore's built-in test mode with --trust-root flag
# Option 3: Simulate via mock OIDC endpoint for testing purposes only
```

**Important POC constraint:** Real Forgejo OIDC token issuance requires actual Forgejo OAuth2 server running. For the POC, we will use **self-signed certificate + manual trust distribution** as a simulation approach, documenting what would change when connecting to real Forgejo in production.

---

## Phase G2-2: Cosign Signing POC (Implementer)

### Step 3: Sign test artifact with Cosign key-based approach

| # | Action | Details |
|---|--------|---------|
| 1 | Create a test wheel file | Use existing MEE v0.4.5 wheel as the test artifact (read-only copy) |
| 2 | Generate `.sigstore.json` bundle with cosign sign | `cosign sign --key cosign-private.pem <test-artifact>` |
| 3 | Upload bundle to isolated POC environment | Store locally in `/tmp/mee-signing-poc/cosign-bundles/` — do NOT upload to any registry |
| 4 | Verify with public key | `cosign verify --key cosign-public.pem <test-artifact>` |

**Exact verification command:**

```bash
COSIGN_PUBLIC="/tmp/mee-signing-poc/cosign-public.pem"
ARTIFACT="/tmp/mee-signing-poc/test-wheel.whl"

# Verify signature with key-based Cosign (simulated customer path)
cosign verify --key "$COSIGN_PUBLIC" "$ARTIFACT"
# Expected: PASS (with appropriate output showing identity and issuer claims)
```

---

## Phase G2-3: Fulcio Keyless Signing POC (Implementer)

### Step 4: Sign test artifact with self-hosted Fulcio + simulated OIDC

| # | Action | Details |
|---|--------|---------|
| 1 | Create test wheel file (same as Step 3 above) | Identical artifact for fair comparison |
| 2 | Generate `.sigstore.json` bundle with Fulcio CA | Use self-signed Fulcio root cert generated in Step 2.2 |
| 3 | Verify against self-hosted trust root | `sigstore verify github --trust-root <self-hosted-root> --bundle ...` |
| 4 | Record verification output | Capture full output for comparison report |

**Note:** This step simulates the production path — in reality, Fulcio would need:
- Real Forgejo OIDC issuer configured (not local mock)
- Proper certificate chain (self-signed root → intermediate CA → ephemeral certs)
- Rekor transparency log integration for certificate storage and retrieval

---

## Phase G2-4: Customer Verification Tests (Implementer + CTO)

### Test 1: Cosign key-based verification

```bash
# Simulated customer: download artifact + verify with known public key
cosign verify --key <public-key.pub> \
  --certificate-identity "ci@deepsim.ai" \
  --certificate-oidc-issuer "https://forge.deepsim.ai:8443" \
  test-artifact.sigstore.json test-artifact.whl
```

### Test 2: Fulcio keyless verification against self-hosted root

```bash
sigstore verify github \
  --repository Deepsim-AI/test-repo \
  --trust-root <self-hosted-fulcio-root-cert.pem> \
  --bundle test-artifact.sigstore.json \
  test-artifact.whl
```

### Test 3: Parallel verification (cosign + Fulcio roots)

```bash
# Verify same artifact signed with both methods produces identical verification output format
# Document differences in chain-of-trust presentation
```

---

## Phase G2-5: Key Protection Analysis (Implementer + CTO)

### Cosign key protection analysis

| Aspect | Analysis |
|--------|---------|
| **Storage** | ECDSA P-256 key stored in Forgejo secrets (encrypted with app.secret at rest) |
| **Exposure risk** | Single secret, long-lived — compromise grants permanent signing ability |
| **Recovery** | Generate new key pair → update Forgejo secret → announce to customers via CHANGELOG + release notes |
| **Rotation** | Simple: replace secret value in Forgejo. Requires customer trust bundle update for verification |
| **Operational burden** | Low — no running services, no certificate management, no CA infrastructure |

### Fulcio keyless protection analysis

| Aspect | Analysis |
|--------|---------|
| **Storage** | Ephemeral certificates — no long-lived signing key exists |
| **Exposure risk** | Root CA key compromise is the single point of failure (HSM/TPM required for production) |
| **Recovery** | Revoke intermediate CA via CRL → issue new intermediate CA signed with fresh root → customers update trust bundle |
| **Rotation** | New root cert + publish to transparency log → announce migration window (N months) |
| **Operational burden** | High — HSM/TPM management, certificate chain maintenance, Rekor monitoring, OIDC integration |

---

## Phase G2-6: Transparency Log Analysis

### Option B (Cosign) transparency path

| Item | Status |
|------|--------|
| Current approach | Cosign bundles uploaded to Sigstore Rekor public (same as Fulcio keyless) |
| Self-hosted alternative | Can deploy Rekor on VPS; Mirrors remain the same for verification |
| Trust model | Customer verifies against known cosign public key + Rekor transparency log |
| Operational cost | Low — only Rekor instance maintenance (about 100MB RAM, SSD storage) |

### Option A (Fulcio) transparency path

| Item | Status |
|------|--------|
| Fulcio certificates stored in Rekor | Yes — each certificate is logged as an STIX bundle entry |
| Self-hosted Rekor | Same instance can serve both Cosign and Fulcio bundles |
| Public mirror requirement | At least one public Rekor mirror recommended for availability |
| Operational cost | Moderate — monitor log size growth (~10KB per signing operation) |

---

## Phase G2-7: Trust-Root Distribution Analysis

### Current customer verification (GitHub + public Fulcio)

```bash
# Works out of the box — public Fulcio root pre-bundled in sigstore-go trust bundle
sigstore verify github \
  --repository Deepsim-AI/multimodal-emotion-engine \
  --bundle artifact.sigstore.json \
  artifact.whl
# → PASS (no extra flags needed)
```

### Option B (Cosign) trust path for customers

| Method | Complexity | Breaking change? |
|--------|-----------|-----------------|
| cosign verify with public key | Low — one `--key` flag per customer | No (public key distributed as text file) |
| cosign verify with cert identity | Medium — requires OIDC issuer configuration | Yes (requires trust root update) |

### Option A (Fulcio) trust path for customers

| Method | Complexity | Breaking change? |
|--------|-----------|-----------------|
| sigstore verify github with custom --trust-root | Medium — one `--trust-root` flag | Yes (breaking change for existing releases) |
| Updated trust bundle pre-bundled in customer tooling | Low — transparent to customers | No (requires updating customer verification tooling) |

**Critical finding:** Option A requires **every customer** to update their verification configuration with the self-hosted Fulcio root. This is a mandatory migration step. Option B only requires distributing a public key, which is simpler but still requires action.

---

## Phase G2-8: Operational Requirements (Implementer)

### Estimated production operational requirements per option:

| Metric | Cosign Key-Based | Fulcio Keyless |
|--------|-----------------|----------------|
| Infrastructure cost | ~0 additional servers | +1 Rekor instance (~100MB RAM) |
| Certificate management | None (single long-lived key) | High (root CA, intermediate CA, CRL) |
| Key rotation frequency | Every 12 months | Continuous (ephemeral certs per release) |
| Recovery time (key compromise) | Minutes to hours | Hours to days (CRL + new CA + trust update) |
| Maintenance burden | Very low | Moderate to high |
| Customer impact | New public key announced via CHANGELOG | Trust bundle migration required for all customers |
| Fork safety | Key in Forgejo secrets — access controlled by repo permissions | No long-lived key = inherently safer against theft |

---

## Phase G3: Review (Reviewer)

**Scope:** Exactly one task directory — `docs/development/reports/TASK_MEE_025_A/`

1. Verify all acceptance criteria (AC-1 through AC-6) pass and are recorded
2. Verify POC artifacts are in isolated test environment, not committed to any repository
3. Verify security comparison is balanced (not biased toward either option)
4. Verify trust-root migration analysis is complete for both options
5. Produce `REVIEW_REPORT.md` with recommendation to CTO

---

## Phase G4: CTO Approval

- Review Implementer's test results and verification evidence
- Confirm POC artifacts remain isolated (not committed, not published)
- Issue `CTO_APPROVAL.md` with final decision on recommended path
- Do NOT execute Post-G4 duties

---

## Acceptance Criteria

| AC | Criterion | Verification Method | Expected |
|----|-----------|-------------------|----------|
| AC-1 | Cosign signing produces valid bundles verifiable against known public key | cosign verify --key <public-key> | PASS |
| AC-2 | Fulcio POC signs artifacts via simulated Forgejo OIDC identity | sigstore verify github with self-hosted root cert | PASS (with expected warnings) |
| AC-3 | Customer-side verify_release.sh reports PASS for both paths against documented trust configuration | Live verification tests | Both PASS |
| AC-4 | Key compromise, recovery, rotation procedures documented (not theoretical only) | Document review | Documented with concrete steps |
| AC-5 | Operational cost estimates provided (CPU, RAM, disk, maintenance hours/week) | Infrastructure analysis report | Quantified per option |
| AC-6 | Security comparison between Cosign and Fulcio approaches documented and balanced | Comparative analysis document | Balanced assessment |

---

## Stop Conditions

- Docker cannot run on this host → stop and report (Fulcio POC impossible)
- cosign installation fails → stop and report for Option B only (Fulcio may still be viable)
- Any signing produces invalid bundles → investigate and correct before proceeding
- Any test fails → stop, document, report to CTO

---

## Constraints Enforced

| Constraint | Enforcement |
|-----------|-------------|
| No production signing migration | All work in /tmp/mee-signing-poc/ isolated directory |
| No changes to protected MEE workflows | Read-only access to existing release artifacts only |
| No official release signing | Test artifacts are copies, never original distribution files |
| No new official tags or publication | Nothing pushed to any repository beyond this task's local dir |
| Isolated test environment | Docker containers for POC services use host networking in isolated compose project |

---

## Model Pressure Management

| Phase | Required Models | Always Unload |
|-------|-----------------|---------------|
| G2 implementation | qwen3.6:35b (CTO), qwen3.8:27b (Implementer) | ornith-1.5:35b, laguna-xs-2.1 |
| G3 review | laguna-xs-2.1, qwen3.6:35b, nomic-embed-text | qwen3.8:27b, ornith-1.5:35b |
| Idle | nomic-embed-text only | all large models |

---

## Non-Goals for this POC (to prevent scope creep)

- ❌ Production deployment of either signing method
- ❌ Real Forgejo OIDC integration (POC uses simulated identity)
- ❌ Customer communication or migration planning beyond analysis
- ❌ Infrastructure that persists beyond POC isolation period
- ❌ Integration with Keygate license verification
- ❌ Multi-repository comparison (single test repo is sufficient for POC)

---

*End of TASK_MEE_025_A CTO PLAN (G1).*
