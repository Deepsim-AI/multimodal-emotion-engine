# TASK_MEE_029 — G3 Review Package

**Task ID:** TASK_MEE_029
**Gate:** G3 — Senior Code Reviewer
**Date:** 2026-10-27 (PDT)
**Reviewer:** 🔍 (ollama/laguna-xs-2.1:q4_K_M)
**Scope:** Verify the additive Cosign key-based (Option B) signing path in `release-sigstore.yml`, the public key distribution, the customer verification helper, and the CI pipeline verification.

---

## 1. Review Scope & Method

### 1.1 What to review

| # | Item | File(s) | Type |
|---|------|---------|------|
| R1 | Additive signing step | `.github/workflows/release-sigstore.yml` | workflow step (new) |
| R2 | Additive CI self-check step | `.github/workflows/release-sigstore.yml` | workflow step (new) |
| R3 | Release asset upload (includes `.sig` + `cosign-public.pem`) | `.github/workflows/release-sigstore.yml` | workflow step (modified) |
| R4 | Public key (committed) | `cosign-public.pem` | new file |
| R5 | Customer verification helper | `tools/verify_cosign.sh` | new file |
| R6 | Key protection / rotation / recovery doc | `docs/…/TASK_MEE_029/G2_KEY_PROTECTION.md` | new doc |
| R7 | CHANGELOG entry (customer-facing) | `CHANGELOG.md` | new section |
| R8 | Keyless Sigstore path (must be **unchanged**) | `.github/workflows/release-sigstore.yml` | existing (verify no modification) |
| R9 | CI pipeline verification evidence | `G2_COMPLETION_EVIDENCE.md` §7 | evidence |
| R10 | Temporary probe step (must be **removed** before G4) | `.github/workflows/release-sigstore.yml` | cleanup check |

### 1.2 What NOT to review (out of scope)

- MEE_030 (GitHub mirror) — independent workstream
- MEE_025_A (signing POC) — already closed G5
- Python package internals (`mee/`) — no changes in this task
- Build system (`pyproject.toml`, `setup.py`) — no changes in this task

### 1.3 Review method

1. Read each file in the scope table.
2. For R1/R2/R8: verify the additive-only nature — the keyless Sigstore steps (sign + verify) must be byte-for-byte unchanged in their logic (only `continue-on-error: true` and a comment may have been added).
3. For R4: verify the public key is a valid ECDSA P-256 (SPKI) key.
4. For R5: verify the helper script is correct, handles errors, and does not leak secrets.
5. For R6: verify rotation and recovery procedures are complete and actionable.
6. For R9: verify the CI evidence is consistent (task 38, 5× "Verified OK", 9 assets).
7. For R10: verify the temporary COSIGN_PROBE step is still present (it should be — removal is a G4 prerequisite, not a G3 requirement, but flag it).

---

## 2. Key Technical Facts (for reviewer reference)

### 2.1 Signing method

- **Algorithm:** ECDSA P-256 (prime256v1) with SHA-256
- **Tool:** `openssl dgst -sha256 -sign/-verify` (no `cosign` CLI, no Rekor, no network)
- **Key format:** SEC1 EC private key (227 bytes) in Forgejo secret `COSIGN_PRIVATE_KEY`
- **Public key format:** SPKI (SubjectPublicKeyInfo) PEM — standard `-----BEGIN PUBLIC KEY-----`

### 2.2 Public key

```
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEz/Kiuzp1SNB7WqArYQ+2UteNs6An
06USBH6AZn3jOsXa60/bAbrEDctEeHzUWAljRe/fhhAcHBt8u4f95oo2kg==
-----END PUBLIC KEY-----
```

| Property | Value |
|----------|-------|
| Key type | EC P-256 (prime256v1), 256-bit |
| SPKI DER sha256 | `5e1282a5a490dec413e3e86bf65e950cedfbf7d86e584e0edad2e7fd76518ccc` |
| Raw PEM file sha256 | `a1d2cdf68302839b6643331c2170c3a7c2cefb6b0985d3532aa5f4edf1f0bfbf` |
| Generated | 2026-10-26 (PDT) |
| Location | `cosign-public.pem` (repo root) + release assets |

