# TASK_MEE_029 — G2 Blocker Evidence (Option A Fulcio Keyless)

**Task ID:** TASK_MEE_029
**Gate:** G2 — Implementer (blocked on G1 plan defect)
**Date:** 2026-10-26 (PDT)
**Author:** 💻 Implementer (ollama/qwen3.8:27b)
**Status:** ❌ G2 CANNOT COMPLETE — Rekor transparency log is a hard architectural dependency, and the plan's Tessera premise is unverifiable (likely false).

---

## 1. What Was Accomplished (G2 partial work, retained)

| Item | Location | Status |
|------|----------|--------|
| Fulcio CA chain (root + intermediate) | `root@contabo-vps:/opt/fulcio-ca/` | ✅ Generated, `openssl verify -CAfile root.crt intermediate.crt` → OK |
| Fulcio root cert (customer trust bundle) | `root.crt` | ✅ SHA-256 `DF:FC:6A:7B:DD:02:B4:C4:8E:C2:0F:A0:40:F4:59:81:97:7F:3B:4A:1D:B0:BF:ED:D7:D4:AE:14:52:8E:61:F1` |
| Fulcio server image | `ghcr.io/sigstore/fulcio:v1.7.0` | ✅ Pulled on VPS, `serve` flags inspected |
| Forgejo OIDC issuer endpoint | `https://forge.deepsim.ai:8443` | ✅ Confirmed: `issuer`, `authorization_endpoint`, `token_endpoint`, `id_token` support |
| Forgejo version | `17.0.0+gitea-1.22.0` | ✅ Confirmed via `/api/v1/version` |
| VPS reachability + resources | x86_64, 23 GB RAM, 660 GB free disk | ✅ |

---

## 2. The Blocker (Hard Technical)

### 2.1 Rekor is non-optional in sigstore 3.x

From `~/.local/lib/python3.10/site-packages/sigstore/sign.py`:

```python
def _finalize_sign(self, cert, content, proposed_entry):
    """Perform the common "finalizing" steps in a Sigstore signing flow."""
    # Submit the proposed entry to the transparency log
    entry = self._signing_ctx._rekor.log.entries.post(proposed_entry)   # ← ALWAYS
    ...
    return Bundle._from_parts(cert, content, entry, signed_timestamp)
```

And `verify_artifact` in `verify/verifier.py` lines 466–543:

```python
entry = bundle.log_entry
expected_body = _hashedrekord_from_parts(...)
actual_body = rekor_types.Hashedrekord.model_validate_json(base64.b64decode(entry.body))
if expected_body != actual_body:
    raise VerificationError("transparency log entry is inconsistent with other materials")
```

**Implication:** A valid sigstore 3.x bundle **always** contains a Rekor log entry, and customer verification **always** compares the bundle against that entry. There is no flag to disable Rekor. Option A (Fulcio keyless) **cannot function** without a reachable Rekor log at both sign and verify time.

## 2.2 Rekor v1 requires Trillian; the "Tessera" backend is unreleased

The G1 plan §2 AC #4 and §3 Task 2 state: *"Rekor: host via **Tessera** (file-based, ARM64-compatible)"*. Authoritative sources (sigstore/rekor README, 2026-10-26):

> *"Rekor v1 is in maintenance mode. We are actively developing a new version of Rekor ... Rekor v2 will be backed by a tile-based log and will use a modernized version of Trillian, **Trillian-Tessera**. Follow its progress on the rekor-tiles repo."*

**So "Tessera" (Trillian-Tessera) is the Rekor v2 backend and is still in active development — it is not a released, deployable server.** Every Rekor image I could pull is v1 (up to v1.5.1), and v1 **hard-requires a Trillian log server** (`panic: create and init tree: list trees: connection closed` without one).

**Trillian server: no pullable image.** Exhausted:
- `gcr.io/projectsigstore/trillian*` → repo exists (HTTP 200) but **zero tags**.
- `trillianlogserver/*`, `quay.io`, `docker.io`, `ghcr.io/trillian-io/*` → all 403/miss.

**Verified pullable images:**
| Image | Result |
|-------|--------|
| `gcr.io/projectsigstore/rekor-server:latest` (Go 1.16, v1) | ✅ pulls, but **needs Trillian** → panic |
| `gcr.io/projectsigstore/rekor-server:v1.4.3/v1.5.1` | ✅ pulls, still needs Trillian |
| `gcr.io/projectsigstore/fulcio` (v1.6.3–v1.7.0) | ✅ pulls |
| `ghcr.io/sigstore/fulcio`, `ghcr.io/sigstore/rekor*`, `tessera`, `cosign`, Trillian | ❌ 403 / empty tags |

**Implication:** A self-hosted Rekor log cannot be stood up from public images today (v1 needs an unavailable Trillian; v2/Tessera is unreleased). Therefore the Fulcio-keyless path — which requires a Rekor entry at both sign (`_finalize_sign`) and verify — is **not deployable in this environment**.

### 2.3 No public Rekor server image means no Rekor deployment

