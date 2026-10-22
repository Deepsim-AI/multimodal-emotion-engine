# TASK_REQUEST — TASK_MEE_020: MEE License Hardening & Signed Distribution

**Task ID (proposed, pending registry confirmation):** TASK_MEE_020
**Gate:** G0 — PM Intake (DRAFT, prepared by Implementer for PM/owner signature)
**Phase:** Post-019 licensing hardening (commercial enforcement)
**Date:** 2026-10-22
**Requested By:** Gateway Owner (Shouke Wei)
**Depends On:** TASK_MEE_015 (License Integration, CLOSED), TASK_MEE_019 (License UI, CLOSED)

> ⚠️ **Goverance note (Rule 9):** This G0 intake was *drafted* by the Implementer
> (G2) at the owner's request. It must be **reviewed, signed, and submitted by the
> PM (gateway-owner)** before handoff to CTO (G1). No implementation, code change,
> or gate bypass has occurred in this step.

---

## 1. Problem Statement

The TASK_MEE_019 licensing assessment surfaced two **client-side** weaknesses:

1. **Patchable enforcement gate.** The license check is a single Python method call —
   `EmotionEngine._license_check()` at the top of `process()` (`mee/api/engine.py:244`).
   It can be bypassed by monkey-patching (e.g. `EmotionEngine._license_check = lambda: None`)
   or by stubbing `mee.licensing.client`. This makes the gate a *compliance* control, not
   an *anti-piracy* barrier. (Verified empirically 2026-10-22.)
2. **No signed distribution / integrity.** Release artifacts (wheel / source) are not
   signed, and there is no mechanism for customers or the pipeline to verify artifact
   authenticity, nor any installed-package integrity check to detect post-install
   modification of critical files.

**Reality constraint (must be stated up front):** a locally installed Python application
cannot be made fully tamper-proof. The goal is to **raise the cost and detectability** of
unauthorized modification and to make **provenance verifiable**, not to achieve
unbreakable DRM.

**Explicitly OUT of scope (separate remediation):** the Keygate server-side secret-storage
issue — `RELEASE_KEY_ENCRYPTION_KEY` unset on the VPS (license keys at rest are plaintext).
That is a **separate security task** and this task does **not** resolve or depend on it.

---

## 2. Scope (5 workstreams)

### 2.1 Signed distribution & provenance
- Evaluate signing release artifacts (wheel/sdist) with verifiable signatures.
  Options to assess: **Sigstore/fulcio (keyless, OIDC)** vs. **GPG/age detached
  signatures** vs. PyPA **`sigstore-python`** + `store`/`verify` workflow.
- Define verifiable checksums (SHA-256) + signature publishing in the release pipeline.
- Provide a `verify` path for customers and CI:
  `pip download` → verify signature → verify wheel hash before install.
- Compatibility check against the existing packaging workflow
  (`pyproject.toml`, any CI in `docs/`/`.github`), and cross-platform
  (Jetson aarch64 + x86_64) install paths.

### 2.2 Licensing enforcement hardening (assessment — NOT a pre-decided choice)
- **Assess** compiling the licensing enforcement boundary + a minimal critical shim with
  **Cython** (or an equivalent C extension) so the gate is not a patchable Python call.
- **Assess alternatives** and their trade-offs:
  - Cython/AOT-compiled gate (+ small inference shim)
  - PyArmor / pyoxipin commercial obfuscation (license-protected bytecode)
  - PyArmor-rundir / license-protected interpreter
  - Bytecode-only hardening (hash self-check + import hooks) — cheapest, weakest
  - Native extension via `cffi`/`ctypes` holding the verify+gate coupling
- For each: maintenance cost, cross-platform packaging (manylinux + Jetson aarch64),
  bypass-resistance, and interaction with the existing `verify()`/`activate()` flow.
- **Deliverable is a recommendation + CTO decision record, not code.** Cython is **not**
  mandated before this assessment and the CTO (G1) decision.