> **Note:** The G2 evidence and CHANGELOG reference the **raw PEM file** sha256 (`a1d2cdf6…`) as the "fingerprint." The **cryptographic key fingerprint** (SPKI DER sha256) is `5e1282a5…`. Both are valid identifiers; the reviewer should confirm which one is used consistently. This is a **documentation inaccuracy** (not a security defect) — see Finding F1 below.

### 2.3 Private key storage

- **Location:** Forgejo secret `COSIGN_PRIVATE_KEY` (repository-level)
- **Format:** SEC1 EC PRIVATE KEY PEM (227 bytes, 5 lines)
- **Never committed:** verified — `cosign-private.pem` does not exist in the repository
- **CI materialization:** `mktemp` → `chmod 600` → `trap 'rm -f "$KEYFILE"' EXIT`
- **PEM auto-wrapping:** if the secret value is raw base64 (no `BEGIN`/`END` headers), the workflow wraps it before use

### 2.4 CI pipeline (task 38, 2026-10-27T14:41Z)

```
🚀  Start image=node:22-bookworm
  ✅ apt-get install python3-pip python3-venv
  ✅ python3 -m venv /opt/venv
  ✅ pip install build sigstore
  ✅ Build: multimodal_emotion_engine-0.4.5-py3-none-any.whl + .tar.gz
  ✅ Cosign sign: 4 artifacts signed (manifest, hashes, wheel, sdist)
  ✅ Cosign verify: 5× "Verified OK" → "All Cosign (Option B) verifications PASSED"
  ⚠️  Sigstore keyless: skipped (continue-on-error, no OIDC on Forgejo)
  ✅ Release created: ID 21, tag v0.4.5
  ✅ Assets uploaded: 9 files
🏁  Job succeeded
```

### 2.5 Commit range (MEE_029)

| Commit | Description |
|--------|-------------|
| `9f05231` | G2: Option B signing path — additive, validated |
| `287f938` | MEE_026_B closure (context) |
| `28bf043`–`d625c8b` | CI debug iterations (Python env, YAML schema, Sigstore) |
| `2b79a71` | venv fix (PEP 668) |
| `3837229` | Sigstore non-fatal + FORGEJO_TOKEN |
| `ff32938` | YAML comment removal (Forgejo schema) |
| `9e8a831` | Hardcode API URL (no `server.url` context) |
| `d4d4729` | Asset upload endpoint fix |
| `bcc6cff` | Release ID parsing (python3) + upload endpoint |
| `25f4ff1` | CI verified + MEE_030 decisions + cosign-probe removal |
| `3167c48` | GATE_STATUS update + probe tag cleanup |

---

## 3. Review Checklist

### 3.1 Security

| # | Check | Criteria | Status |
|---|-------|----------|--------|
| S1 | Private key never in repository | `cosign-private.pem` absent from git history; only `cosign-public.pem` committed | ⬜ |
| S2 | Private key never echoed in logs | Workflow uses `[ -n "$COSIGN_PRIVATE_KEY" ]` check, never `echo` the value | ⬜ |
| S3 | Private key temp file cleanup | `mktemp` + `chmod 600` + `trap 'rm -f' EXIT` | ⬜ |
| S4 | No `admin` scope token | Workflow uses `FORGEJO_TOKEN` (repo-scoped) or `COSIGN_PRIVATE_KEY` (secret) — no admin token | ⬜ |
| S5 | Keyless path not weakened | `id-token: write` permission retained; keyless steps only gained `continue-on-error` | ⬜ |
| S6 | Customer helper no secret access | `tools/verify_cosign.sh` uses only public key + openssl — no secrets, no network | ⬜ |

### 3.2 Correctness

