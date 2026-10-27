# G0_INTAKE_CHECKLIST - TASK_MEE_029: Fulcio Keyless Release Signing Deployment (Option A)

**Task ID:** TASK_MEE_029
**Gate:** G0 - PM Intake (mechanical sign-off checklist)
**Date:** 2026-10-26 (PDT)
**Prepared by:** PM 📋 at gateway-owner authorization
**Companion to:** MEE_025_A POC (CLOSED G5 2026-10-26, Option A selected by owner 2026-10-26)

> **Owner decision (2026-10-26): Option A (Fulcio keyless + OIDC) selected over Option B (Cosign).**
> The initial G1 plan had chosen Option B (Cosign key-based) on the basis of two technical claims:
> (1) Forgejo Actions lacks native OIDC, and (2) Rekor requires Trillian (not ARM64-available). Both
> claims are **INCORRECT / OUTDATED** per owner research:
> - Gitea 1.22.0 (the Forgejo 17.0.0 backend) **added native OIDC token issuance for Actions**
>   (`id-token: write`). Confirmed: Forgejo at `17.0.0+gitea-1.22.0`; the current
>   `.github/workflows/release-sigstore.yml` already uses `id-token: write` (line 12).
> - Rekor no longer requires Trillian — **Tessera** (file-based, lightweight) is a production-ready
>   ARM64-compatible alternative to Trillian.
> The G1 plan is superseded; this task deploys Option A.

## 1. Task ID Verification

| Check | Result |
|-------|--------|
| TASK_MEE_029 available by convention | Next unused ID (025-027, 028, 030 taken) OK |
| No conflicting in-flight task | Confirmed - no TASK_MEE_029/ directory exists OK |

## 2. Intake Artifacts Present

| Artifact | Status |
|----------|--------|
| G0_INTAKE_CHECKLIST.md (this file) | written (G0) |
| LOCK.md | this file (PENDING until released) |

## 3. Parent Task Authorization

**TASK_MEE_025_A** (signed POC) evaluated both Option A (Fulcio) and Option B (Cosign). Owner 2026-10-26
selected **Option A (Fulcio keyless + OIDC)** after correcting the technical premises that had favored
Option B. This task deploys Option A.

## 4. Constraints (from MEE_025_A POC + owner 2026-10-26)

| Constraint | Source |
|------------|--------|
| Additive only — do NOT remove/disable current keyless Sigstore (Fulcio) path during migration | MEE_029 constraint |
| Keep both signing paths parallel during migration; no customer breakage | MEE_025_A CTO |
| Fulcio: self-hosted CA (HSM/TPM-backed root key preferred for production) | MEE_025_A Proposal §2.2 |
| Rekor: host via **Tessera** (file-based, ARM64-compatible), not Trillian | owner 2026-10-26 correction |
| Forgejo Actions OIDC (`id-token: write`) is the identity provider for Fulcio | owner 2026-10-26 correction |
| Customer impact: distribute new Fulcio root (trust bundle update) via CHANGELOG/release notes | MEE_025_A §2.2 |
| No production change outside `.github/workflows/release-sigstore.yml` + Forgejo secret + CHANGELOG | Scope |

## 5. Baseline Verification (G0 read-only)

| Check | Result |
|-------|--------|
| Workflow file exists | `.github/workflows/release-sigstore.yml` present (keyless Sigstore, `id-token: write`) OK |
| OIDC already wired | `id-token: write` on line 12 — OIDC identity provider available OK |
| Cosign secret not configured | No COSIGN_PRIVATE_KEY anywhere in repo/.env OK (Option B not used) |
| POC evidence present | `/tmp/mee-signing-poc/` (isolated) — cosign keys, test bundles OK |

---
*G0 process artifact — nothing implemented.*
