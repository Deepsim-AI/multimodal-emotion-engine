# THREAT_MODEL — TASK_MEE_020: MEE License Hardening & Signed Distribution

**Task ID:** TASK_MEE_020
**Gate:** G0 — companion to `TASK_REQUEST.md` (DRAFT, prepared by Implementer for PM/owner signature)
**Date:** 2026-10-22
**Companion to:** `TASK_REQUEST.md` §6 (threat-model summary) — this file is the expanded,
decision-grade version.

> **Purpose:** give the CTO (G1) a complete, honest picture of *what the proposed controls
> will and will not protect against*, and a per-control "bypass cost" analysis, so the
> six decision points in `TASK_REQUEST.md` §8 can be made with full information.
>
> **Honesty constraint (C3):** a locally installed Python application **cannot be made fully
> tamper-proof**. Nothing in this document should be read as promising that. The design goal is
> to **raise the cost and detectability** of unauthorized modification and to make **provenance
> verifiable** — not to achieve unbreakable DRM.

---

## 1. Threat Actor & Capability Model

We reason about distinct adversary classes so controls are matched to the threat, not to the
scariest hypothetical.

| Class | Capability | Intent | Realism for MEE |
|-------|-----------|--------|-----------------|
| **A1 — Casual end user** | Installs via `pip`/wheel; no reverse-engineering skill | Accidental misuse; not adversarial | Very high |
| **A2 — Skilled software dev / reverse engineer** | Reads Python source; can monkey-patch, recompile, use `frida`/`pyrasite`; has a dev box | Bypass license for personal/internal use; redistribute a "cracked" wheel | High |
| **A3 — Adversarial org (competitor / reseller)** | Team, tooling, time; can instrument runtimes, strip/patch binaries at scale, build a fake Keygate or MITM | Mass-piracy, resell cracked MEE, strip license from an embedded product | Medium |
| **A4 — Insider / supply-chain** | Access to source repo, CI, or the Keygate server; or compromises the signing path | Tamper source/CI, forge signatures, steal keys | Low (but high impact) |

**Design rule:** controls are chosen to be *proportionate* to A1–A3. We do **not** invest in
A4-grade (key-custody / HSM / hardware-rooted-TPM) controls unless the G1 assessment shows a
clear, demonstrated need (C4). A4 is handled by **operational** security (repo/CI/Keygate
hardening, separate task) not by client-side code.

---

## 2. Asset Inventory (what we are protecting)

| Asset | Where | Value if lost |
|-------|-------|---------------|
| **License enforcement gate** | `mee/api/engine.py` (`_license_check`, `process`) | Unauthorized free inference = lost revenue |
| **Licensing client logic** | `mee/licensing/client.py` (verify/activate/deactivate) | Bypass + license cloning |
| **Offline signed-token verifier** | `mee/licensing/offline.py` (ed25519 verify) | Offline-license forgery |
| **Device identity / state** | `~/.config/mee-licensing/licenses/` | Trial re-use, activation-limit bypass |
| **Release artifacts** | wheel/sdist from CI | Tampered / unprovenance MEE shipped to customers |
| **Provenance & authenticity** | signing + manifest | Customer trust; counterfeit distributions |
| **Customer privacy** | (absence of telemetry) | Trust / compliance |

**Not client-side assets (out of scope):** the Keygate **private** signing key (server-side),
the `RELEASE_KEY_ENCRYPTION_KEY` secret-storage concern (separate remediation task, C6).

---