| # | Check | Criteria | Status |
|---|-------|----------|--------|
| C1 | Additive-only nature | Keyless Sigstore sign + verify steps: logic unchanged (only `continue-on-error` + comment added) | ⬜ |
| C2 | Signing covers all artifacts | wheel, sdist, `MEE_RELEASE_MANIFEST.json`, `MEE_INTEGRITY_HASHES.txt` all signed | ⬜ |
| C3 | Verification covers all artifacts | Same 4 artifacts verified in CI self-check step | ⬜ |
| C4 | Public key matches private key | `openssl ec -in <private> -pubout \| diff - cosign-public.pem` → no output (verified in G2 §2.1) | ⬜ |
| C5 | Customer helper exit codes | 0=PASS, 1=FAIL, 2=ERROR — correct and documented | ⬜ |
| C6 | Tamper detection | G2 §2.2: 1-byte modification → "Verification failure" (exit 1) | ⬜ |
| C7 | Release assets complete | 9 files: wheel, sdist, 2× .sig, manifest, hashes, 2× manifest/hashes .sig, cosign-public.pem | ⬜ |

### 3.3 Robustness

| # | Check | Criteria | Status |
|---|-------|----------|--------|
| R1 | Secret absent → fail-fast | `[ -n "${COSIGN_PRIVATE_KEY:-}" ] \|\| { echo "ERROR: …"; exit 1; }` — no silent skip | ⬜ |
| R2 | PEM auto-wrapping | Raw base64 secret → wrapped with `BEGIN/END EC PRIVATE KEY` headers | ⬜ |
| R3 | Release already exists → idempotent | 422 on create → lookup existing release by tag name → upload to it | ⬜ |
| R4 | Upload failure → non-fatal | `curl … \|\| echo "UPLOAD FAILED: $name"` — does not block the job | ⬜ |
| R5 | Sigstore keyless failure → non-fatal | `continue-on-error: true` on both keyless sign and verify steps | ⬜ |
| R6 | Python env in CI | `apt-get install python3-pip python3-venv` + `python3 -m venv /opt/venv` (PEP 668 compliant) | ⬜ |

### 3.4 Documentation

| # | Check | Criteria | Status |
|---|-------|----------|--------|
| D1 | Key protection doc complete | Rotation (§5), recovery (§6), supply-chain analysis (§7) all present | ⬜ |
| D2 | CHANGELOG customer-facing | Explains what changed, customer action (none), new files | ⬜ |
| D3 | G2 evidence consistent | AC table, CI verification §7, file list all consistent | ⬜ |
| D4 | Fingerprint consistency | G2 evidence + CHANGELOG + key-protection doc use the same fingerprint (see Finding F1) | ⬜ |

### 3.5 Cleanup

| # | Check | Criteria | Status |
|---|-------|----------|--------|
| CL1 | COSIGN_PROBE step | Still present in workflow (temporary — must be removed before G4) | ⬜ |
| CL2 | cosign-probe.yml | Removed (verified: file absent) | ⬜ |
| CL3 | Probe tags | `v0.0.0-probe-task-mee-029*` deleted from Forgejo (verified: 7 tags removed) | ⬜ |
| CL4 | No temp files in repo | No `cosign-private.pem`, no test files, no probe artifacts | ⬜ |

---

## 4. Known Findings (pre-identified for reviewer)

### F1: Fingerprint documentation inconsistency

**Severity:** LOW (documentation accuracy, not security)

**Issue:** The G2 evidence, CHANGELOG, and key-protection doc reference `sha256 a1d2cdf6…` as the "public key fingerprint." This is the **raw PEM file** sha256, not the **cryptographic key fingerprint** (SPKI DER sha256 = `5e1282a5…`).

**Impact:** A customer trying to verify the key by fingerprint would get a mismatch if they compute the SPKI DER sha256 (the standard method). No security impact — the key is still valid and verifiable — but the documentation should use the correct fingerprint or explicitly state "PEM file hash."

**Recommendation:** Update all three documents to use the SPKI DER sha256 (`5e1282a5…`) as the primary fingerprint, with the PEM file hash as a secondary identifier.

