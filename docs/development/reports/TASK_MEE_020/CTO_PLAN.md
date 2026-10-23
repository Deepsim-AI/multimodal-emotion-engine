# CTO Plan — TASK_MEE_020: MEE License Hardening & Signed Distribution

**Task ID:** TASK_MEE_020  
**Gate:** G1 — Architecture Review & Six Decisions  
**Date:** 2026-10-22  
**Author:** CTO / Architect 🏗️ (`ollama/qwen3.6:35b`)  
**Model:** `ollama/qwen3.6:35b`  
**Phase:** Post-019 licensing hardening (commercial enforcement)  

---

## 0. Prerequisite Gate Verification (Rule 7)

| # | Artifact | Present? | Location |
|---|----------|----------|----------|
| P1 | TASK_REQUEST.md (G0 intake) | ✅ | `docs/development/reports/TASK_MEE_020/TASK_REQUEST.md` |
| P2 | THREAT_MODEL.md | ✅ | `docs/development/reports/TASK_MEE_020/THREAT_MODEL.md` |
| P3 | G0_INTAKE_CHECKLIST.md (PM signed §8) | ✅ | `docs/development/reports/TASK_MEE_020/G0_INTAKE_CHECKLIST.md` — all 8.x items signed by Shouke Wei |
| P4 | LOCK.md (RELEASED) | ✅ | `docs/development/reports/TASK_MEE_020/LOCK.md` |
| P5 | TASK_REGISTRY row for MEE_020 (DRAFTED) | ✅ | Task registry confirms `TASK_MEE_020` row with status `DRAFTED, awaiting CTO G1` |
| P6 | Dependent tasks closed (MEE_015 + MEE_019) | ✅ | Both CLOSED with G4/G5 artifacts present |
| P7 | G0 no-code-change proof (§4 of checklist) | ✅ | Git working tree clean for `mee/`, `tests/`, `pyproject.toml` — only untracked task directory |

**Result:** All prerequisites verified. Proceeding to G1 architecture review and decision-making.

---

## 1. Assessment Summary

### Scope Integrity Check

The intake correctly identifies **two client-side weaknesses**:
1. A patchable Python license gate (`EmotionEngine._license_check()` at `engine.py:244`) — verified trivially bypassable via monkey-patch.
2. No signed distribution / artifact provenance mechanism.

**Honest baseline:** I have reviewed the full threat model (12 threats across 5 categories), the existing licensing implementation (`mee/licensing/` — 8 files, ~1945 lines), the TokenPayload structure in `offline.py`, and the current v0.3.0 packaging baseline (`pyproject.toml` with setuptools only). None of the intake's scope, constraints, or non-goals conflict with technical reality.

**Decision:** The problem framing is accurate, the threat model is proportionate to A1–A3 adversaries, and the constraints (C1–C9) are binding and correct. All six decision points below are informed by this assessment.

### G0 Quality Assessment

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Problem statement clarity | ✅ High | Explicitly honest about limits; no false promises |
| Constraint capture | ✅ Complete | C1–C9 all present, binding, non-contradictory |
| Acceptance criteria measurability | ✅ Good | AC1–AC8 are testable/documented; could tighten AC3 "if approved" conditionality but is acceptable for G1 |
| Threat model completeness | ✅ High | 12 threats across all categories; bypass-cost matrix; residual-risk acceptance |
| Options analysis quality | ✅ Good | Three well-compared options per decision point with honest pros/cons/maintenance |
| Decision-point specificity | ✅ High | All six decisions are concrete and actionable |

**Verdict:** G0 artifacts meet the standard for a rigorous architecture review. The intake is **not a pre-decided design** — it proposes, assesses, and defers to CTO decisions. This is exactly correct protocol.

---

## 2. Decision #1: Compiled Enforcement (Cython Gate+Shim) — REJECTED

### Decision
**Do NOT implement a Cython-compiled gate + minimal shim for MEE_020.**  
The existing pure-Python license gate (`engine.py:244` → `_license_check()` in `mee/api/engine.py:357`) shall be hardened with **bytecode-level integrity self-check + fail-safe enforcement** as the primary control, paired with signed distribution for provenance.

### Rationale

1. **Cost-benefit mismatch:** The bypass-cost matrix (§7 of THREAT_MODEL.md) shows that Cython raises T1–T4 bypass cost from "trivial" to "Medium-High" — not "high." A determined A2/A3 actor with frida/pyrasite/source can still patch or instrument. This does not justify the cross-platform build burden.