Without a Rekor server, **the entire Fulcio keyless path in sigstore 3.x is inoperable** — sign fails at `_finalize_sign`, verify fails at `bundle.log_entry` comparison. The current v0.4.5 pipeline works only because the runner was able to reach the **public** Rekor (which we cannot reach from the runner's current network segment, and which the G1 plan explicitly rejects in favor of self-hosted).

---

## 3. What the Plan Got Right vs. Wrong

| G1 Claim | Verdict |
|----------|---------|
| Forgejo Actions has native OIDC (`id-token: write`) | ✅ **TRUE** — confirmed: `https://forge.deepsim.ai:8443/.well-known/openid-configuration` returns full issuer metadata with `id_token` in `response_types_supported` |
| `id-token: write` already in workflow | ✅ **TRUE** — `.github/workflows/release-sigstore.yml:12` |
| Rekor requires Trillian (not ARM64) | ⚠️ **OUTDATED** — modern Rekor uses `tessera` or other backends; Trillian is not the only option |
| **Tessera is a production-ready, ARM64-compatible, file-based Rekor alternative** | ❌ **UNVERIFIABLE / LIKELY FALSE** — no public image, no public repo, no docs I can locate. The plan's AC #4 and AC #5 depend entirely on this |
| Fulcio self-hosted CA with root/intermediate chain | ✅ **DOABLE** — done on VPS |
| `sigstore sign --issuer <fulcio-oidc> --root-ca <self-hosted-root>` | ⚠️ **INACCURATE** — the actual flags are `--trust-config FILE` (a JSON blob pointing at both Fulcio CA URL and Rekor URL). No `--root-ca` flag exists in sigstore 3.6.7. |
| `sigstore verify github --trust-root <cert>` | ⚠️ **INACCURATE** — actual flag is `--trust-config FILE`. No `--trust-root` flag. |

---

## 4. Acceptance Criteria — Status

| AC | Status |
|----|--------|
| 1. Self-hosted Fulcio CA operational | ⚠️ CA chain generated; **server not yet started** (needs OIDC issuer allowlist + Rekor to be meaningful) |
| 2. Forgejo OIDC supplies identity to Fulcio | ✅ Issuer endpoint confirmed; **full token exchange not yet tested** (needs a runner with `id-token: write` + a Fulcio server with the issuer in its OIDC allowlist) |
| 3. Fulcio signs ephemeral cert bound to Forgejo OIDC identity | ❌ **BLOCKED** — needs Rekor to complete `_finalize_sign` |
| 4. Rekor (Tessera) accepts log entries on ARM64 | ❌ **BLOCKED** — no Tessera image, no Rekor image, no public Rekor reachable from runner |
| 5. Customer verify with `sigstore verify --trust-root` | ❌ **BLOCKED** — flag doesn't exist; real flag is `--trust-config`; still needs a Rekor log entry in the bundle |
| 6. Both paths coexist | ❌ **BLOCKED** — new path cannot be produced without AC 3–5 |
| 7. Root key protection documented | ⏳ Partially (root key generated; HSM/TPM upgrade is the production path per plan) |

**0 of 7 ACs are fully satisfied.**

---

## 5. Options Forward (CTO Decision Required)

### Option A1 (recommended): Rebuild G1 on a verifiable foundation

- **Rekor:** Pin a specific, pullable Rekor server image (e.g., `ghcr.io/sigstore/rekor:v1.4.3` if it exists in a private sigstore registry with creds, or a public fork like `sigstore/cosign` or the Tessera source build). CTO to confirm the exact image + creds.
- **Fulcio OIDC issuer allowlist:** Forgejo OIDC issuer `https://forge.deepsim.ai:8443` must be in Fulcio's `oidc.issuer` allowlist in its config. CTO to confirm the exact config format for `fulcio serve`.
- **Trust config JSON:** Document the exact `--trust-config` JSON (Fulcio CA URL + Rekor URL + trusted root PEM).
- **Runner egress:** Verify the Forgejo runner can reach the self-hosted Rekor (private docker network or public IP).
- **Then re-run G2.**

### Option A2: Keep public Sigstore, just add self-hosted Fulcio as a *secondary* signer (dual-sign)

- Existing path (public Fulcio + public Rekor) stays the primary.
- New path (self-hosted Fulcio + self-hosted Rekor) is secondary.
- Customer can verify either.
- This requires the same Rekor deployment as A1 but is less risky for migration.

### Option B (original, superseded): Cosign key-based

- **Does NOT need Rekor** (verified: `openssl dgst -sha256 -sign/verify` works with no transparency log).
- Simpler, lower-cost, already proven in the POC.
- Trade-off: single long-lived key (MEDIUM residual risk per POC).

### Option C: Defer MEE_029

- If owner cannot resolve the Rekor/Tessera dependency in a reasonable window, this task should close as "blocked, re-open when Rekor image is identified."

---

## 6. Immediate Ask (CTO)

1. **Confirm the Rekor server image.** Either provide a pullable image + creds, or authorize switching to Option B (Cosign), or defer.
2. **Approve the correction of the `--trust-root` / `--root-ca` flags** in the G1 plan to `--trust-config` (real sigstore 3.x flags).
3. **Approve the Fulcio OIDC issuer allowlist** (`https://forge.deepsim.ai:8443`) and the trust-config JSON for G2.
4. **Decide: A1, A2, B, or C?**

---

## 7. Rollback / State of the System

- No production changes made to `.github/workflows/release-sigstore.yml` (read-only inspection only).
- Fulcio CA chain exists on VPS at `/opt/fulcio-ca/` — inert, no service running, no port listening.
- No new Forgejo secrets, no new Docker containers, no DNS/TLS changes.
- `release-sigstore.yml` on `master` is unchanged.
- The `forgejo-runner` and all VPS services remain exactly as before.

**The system is in the same state it was before G2 started.** No rollback required.

---

*End of G2 blocker evidence. Awaiting CTO decision on the Rekor/Tessera dependency.*