### F2: COSIGN_PROBE step still present

**Severity:** MEDIUM (cleanup before G4)

**Issue:** The temporary `COSIGN_PROBE (temporary, remove after test)` step is still in `release-sigstore.yml`. It runs `if: always()` and echoes whether the secret is present. While it does not leak the key value, it does confirm to any log reader that the secret exists.

**Impact:** Low security risk (the secret's existence is not secret information), but it violates the "no temporary code in production" principle. Must be removed before G4.

**Recommendation:** Remove the COSIGN_PROBE step. The CI self-check step ("Verify Cosign signatures") already proves the secret works.

### F3: Upload failure is silent

**Severity:** LOW (robustness)

**Issue:** The asset upload function uses `|| echo "UPLOAD FAILED: $name"` — if the upload fails, the job still succeeds. The release is created but may have missing assets.

**Impact:** A release with missing signatures would fail customer verification. However, the CI self-check step (which runs before the release step) already verified all signatures — so if signing succeeded, the artifacts are present and the upload is the only failure point.

**Recommendation:** Consider making the first two uploads (wheel + sdist) fatal, with the remaining 7 as non-fatal. Or add a post-upload verification step that checks the asset count via API.

### F4: Hardcoded Forgejo URL

**Severity:** LOW (portability)

**Issue:** The release step hardcodes `https://forge.deepsim.ai:8443` and `deepsim/multimodal-emotion-engine`. If the repository is mirrored (MEE_030), the workflow would need to be adapted.

**Impact:** None for the current single-repo setup. MEE_030 (mirror) is a separate task and does not modify this workflow.

**Recommendation:** No action needed for MEE_029. Note for MEE_030: the GitHub mirror will need a separate release workflow or the Forgejo one will be the canonical release path.

---

## 5. Reviewer Instructions

1. **Read all files** in the scope table (§1.1) before making findings.
2. **Verify the additive-only nature** (§3.2 C1) — this is the highest-priority check. If the keyless Sigstore path was modified in any way beyond `continue-on-error` + comment, flag as **HIGH**.
3. **Verify the public key** (§3.2 C4) — the key pair match was verified in G2 §2.1. Confirm the committed `cosign-public.pem` matches.
4. **Verify the CI evidence** (§3.4 D3) — task 38 log shows 5× "Verified OK" + "All Cosign (Option B) verifications PASSED." Confirm this is consistent with the G2 evidence §7.
5. **Check for the findings** in §4 — confirm or refute each. Add any new findings.
6. **Write your REVIEW_REPORT.md** to `docs/development/reports/TASK_MEE_029/REVIEW_REPORT.md` with:
   - Overall verdict: **APPROVE** / **APPROVE WITH CONDITIONS** / **REJECT**
   - Finding-by-finding analysis (confirm/refute §4 findings, add new ones)
   - Checklist completion (§3)
   - Conditions for approval (if any)

---

## 6. File Map (quick reference)

```
.github/workflows/release-sigstore.yml    # Main workflow (R1, R2, R3, R8, R10)
cosign-public.pem                         # Public key (R4)
tools/verify_cosign.sh                    # Customer helper (R5)
CHANGELOG.md                              # Customer-facing changelog (R7)
docs/development/reports/TASK_MEE_029/
  G2_COMPLETION_EVIDENCE.md               # G2 evidence incl. CI verification §7 (R9)
  G2_KEY_PROTECTION.md                    # Key protection / rotation / recovery (R6)
  GATE_STATUS.md                          # Gate status (reference)
  G2_BLOCKER_EVIDENCE.md                  # Option A blocker (context)
  G0_INTAKE_CHECKLIST.md                  # Intake (reference)
  G1_PLAN/CTO_TASK_PLAN.md                # CTO plan (reference)
  LOCK.md                                 # Task lock (reference)
  RELEASED.md                             # Release state (reference)
```

---

*End of G3 review package. Reviewer: verify all findings, write REVIEW_REPORT.md.*