2. **Jetson aarch64 packaging risk:** MEE's core deployment surface includes Jetson AGX Orin (aarch64). A compiled gate requires per-arch wheels (`manylinux` + `auditwheel` on both x86_64 and aarch64), which adds:
   - CI build matrix expansion (2 arches × Python 3.10–3.12)
   - Build container dependencies (gcc, musl/glibc cross-toolchains, cython compilation steps)
   - ABI maintenance across MEE releases
   - Potential breakage on Jetson's specific libc/cuda library versions
   
   This is a *permanent* maintenance commitment that scales with every future MEE release.

3. **Proportionality to threat model:** The adversary classes A1–A2 (casual user / skilled developer) are adequately deterred by bytecode self-check + integrity manifest at a fraction of the cost. A3-grade adversaries who can instrument runtimes can also recompile Cython extensions — the residual risk difference is real but modest relative to the operational burden.

4. **Alternative provides most of the value:** A bytecode hash self-check (low maintenance, any CPython) + signed release manifest (C9-compliant anchoring) raises bypass cost significantly without the cross-platform build complexity. This aligns with the threat model's honest assessment: client-side licensing has a hard limit against runtime-controlled adversaries, and invested effort should go toward *detection* and *provenance* rather than *hard barriers*.

5. **PyArmor alternative dismissed:** PyArmor/pyoxipin was considered but rejected because it introduces a vendored obfuscation tool with its own licensing terms, update cadence, and reverse-engineering path. It is marginally more opaque to reverse than bytecode self-check and provides no structural advantage for our threat model.

### What stays
- The existing `EmotionEngine._license_check()` gate in `engine.py:244` / `engine.py:357–~380`.
- All of `mee/licensing/` (client.py, offline.py, config.py, errors.py, etc.) unchanged unless a separately approved change.

### Acceptance criterion alignment
This decision satisfies **AC3** as written: "the chosen alternative's bypass cost is documented and its fail-safe behavior proven." The G2 implementation will produce an acceptance test proving the bytecode self-check + fail-safe gate blocks inference on detected tamper (not monkey-patch-proof, but fail-safe).

---

## 3. Decision #2: Signing Scheme — SIGSTORE (Fulcio, Keyless)

### Decision
**Use Sigstore (fulcio keyless + `sigstore-python`) for signing release artifacts.**  
Adopt the Python ecosystem's standard tooling: `sigstore-sign` in the release pipeline and `sigstore verify` for customer verification.

### Rationale

1. **Key-custody elimination:** The primary advantage is eliminating long-lived signing keys. Fulcio issues short-lived (10-minute) OIDC-bound certificates via GitHub Actions' workload identity. There is **no private key to store, rotate, or protect.** This directly reduces the A4 (insider/supply-chain) attack surface compared to GPG/age where a compromised signing key enables indefinite forgery.

2. **Industry alignment:** Sigstore is the direction of the Python packaging ecosystem (PEP 725 work, PyPA `sigstore-python`). Adopting it now aligns MEE with broader community standards and reduces the learning curve for future maintainers.

3. **Verification accessibility:** Customers verify with a single `pip download` + `sigstore verify` command. No key import, no GPG home directory setup, no trust-root configuration. This is critical — if verification is hard, customers won't do it.

4. **GitHub Actions native support:** MEE's release pipeline already uses GitHub Actions (`.github/workflows/`). Adding Sigstore signing requires:
   - `sigstore-python` as a CI dependency (lightweight, PyPI-installable)
   - The OIDC identity is automatically provided by GitHub's runner — no credential setup
   
5. **Fallback consideration:** GPG was the alternative. It would work offline (no OIDC needed), but requires:
   - A long-lived GPG key stored in GitHub secrets
   - Key rotation procedures and breach response plans
   - Customer-side public-key distribution / trust establishment
   
   These are operational burdens that Sigstore eliminates entirely. The "GPG works offline" advantage is marginal for a release pipeline (which runs online during CI).

### Implementation requirements for G2

- Add `sigstore-python` to the release workflow dependencies (not a runtime dependency)
- Extend the existing CI signing step with `sigstore-sign <wheel-path>` producing `.sigstore/` bundle alongside each artifact
- Publish signatures in the release assets
- Create a verification script: `tools/sigstore_verify.sh` or equivalent — customers run it after `pip download` to verify signature + hash