## 3. Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│  UNTRUSTED  — customer host / runtime / filesystem           │
│                                                             │
│   ┌───────────────────────────────────────────────────┐     │
│   │  MEE installed package  (the protected surface)    │     │
│   │  · engine.py  · licensing/*  · offline.py          │     │
│   │  · compiled shim (if G1 approves)                  │     │
│   │  · signed release manifest / wheel metadata        │     │
│   └───────────────────────────────────────────────────┘     │
│            ▲  network (activate/verify/deactivate only)      │
└────────────┼────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────┐
│  TRUSTED (server-side, separate task)                        │
│   Keygate server — Ed25519 private key, license records,    │
│   activation limits, RELEASE_KEY_ENCRYPTION_KEY             │
└─────────────────────────────────────────────────────────────┘
```

**Key implication:** everything *inside the box* (left) is untrusted to an A2/A3 actor who
controls the host. Therefore **no client-side control is a hard barrier** — only *economic*
and *detection* barriers. The only cryptographically hard boundary is the **server-side
private key** (right), which an attacker cannot forge without a Keygate compromise (A4).

---

## 4. Threat Catalogue & Control Mapping

Each row: threat → current exposure → proposed control (from `TASK_REQUEST.md`) → **what it
actually stops** → **residual risk / bypass path**.

### 4.1 Bypass the license gate (inference without a license)

| ID | Threat | Current exposure | Proposed control | Stops | Residual / bypass |
|----|--------|------------------|------------------|-------|-------------------|
| T1 | Monkey-patch `EmotionEngine._license_check` / `process` | **Trivial** (verified: one Python call) | Compiled gate+shim (if G1 approves) / bytecode self-check | Raises cost from "one line" to "recompile + evade self-check" | A2/A3 with source or a runtime (`frida`) can still patch. **Not eliminated.** |
| T2 | Stub `mee.licensing.client` (`sys.modules` injection) | Trivial | Same as T1 | Same | Same |
| T3 | Edit `engine.py` on disk to delete the gate call | Trivial | Signed manifest / anchored digest + fail-safe gate | Detected at runtime → **block inference** | If integrity anchor is beside-code only, attacker deletes the digest too — **hence C9 (anchor outside the code).** |
| T4 | Run an instrumented/alternative CPython that skips the gate | Moderate | Compiled shim (native call harder to intercept) + self-check | Raises cost | A3 can instrument any binary. Not eliminated. |

**Honest verdict for T1–T4:** these controls **raise the cost and make tampering detectable
(blocking inference on detection)**. They do **not** stop a motivated A2/A3 actor who controls
the runtime. This is the fundamental limit of client-side licensing.

### 4.2 Ship / install a tampered or counterfeit MEE

| ID | Threat | Current exposure | Proposed control | Stops | Residual / bypass |
|----|--------|------------------|------------------|-------|-------------------|
| T5 | Customer installs a forged/modified wheel (phishing, bad mirror) | **No detection** | Signed artifact (Sigstore/GPG) + SHA-256 verify | Verifier detects mismatch → **fail** | A customer who *chooses not to verify* is unprotected (policy, not crypto). |
| T6 | CI/supply-chain ships a tampered wheel (A4) | No detection | Signing at release + customer verify | Detects if signature key is intact | If the signing key/path is compromised (A4), forged-but-valid signatures pass — handled by key custody (separate task), not here. |
| T7 | "Modified MEE" redistributed as a product (A3) | No detection | Signed manifest + provenance | Gives customers a way to detect non-genuine builds | Reseller can ship an *unverified* build and tell users to skip verify. Detection, not prevention. |

### 4.3 Offline license abuse

| ID | Threat | Current exposure | Proposed control | Stops | Residual / bypass |
|----|--------|------------------|------------------|-------|-------------------|
| T8 | Clone a valid offline signed token to another device beyond plan limits | Server-side activation limits are the real control; client is advisory | (unchanged) + documented offline grace | Clarifies behavior; does not add client enforcement | Server enforces the limit; a cloned token works offline until re-verify — server-side, out of client scope. |
| T9 | Confuse "network down" with "license invalid" (or vice versa) | Ambiguity possible | **Test** the 4-case matrix (valid+offline / expired / revoked / invalid) | Correct fail-safe behavior proven | N/A (behavioral, not adversarial) |
| T10 | Forge an offline token | Ed25519 private key is server-only; not shipped | (unchanged) | Cannot forge without Keygate private key (A4) | N/A for client; A4 only. |

### 4.4 Privacy / data

| ID | Threat | Current exposure | Proposed control | Stops | Residual |
|----|--------|------------------|------------------|-------|----------|
| T11 | Hidden telemetry / data collection introduced by hardening | None today (verified) | C7 no-telemetry rule + privacy statement + code review | Prevents regression | None expected if C7 enforced in G1/G2 review. |

### 4.5 Integrity of the protection itself

| ID | Threat | Current exposure | Proposed control | Stops | Residual |
|----|--------|------------------|------------------|-------|----------|
| T12 | Attacker deletes the integrity digest stored beside the code | (would be trivial) | **C9: anchor digest outside the protected code** (signed manifest / wheel metadata / Keygate-anchored) | Digest deletion does not defeat the check | If the *only* anchor is inside the wheel, a wheel-level repackage defeats it — prefer server/fetch-anchored manifest. |

---

## 5. What the Controls WILL Protect Against (capabilities gained)

1. **Verifiable provenance** — a clean environment can confirm a wheel is genuinely from the
   MEE release pipeline (signature + hash). *(T5, T6, T7 — detection.)*
2. **Tamper detection with fail-safe blocking** — modification of a critical installed file is
   detected and **inference is blocked**, not silently allowed. *(T3 — detection + denial.)*
3. **Higher bypass cost** — the gate is no longer a single patchable Python call (if G1
   approves compiled enforcement / self-check). *(T1–T4 — cost increase.)*
4. **Predictable offline behavior** — customers and field ops know exactly what "offline"
   means and that a downed network does not read as an expired license. *(T9.)*
5. **No privacy regression** — the hardening adds no telemetry / data collection. *(T11.)*

## 6. What the Controls WILL NOT Protect Against (explicit non-goals)

1. **A motivated A2/A3 actor who controls the host runtime or has the source** and chooses to
   defeat the gate. Client-side licensing has no hard barrier against this.
2. **A customer who declines to verify** a signed artifact — verification is only as strong
   as the customer's willingness to run it.
3. **A compromised signing key / CI / Keygate server (A4)** — that is operational security and
   a **separate task** (including the `RELEASE_KEY_ENCRYPTION_KEY` issue, C6).
4. **Offline license cloning beyond plan activation limits** — enforced server-side (Keygate),
   not by the client.
5. **Any guarantee of "unbreakable" / "complete" anti-tamper** — explicitly out of scope (C3).

---

## 7. Per-Control Bypass-Cost & Residual-Risk Matrix

| Control | Stops | Bypass cost (A2) | Bypass cost (A3) | Residual risk | Requires compiled component? |
|---------|-------|------------------|------------------|---------------|------------------------------|
| Signed artifact (Sigstore) | Counterfeit/tampered wheel *(detection)* | High (forge signature) | High | Customer may skip verify | No (pipeline-side) |
| Signed artifact (GPG/age) | Same | High (key theft) | High | Key custody (separate task) | No (pipeline-side) |
| SHA-256 + verify | Same | High | High | Same | No |
| Compiled gate+shim (Cython) | Gate bypass *(cost)* | Medium-High | Medium | frida/recompile | **Yes** |
| Bytecode self-check + import hooks | Disk tamper *(detection, fail-safe)* | Medium | Medium | Runtime patch | No |
| PyArmor/pyoxipin obfuscation | Gate bypass *(cost)* | Medium | Medium | De-obfuscate | No (vendored) |
| Anchored signed manifest (C9) | Post-install tamper *(detection, fail-safe)* | Medium-High | Medium | Anchor must live outside wheel | No |
| Anchored digest in wheel metadata | Post-install tamper *(detection)* | Medium | Medium | Wheel repackage | No |
| Keygate-anchored build digest | Post-install tamper *(detection, server-anchored)* | High (needs server) | High | Server dependency | No |

**Reading:** the cheapest, most portable stack (no compiled component) is
**signed-artifact (pipeline) + anchored manifest (wheel metadata or server) + bytecode
self-check + fail-safe gate + no-telemetry**. Adding a **Cython gate+shim** is the single
change that most raises T1–T4 bypass cost and is the primary **CTO decision point #1**.

---

## 8. Fail-Safe Semantics (binding — C2)

Every integrity / enforcement control must **fail safe (block inference)**, never
fail-open:

| Failure mode | Required behavior |
|--------------|-------------------|
| Integrity check error / cannot read anchor | **Block** inference (raise `LicenseExpiredError` / integrity error) |
| Missing anchor / manifest | **Block** (do not default to "allow") |
| Gate import fails (e.g. `mee/licensing` absent) | **Hard fail** before any inference (current behavior — preserve) |
| Network down + valid license | **Allow** (offline path) — this is the *only* permitted "allow without fresh verify" |
| Network down + expired/revoked/invalid | **Block** |
| Any verification ambiguity | **Block** (never silently allow) |

**Rule:** if in doubt → block. The only "allow" without a fresh network verify is the
documented offline signed-token path with a valid `exp` window.

---

## 9. Cross-Platform & Packaging Impact on the Threat Posture

| Platform | Note for controls |
|----------|-------------------|
| x86_64 (CI + customers) | All options viable; Sigstore + manifest + self-check = zero compiled cost |
| **Jetson AGX Orin (aarch64, unified memory)** | A compiled gate/shim needs an **aarch64 wheel** or an in-tree build; confirm the build matrix covers it before choosing Cython (decision point #1) |
| `manylinux` | Compiled options require per-arch wheels or `auditwheel`; increases maintenance |

**Implication:** the no-compiled-component stack has the **lowest packaging risk** on Jetson;
the Cython option adds real build/ABI maintenance. This must weigh into decision point #1.

---

## 10. Decisions This Threat Model Feeds (→ `TASK_REQUEST.md` §8)

| # | Decision | Threat rows informing it | Recommendation input |
|---|----------|--------------------------|----------------------|
| 1 | Compiled enforcement warranted? | T1–T4, §7 matrix | Only if A2/A3 piracy is the dominant risk *and* the aarch64 build cost is accepted; otherwise self-check + manifest is the proportionate choice |
| 2 | Signing scheme (Sigstore vs GPG) | T5–T7 | Sigstore (keyless) avoids long-lived key custody — lower A4 surface; GPG if keyless tooling is undesirable |
| 3 | Integrity anchoring | T3, T12, C9 | Anchor **outside** the protected code — signed release manifest and/or wheel metadata; reject beside-code-only digest |
| 4 | Fail-safe enforcement point | §8 | Block-on-error, allow-only-offline-with-valid-exp |
| 5 | Offline grace window | T8–T9 | Confirm `exp` window is adequate for field use; document |
| 6 | Keep `RELEASE_KEY_ENCRYPTION_KEY` separate | §2, §6.3, C6 | Confirm out-of-scope; track as its own security task |

---

## 11. Test Matrix to Prove the Threat Model (for G1/G2)

| Test | Expectation | Maps to |
|------|-------------|---------|
| Monkey-patch `EmotionEngine._license_check = no-op` then call `process()` | **Inference blocked** (or residual risk explicitly documented) | T1 |
| Delete/stub `mee/licensing` module | `process()` **hard-fails** before inference | T2 |
| Edit `engine.py` on disk post-install, run `process()` | Integrity check **detects → blocks** | T3 |
| Delete the integrity digest (if beside-code) while keeping code edit | Check must **still block** (proves C9 anchoring) | T12 |
| Install a wheel with a wrong/missing signature | Verify **fails**, install blocked/reported | T5 |
| Valid license + network disabled | Inference **allowed** (offline) | T9 |
| Expired / revoked / invalid license (online) | Inference **blocked** | T9 |
| Scan all network calls in the hardened build | Only activate/verify/deactivate; **no telemetry** | T11 |
| Public API / `LicenseClient` behavior diff | **Unchanged** (or separately approved) | C1 |

---

## 12. Residual-Risk Acceptance Statement (for the PM/owner to sign)

*By proceeding with TASK_MEE_020, the owner accepts that:*

1. The controls **raise the cost and detectability** of unauthorized modification and make
   provenance verifiable, but do **not** make MEE tamper-proof.
2. A party who controls the host runtime, the source, or the Keygate server can still defeat
   client-side licensing; those cases are **operational / server-side** matters (separate tasks).
3. Verification of signed artifacts is only as effective as the customer's willingness to run it.
4. The `RELEASE_KEY_ENCRYPTION_KEY` server-side secret-storage issue remains **open and separate**.

**Owner (PM) signature / acceptance:** ________________________   **Date:** __________

---

*This document is a G0 design input. It does not mandate any implementation choice. All
technical selections remain subject to CTO (G1) review and the approval gates.*