### 2.3 Installed-package integrity
- Evaluate a **signed manifest** (or equivalent) to detect modification of critical
  installed files (e.g. `mee/api/engine.py`, `mee/licensing/*`, the compiled shim if
  2.2 proceeds).
- **Constraint:** do **not** rely solely on an expected digest stored *beside* the code it
  protects (attacker deletes the digest too). Preferred: a digest anchored **outside** the
  protected code — e.g. signed at release time and carried in the wheel metadata / a
  separate signed sidecar / the Keygate-issued token or a release manifest the verifier
  fetches/holds independently.
- Decide the integrity-check enforcement point and failure behavior (must **fail safe** —
  block inference — never silently allow).

### 2.4 Offline licensing guarantees
- Document signed-token expiration (`exp` check-in window in `offline.py:is_within_ttl`)
  and offline operation behavior.
- **Test** the distinction between:
  (a) **connectivity failure** (network down, valid license) → should still work offline;
  (b) **expired / revoked / invalid** license → must hard-stop.
- Preserve reasonable offline operation for Jetson / field deployments (document the
  offline grace window explicitly; confirm it is long enough for real field use).
- This workstream is **documentation + test** of existing behavior; it must not weaken
  verification.

### 2.5 Privacy
- Preserve the existing **explicit** licensing-network-operation model
  (network calls only on activate/verify/deactivate — no phone-home, no implicit telemetry).
- **No** hidden telemetry, no unrelated data collection, no new analytics.
- Produce a short "network operations & privacy" statement for customers.

---

## 3. Non-Goals

- **Not** promising complete anti-tamper protection (explicitly out of scope to guarantee).
- **Not** TPM / Secure-Enclave dependency or hardware binding (only if assessment shows a
  clear need — it likely does not, and the owner has directed to avoid it).
- **Not** aggressive obfuscation as a default (evaluate, but do not force).
- **Not** modifying production deployments during G0/G1 (design + assessment only until G2).
- **Not** resolving the Keygate `RELEASE_KEY_ENCRYPTION_KEY` server-side secret-storage issue
  (separate security remediation + verification task).
- **Not** changing the public licensing API / `LicenseClient` contract unless a separately
  approved change is required.

---

## 4. Constraints (binding)

| # | Constraint |
|---|-----------|
| C1 | Preserve the existing licensing contract and public API unless a separately approved change is necessary. |
| C2 | Do **not** weaken license verification or silently allow inference when enforcement fails. All hardening must **fail safe** (block, never bypass-on-error). |
| C3 | Do **not** promise complete anti-tamper protection; scope = raise cost/detectability + verifiable provenance. |
| C4 | Avoid aggressive obfuscation, TPM, or hardware binding unless the assessment demonstrates clear need. |
| C5 | Do not modify production deployments during G0. |
| C6 | Keep the Keygate `RELEASE_KEY_ENCRYPTION_KEY` secret-storage issue **separate**; this task does not resolve it. |
| C7 | No hidden telemetry or unrelated data collection. |
| C8 | Preserve reasonable offline operation for Jetson / field deployments. |
| C9 | Integrity must not rely solely on a digest stored beside the protected code. |

---

## 5. Measurable Acceptance Criteria (draft — CTO to refine in G1)