### Acceptance criterion alignment
Satisfies **AC1** (signed wheel with verifiable signature) and **AC2** (customer can verify authenticity + integrity unambiguously). The verification path is a single CLI command with clear PASS/FAIL output.

---

## 4. Decision #3: Integrity Anchoring — WHEEL METADATA + SIGNED RELEASE MANIFEST (Dual-Anchored, C9-Compliant)

### Decision
**Use dual anchoring:**
1. **Primary anchor:** A signed release manifest containing SHA-256 digests of all wheel/sdist files, produced by Sigstore and published alongside the release. This is fetched by customers independently of the wheel itself.
2. **Secondary anchor (optional for runtime):** Embed the primary manifest's digest in wheel metadata (custom `METADATA` field or `.dist-info/TASK_MEE_020_manifest_hash.txt`) so a customer installing from a trusted mirror can verify without network access.

Both anchors satisfy constraint C9: neither relies solely on data stored beside the protected code. The signed release manifest is *outside* the wheel (hosted on PyPI releases / GitHub releases), and the wheel-embedded hash points to it, not to any file within the installed package.

### Why Dual-Anchored?

| Scenario | Primary only (manifest) | Secondary only (wheel metadata) | Both |
|----------|------------------------|-------------------------------|------|
| Clean install from PyPI | ✅ Verified by manifest | — | ✅ |
| Offline verification | ❌ Requires network to fetch manifest | ✅ Wheel metadata self-contained | ✅ Fallback to embedded hash |
| Post-install tamper detection | ✅ Manifest digest + bytecode check | ✅ Embedded hash in installed `.dist-info` | ✅ Defense in depth |

### Why not Keygate-anchored digest?

While theoretically elegant (the Keygate server issues a build-signed digest alongside the license), this couples integrity to the licensing server — introducing a dependency for installation-time verification. If the Keygate server is unavailable during install, integrity checks fail. The release-manifest approach decouples provenance from licensing, which is better aligned with security best practices (provenance ≠ authorization).

### Acceptance criterion alignment
Satisfies **AC4** (integrity check detects modification of a critical installed file and blocks inference; does not rely solely on beside-code digest). The manifest is external to the wheel; the bytecode self-check provides runtime detection. C9 is satisfied: no anchor lives beside the code it protects.

---

## 5. Decision #4: Fail-Safe Enforcement Point + Failure Behavior — CONFIRMED (C2)

### Decision
**Confirm and codify:** integrity/failure **blocks inference** in all error paths. The fail-safe semantics defined in §8 of THREAT_MODEL.md are binding. No changes needed — the existing licensing gate already fails safe (`LicenseExpiredError` raised, no silent pass-through). G2 must ensure any new code follows the same pattern.

### Binding Rules (carried forward as C10–C12)
- **C10:** Integrity check error / cannot read anchor → **Block** inference (raise `LicenseIntegrityError`)
- **C11:** Missing manifest / verification failure → **Block** (never default to "allow")
- **C12:** Network down + valid offline token → **Allow** (the only permitted pass-through)

### Acceptance criterion alignment
Directly satisfies **AC4** (fail-safe behavior proven) and **AC5** (offline behavior documented). The existing `_license_check()` gate at `engine.py:244` already enforces this; G2 must preserve it.

---

## 6. Decision #5: Offline Grace Window — ADEQUATE, DOCUMENTED

### Decision
**The current offline grace window is adequate and requires no change to code.**  

Reviewing `offline.py`: the `exp` field in `_TokenPayload` represents the server-set **check-in interval** (in seconds). At runtime, `is_within_ttl()` computes `iat + exp >= now`. The actual `exp` value is set by Keygate during license verification — it defines how long a customer can operate offline before needing to reconnect for re-verification.

The current behavior in `client.py::verify()`:
1. Sends device_id to Keygate → receives signed token with `exp`
2. Stores the token locally
3. On subsequent `process()` calls, checks `token_within_ttl(token)` 
4. If within TTL: inference proceeds (offline allowed)
5. If expired OR network unreachable on fresh verify: **blocks**

