# TASK REQUEST: MEE Signing — Independent Signing Proof of Concept

**Task ID:** Pending (proposed: TASK_MEE_025_A or similar per DS-EO convention)  
**Status:** PENDING — awaiting PM intake  
**Priority:** High  
**Depends on:** TASK_MEE_024 approved direction (Phase B: Cosign key-based signing evaluation)  

## Objective

Run a bounded proof of concept evaluating two alternative signing approaches for Deepsim's
independent release infrastructure: (1) key-based Cosign with self-hosted key pair, and
(2) self-hosted Fulcio + OIDC integration.

## Context

Per TASK_MEE_024 decision 1, the owner approves evaluation of self-hosted signing alternatives
but explicitly does NOT authorize production migration. This task is a POC only — no changes
to production workflows or release publication.

The current MEE signing pipeline (GitHub Actions + public Sigstore Fulcio) continues as baseline.

## Deliverables

1. **Cosign POC environment** — ECDSA P-256 key pair generated and stored in local test secret store
2. **Fulcio OIDC POC environment** — Self-hosted Fulcio instance deployed with Forgejo-compatible OIDC issuer
3. **Verification test results** — Customer-side verification for both signing paths against POC artifacts
4. **Key protection analysis** — Comparison of key storage, compromise recovery, and rotation procedures
5. **Operational requirements report** — CPU, RAM, disk, maintenance burden estimates for production deployment

## Acceptance Criteria

- [ ] AC-1: Cosign signing produces valid .sigstore.json bundles verifiable against the POC public key
- [ ] AC-2: Fulcio POC signs artifacts via Forgejo-compatible OIDC token exchange
- [ ] AC-3: Customer-side `verify_release.sh` reports PASS for both POC paths with documented trust configuration
- [ ] AC-4: Key compromise, recovery, and rotation procedures documented (not just theoretical)
- [ ] AC-5: Operational cost estimates provided (hardware requirements, maintenance hours/week)
- [ ] AC-6: Security comparison between Cosign key-based and Fulcio keyless approaches documented

## Constraints

- **Do NOT modify** existing GitHub Actions release workflows
- **Do NOT publish** any new releases or artifacts to Hub or Forgejo
- **Do NOT change** v0.4.5 or any historical release
- All work runs in isolated test environment on local VPS
- No customer-facing changes or communications required

## Governance

PM intake → CTO plan → Implementer → Reviewer → CTO approval (for POC results only)

---
*End of TASK_REQ for Signing POC evaluation.*