| # | AC | How verified |
|---|----|--------------|
| AC1 | A signed wheel is produced by the release pipeline with a **verifiable** signature (Sigstore or GPG/age) that a clean environment can verify before install. | `pip download` + `sigstore verify` / `gpg --verify` in a fresh container; CI check. |
| AC2 | A customer can verify artifact authenticity (signature) **and** integrity (SHA-256) and is told pass/fail unambiguously. | Documented + scripted `mee-verify-release <wheel>` (or `pip` hook) returns clear PASS/FAIL. |
| AC3 | The licensing gate is no longer a single patchable Python call **if** the CTO approves compiled enforcement; otherwise the chosen alternative's bypass cost is documented and its fail-safe behavior proven. | G1 decision record + bypass test (monkey-patch `process`/gate) shows inference is blocked or the residual risk is explicitly documented. |
| AC4 | Integrity check detects modification of a critical installed file and **blocks inference (fails safe)**; it does **not** rely solely on a beside-code digest. | Mutation test: edit `mee/api/engine.py` (or compiled shim) post-install → `process()` raises / is blocked; digest-only-beside-code is rejected as the sole mechanism. |
| AC5 | Offline behavior: valid license + network-down → **works**; expired/revoked/invalid → **hard-stop**. Documented offline grace window. | Tests with network disabled (or mocked) for all four cases; `docs/licensing/offline.md` states the grace window. |
| AC6 | No new network calls, telemetry, or data collection are introduced; a "network operations & privacy" statement exists. | Code review (no new outbound calls outside activate/verify/deactivate) + `docs/licensing/privacy.md`. |
| AC7 | `RELEASE_KEY_ENCRYPTION_KEY` server-side issue is **not** claimed resolved; it is listed as a separate open item. | G1/G2 records reference it as out-of-scope; no code/config change to it in this task. |
| AC8 | Existing public licensing API and `LicenseClient` behavior are unchanged (or change is separately approved). | API diff + existing `tests/test_licensing_*` suite green. |

---

## 6. Threat-Model Summary

| Threat | Current state | Proposed control | Residual risk |
|--------|--------------|------------------|---------------|
| Bypass license gate (monkey-patch `process`/`_license_check`) | **Trivial** — one Python call | Compiled gate + shim (if approved) / integrity self-check | Compiled raises cost; a determined actor with the source or runtime can still patch. **Not eliminated.** |
| Ship a "modified" MEE wheel to a customer | No detection | Signed artifacts + customer verify path | Customer can choose to ignore verification (policy, not crypto). |
| Post-install tamper of critical files | No detection | Signed manifest / anchored digest + fail-safe gate | Digest must be anchored outside the protected code (C9). |
| Forge a license / offline token | Ed25519 signed token, key not shipped | (unchanged) | Private key compromise on Keygate server (server-side, out of scope). |
| Re-use a license across devices beyond plan limit | Keygate activation limits | (unchanged, server-side) | Server-side enforcement; client is advisory. |
| Collect customer data without consent | None collected | Privacy statement + no-telemetry rule (C7) | None expected. |
| **Will NOT protect against:** a customer who owns the source or runs in an instrumented runtime and deliberately disables licensing; a compromised Keygate server; a user ignoring signed-artifact verification. |

**Honest framing:** the proposed controls make **unauthorized modification more detectable and
more costly** and make **provenance verifiable**. They do **not** make a local Python app
tamper-proof, and they do not stop a party who controls the host runtime or the source.

---

## 7. Feasible-Options Comparison (for CTO decision in G1)

### 7.1 Signed distribution
| Option | Pro | Con | Maintenance |
|--------|-----|-----|-------------|
| **Sigstore (fulcio, keyless, OIDC)** | No long-lived signing key to manage; industry-standard provenance; `sigstore-python` verify | Needs CI OIDC identity (GitHub Actions); slightly newer tooling | Low (no key custody) |
| **GPG/age detached sig + published SHA-256** | Familiar; works offline with a distributed public key | Long-lived key custody/rotation; key-leak risk | Medium (key management) |
| **PyPA `store`/`verify`** | Pythonic; pairs with Sigstore | Less widely known; smaller ecosystem | Low |