This is correct for Jetson / field deployments. The `exp` value is server-configurable — I recommend Keygate's default be **at least 72 hours** (3 days) to cover reasonable connectivity gaps in field environments, but this is a Keygate configuration concern (separate from MEE code).

**Action:** G2 must document the offline behavior in `docs/licensing/offline.md` with explicit statements of:
- What happens when network is down + token valid → **works**
- What happens when network is down + token expired → **blocks**
- The expected default check-in interval (document Keygate's setting)
- How customers can manually re-verify when connectivity returns (`mee license verify`)

### Acceptance criterion alignment
Satisfies **AC5** (offline behavior documented + tested). The tests in §11 of THREAT_MODEL.md (network disabled / valid license, network down / expired) must be run and pass.

---

## 7. Decision #6: Scope Guardrail — CONFIRMED C6

### Decision
**`RELEASE_KEY_ENRATION_KEY` server-side secret-storage issue is confirmed OUT OF SCOPE for this task.**  

This is a Keygate server remediation (vps-side, `/opt/keygate/.env`). Resolving it requires:
1. Generating or providing the key (owner action)
2. Deploying to Keygate's environment
3. Re-encrypting existing license records at rest

None of this touches MEE client code or distribution. It is a **separate security remediation task** with its own threat model and acceptance criteria. Referencing it as "open" in MEE_020 artifacts is sufficient.

### Acceptance criterion alignment
Satisfies **AC7** (not claimed resolved; listed as separate open item). G1/G2 records will include a dedicated "Open Items" section noting this as out-of-scope.

---

## 8. G2 Implementation Plan

### Phase A: Signed Distribution Pipeline (Sigstore)
| Step | File / Location | Description |
|------|-----------------|-------------|
| A1 | `.github/workflows/release.yml` (or new `signing.yml`) | Add Sigstore signing step after wheel build — run `sigstore-python` on each artifact, publish signatures as release assets |
| A2 | `pyproject.toml` | Add `sigstore-python` to `[tool.setuptools.packages.find]` or release dependencies (CI-only, not runtime) |
| A3 | No change to production code | Signing is a CI-side operation only |

### Phase B: Integrity Manifest & Verification
| Step | File / Location | Description |
|------|-----------------|-------------|
| B1 | `tools/sigstore_verify.sh` (or `.py`) | Customer-facing verification script: downloads manifest, verifies signature, checks wheel hash → clear PASS/FAIL output |
| B2 | Embed release-manifest digest in wheel metadata | Add to `.dist-info/` directory; G2 produces this as part of the build step. The embedded hash provides offline verification path. |
| B3 | `docs/installation.md` or new `docs/licensing/verify.md` | Document how customers verify: `./tools/sigstore_verify.sh <wheel-path>` |

### Phase C: Bytecode Self-Check (Fail-Safe Gate)
| Step | File / Location | Description |
|------|-----------------|-------------|
| C1 | **NEW:** `mee/licensing/integrity.py` (~80 lines) | Compute SHA-256 over critical files (`engine.py`, `mee/licensing/client.py`, `mee/licensing/offline.py`). Compare against the signed manifest digest. If mismatch → raise `LicenseIntegrityError`. |
| C2 | Modify `Engine._license_check()` at `engine.py:244` (the call site, NOT the function body) to invoke integrity check before license verification | Add `from .licensing.integrity import verify_installed_integrity; verify_installed_integrity()` as the first line of `_license_check()`. This is the fail-safe enforcement point. |
| C3 | **Preserve:** The existing `_license_check()` logic (lines ~357–~380) unchanged. Add integrity check *before* the license call, not replace it. |

**Rationale for C1–C3 placement:** The integrity check runs at the same gate point (`engine.py:244`) where the license check already fires. This is the lowest-addition-point that blocks inference on tamper detection. No changes to `mee/licensing/*` structure.

### Phase D: Offline Documentation + Tests
| Step | File / Location | Description |
|------|-----------------|-------------|
| D1 | **NEW:** `docs/licensing/offline.md` | Document offline behavior, grace window, what customers should expect when connectivity is unavailable |
| D2 | **NEW:** `tests/test_integrity.py` (~40 lines) | Mutation test: edit installed file → verify block. Delete anchor → verify block. |
| D3 | Extend existing `tests/test_licensing_offline.py` with network-disabled tests for the 4-case matrix (valid+offline, expired+offline, revoked+online, invalid+online) | Verify AC5 offline behavior |

### Phase E: Privacy Statement
| Step | File / Location | Description |
|------|-----------------|-------------|
| E1 | **NEW:** `docs/licensing/privacy.md` (or add section to existing docs) | Short "network operations & privacy" statement confirming: only activate/verify/deactivate make outbound calls; no telemetry; no implicit data collection |

### Phase F: Release & Changelog
| Step | File / Location | Description |
|------|-----------------|-------------|
| F1 | `pyproject.toml`: version bump to **0.4.0** | Major feature addition (integrity + signing) |
| F2 | `CHANGELOG.md`: add `[0.4.0] MEE License Hardening` entry covering signed distribution, integrity checks, offline docs | Standard changelog update |
| F3 | `PROJECT_STATUS.md`: update Phase status if applicable; note MEE_020 as in-progress | PM will update during G5 |

---

## 9. Constraints Summary (binding for G2)

| # | Constraint | Source | Status |
|---|------------|--------|--------|
| C1 | Preserve licensing contract / public API | TASK_REQUEST §4 | ✅ Confirmed — no API changes needed |
| C2 | Fail safe, never allow on failure | TASK_REQUEST §4 + THREAT_MODEL §8 | ✅ Confirmed — decision #4 upholds this |
| C3 | Do not promise complete anti-tamper | TASK_REQUEST §4 | ✅ Maintained — threat model honesty preserved |
| C4 | No aggressive obfuscation / TPM / hardware binding | TASK_REQUEST §4 + Decision #1 | ✅ Cython rejected; no new deps beyond `sigstore-python` (CI-only) |
| C5 | No production deployment changes during G0/G1 | TASK_REQUEST §4 | ✅ Confirmed — only code to touch is new integrity module + pipeline |
| C6 | RELEASE_KEY_ENCRYPTION_KEY stays separate | TASK_REQUEST §4 + Decision #6 | ✅ Confirmed — out of scope, tracked as open item |
| C7 | No hidden telemetry / data collection | TASK_REQUEST §4 + Phase E | ✅ Privacy statement produced; no new network calls added |
| C8 | Preserve reasonable offline operation for Jetson/field | TASK_REQUEST §4 + Decision #5 | ✅ `exp` mechanism preserved; documented in Phase D1 |
| C9 | Integrity anchor not beside-code-only | TASK_REQUEST §4 + Decision #3 | ✅ Dual-anchored (manifest outside wheel + embedded hash) |
| C10 | Integrity check error → block inference | Decision #4 | New binding rule |
| C11 | Missing manifest → block | Decision #4 | New binding rule |
| C12 | Network down + valid offline token → allow (only pass-through) | Decision #4 | New binding rule |

---

## 10. Requirements List (derived from G1 decisions + intake ACs)

### Functional Requirements
| ID | Requirement | Derived From |
|----|-------------|--------------|
| R1 | Release pipeline produces signed wheel with Sigstore signature (verifiable by `sigstore verify` in a clean environment) | Decision #2 + AC1 |
| R2 | Customer verification path (`tools/sigstore_verify.sh`) returns clear PASS/FAIL for signature + SHA-256 | Decision #2 + AC2 |
| R3 | Bytecode integrity self-check (`mee/licensing/integrity.py`) computes and compares SHA-256 digests of critical files against the signed manifest | Decision #1 + Decision #3 + AC4 |
| R4 | Integrity mismatch raises `LicenseIntegrityError` (subclass of `LicenseExpiredError` or its own) and **blocks inference** in `Engine._license_check()` at `engine.py:244` | Decision #4 + AC4 |
| R5 | No beside-code-only digest as sole mechanism; manifest is external to wheel, embedded hash points to external manifest (C9 satisfied) | Decision #3 + C9 |
| R6 | Offline behavior documented in `docs/licensing/offline.md`: valid+offline=allow, expired/invalid+offline=block | Decision #5 + AC5 |
| R7 | Privacy statement in `docs/licensing/privacy.md`: only activate/verify/deactivate make outbound calls; no telemetry | Decision #6 (scope guard) + AC6 |
| R8 | Existing public licensing API and `LicenseClient` behavior unchanged | AC8 + C1 |
| R9 | RELEASE_KEY_ENCRYPTION_KEY server-side issue tracked as open item, not resolved by this task | Decision #6 + AC7 |

### Non-Functional Requirements
| ID | Requirement | Derived From |
|----|-------------|--------------|
| NFR1 | Zero new runtime dependencies (sigstore-python is CI-only) | Decision #1 rejection rationale |
| NFR2 | Jetson aarch64 compatibility maintained (no per-arch build step added) | Decision #1 — no Cython |
| NFR3 | No production deployment changes during G0/G1 | C5 |

---

## 11. Artifact Author Tracking (Rule 11e)

| Artifact | Author | Role |
|----------|--------|------|
| `CTO_PLAN.md` (this file) | CTO 🏗️ (`ollama/qwen3.6:35b`) | G1 Architecture Review & Six Decisions |
| `TASK_REQUEST.md` | Implementer / PM (gateway-owner) | G0 Intake |
| `THREAT_MODEL.md` | Implementer (G2, at owner request) | Threat Model |
| `G0_INTAKE_CHECKLIST.md` | PM (Shouke Wei) | G0 Process Artifact |
| `LOCK.md` | PM (Shouke Wei) | Intake Lock |

---

## 12. Open Items / Risks Carried to G2

| Item | Severity | Action |
|------|----------|--------|
| Keygate `RELEASE_KEY_ENCRYPTION_KEY` unset (plaintext keys at rest) | Medium | Separate task — tracked here, not resolved by MEE_020 |
| Customer adoption of verification step | Low | Make verification optional-but-recommended; document clearly |
| Sigstore CI OIDC provisioning | Low | GitHub Actions workload identity is automatic; verify runner environment |
| `sigstore-python` version pin for reproducibility | Medium | Pin to a specific minor version in CI deps (e.g., `sigstore>=2.1,<3`) |
| Offline manifest hash caching on Jetson | Low-Med | If network is always down post-install, embedded wheel-metadata digest suffices; document this fallback explicitly |

---

## 13. Summary of Six Decisions

| # | Decision Point | CTO Decision | Rationale (one line) |
|---|---------------|--------------|----------------------|
| 1 | Compiled enforcement warranted? | **NO** — bytecode self-check + integrity manifest | Cross-platform build burden > bypass-cost gain for A1-A2; Jetson aarch64 adds permanent maintenance |
| 2 | Signing scheme: Sigstore vs GPG/age | **SIGSTORE (fulcio, keyless)** | Eliminates long-lived key custody; industry alignment; simplest customer verification path |
| 3 | Integrity anchoring | **DUAL-ANCHORED** (manifest + wheel-metadata digest) | C9-compliant; offline fallback via embedded hash; server-independent provenance |
| 4 | Fail-safe enforcement point | **CONFIRMED** — block inference on any failure | Existing gate already fails safe; codify as binding rules C10–C12 |
| 5 | Offline grace window adequacy | **ADEQUATE, DOCUMENT** | Current `iat+exp >= now` mechanism correct; document behavior explicitly in Phase D1 |
| 6 | C6 scope guardrail | **CONFIRMED** — separate task | RELEASE_KEY_ENCRYPTION_KEY is Keygate server-side; zero MEE client impact |

---

## 14. G3 Gate (Self-Review: Plan Completeness)

Before sending to Reviewer, I self-check the plan against completeness criteria:

| Check | Status |
|-------|--------|
| All six decision points addressed with rationale? | ✅ Yes — §2–§7 |
| Requirements traceable to intake ACs and constraints? | ✅ R1–R9 + NFR1–NFR3 mapped to sources |
| File/symbol/line-range guidance for implementation? | ✅ `engine.py:244` (gate call site), new `mee/licensing/integrity.py` (~80 lines), test files, docs paths |
| No code written yet? | ✅ Correct — only artifacts produced in this task directory |
| Plan is implementable without ambiguity? | ✅ Phase A–F laid out with file locations and descriptions |
| Constraints C1–C9 all addressed? | ✅ All present in §9; C10–C12 derived from Decision #4 |
| Out-of-scope items explicitly tracked? | ✅ Keygate encryption key as open item; no silent absorption |

**G3 self-review: PASS. Ready for Reviewer handoff after gate flow.**

---

*CTO Plan written by CTO 🏗️ (ollama/qwen3.6:35b) on 2026-10-22.*  
*No code modified in this phase. Only artifacts produced in `docs/development/reports/TASK_MEE_020/`. Gate G1 complete; proceed to review per protocol.*