### 7.2 Enforcement hardening
| Option | Bypass resistance | Maintenance | Cross-platform (x86_64 + Jetson aarch64) | Notes |
|--------|-------------------|-------------|------------------------------------------|-------|
| **Cython-compiled gate + minimal shim** | Medium-High (not a Python call) | Medium (build step, ABI, `manylinux` + aarch64 wheels) | Needs per-arch wheels or in-tree build | Most defensible "raise the bar" |
| **PyArmor / pyoxipin (bytecode obfuscation)** | Medium | Low-Med (vendored tool) | Runs on any CPython; license cost | Fast to ship; reversible with effort |
| **PyArmor-rundir / protected interpreter** | Medium | Higher (custom interpreter distro) | Heavy distro to maintain | Heavier than needed |
| **Bytecode hash self-check + import hooks** | Low-Medium | Low | Any CPython | Cheapest; weakest; pairs with manifest |
| **`cffi`/`ctypes` native verify+gate** | Medium | Medium (C build, per-arch) | Needs per-arch build | Similar to Cython, more C |

### 7.3 Integrity anchoring
| Mechanism | Resists beside-code deletion? | Notes |
|-----------|------------------------------|-------|
| Digest **beside** code | ❌ No (attacker deletes it) | **Rejected as sole mechanism (C9)** |
| **Signed release manifest** (fetch/hold independently) | ✅ Yes | Preferred; verifier holds it outside the wheel |
| Digest embedded in **wheel metadata / signed sidecar** | ✅ Yes (independent of the .py) | Good; verify at install + runtime |
| Keygate token carrying an attested build digest | ✅ Yes (server-anchored) | Couples to server; nice-to-have |

---

## 8. Explicit CTO Decision Points (G1)

1. **Is compiled enforcement warranted?** (Cython gate + shim vs. obfuscation vs. bytecode
   self-check vs. native `cffi`). Choose one; record rationale + residual risk.
2. **Signing scheme:** Sigstore (keyless) vs. GPG/age. Choose one; define key/custody model.
3. **Integrity anchoring:** signed release manifest vs. wheel-metadata digest vs. Keygate-anchored
   digest. Choose one (must satisfy C9).
4. **Integrity enforcement point + failure behavior:** confirm fail-safe (block inference).
5. **Offline grace window:** confirm/document the signed-token `exp` value is adequate for field use.
6. **Scope guardrail:** confirm `RELEASE_KEY_ENCRYPTION_KEY` server-side issue stays a separate task (C6).

---

## 9. Dependencies

| Dependency | Status |
|-----------|--------|
| TASK_MEE_015 (License Integration) | ✅ CLOSED |
| TASK_MEE_019 (License UI) | ✅ CLOSED |
| Existing packaging (`pyproject.toml`) | ✅ present (unchanged unless G1 approves) |
| Release pipeline / CI | ✅ present (to be extended with signing, if G1 approves) |
| Keygate server (activate/verify/deactivate) | ✅ live |
| Keygate `RELEASE_KEY_ENCRYPTION_KEY` | ⚠️ **OUT OF SCOPE — separate task (C6)** |

---

## 10. Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Over-engineering / false sense of security | Medium | Explicit "not tamper-proof" framing (C3); threat model in §6 |
| Cross-platform packaging burden (Jetson aarch64) | Medium | Decide in G1; prefer options with existing wheel paths; avoid heavy distros |
| Maintenance cost of a signing key (if GPG) | Medium | Prefer keyless Sigstore (decision point 2) |
| Integrity check produces false positives on legit updates | Low-Med | Anchor digest to release version; document update flow |
| Scope creep into server-side secret storage | Medium | Hard constraint C6; separate task |
| Customer friction from verify step | Low | Make verify optional-but-recommended; document clearly |

---

## 11. Handoff

**Status:** G0 intake **drafted**. Awaiting PM (gateway-owner) review + signature, then handoff to **CTO (G1)** for architecture review + the six decision points in §8.

**No implementation, code modification, or gate bypass has occurred.** G0/G1/G2 gates must proceed normally.

---

*Registry note for the PM: `TASK_MEE_001/TASK_REGISTRY.md` is stale (ends at 011). Confirmed from
the filesystem that 016/017/018/019/035 are in use and **no `02x` IDs exist**, so `TASK_MEE_020` is
the correct next ID. Recommend the PM also refresh the registry table rows for 012–035 as part of
G0 housekeeping.*
