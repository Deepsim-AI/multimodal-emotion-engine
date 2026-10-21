# TASK_REQUEST — TASK_MEE_015

**Submitted by**: gateway-owner (user)
**Submitted at**: 2026-10-21T16:5x:00Z (2026-10-21 08:5x PDT)
**Priority**: P1
**Intake agent**: PM
**Task ID**: TASK_MEE_015
**Task name**: MEE License Integration (Gate C)

---

## Verbatim User Request

> I updated the licenses, /home/deepsim/multimodal-emotion-engine/LICENSE.txt, the previous one is still /home/deepsim/multimodal-emotion-engine/LICENSE_1.0 for references. You are so familier on keygate, So write a Proposal/specification on Gate C first. Then we follows DS-EO workflow.
>
> Besides, I accept your previous recommandation (a) trial 14 days then hard stop, and let Keygate's server-side activation cap handle device limits (client just reports a stable device ID). You already mentioned above: proceed with PM G0 intake for TASK_MEE_015 (License Integration, Gate C) in /home/deepsim/multimodal-emotion-engine, then I hand to CTO for G1. So proceed with PM G0 intake for TASK_MEE_015 (License Integration, Gate C) in /home/deepsim/multimodal-emotion-engine, then I hand to CTO for G1

## Captured Requirements

- **R-0 (scope)**: Add client-side license enforcement to MEE against the live Keygate instance at `https://licenses.deepsim.ai:8443`.
- **R-1 (license of record)**: `LICENSE.txt` (Deepsim Commercial Software License v1.1) is the license of record. `LICENSE_1.0` retained for reference. `pyproject.toml` `license` field updated; `README.md` + `docs/` reference `LICENSE.txt`.
- **R-2 (trial)**: 14-day trial on first run (no valid license), then hard stop (raise `LicenseExpiredError` from `EmotionEngine.process()`).
- **R-3 (device limits)**: Keygate server-side activation cap (`max_activations=3`) is the authority. Client reports a stable device ID. No client-side device-limit enforcement.
- **R-4 (offline)**: Work offline within token TTL (ed25519-verified signed token + cached public key). No hard lockout during network outages.
- **R-5 (public API)**: `mee.api.license_status()` + `EmotionEngine.health()["license"]` + `mee-lic` CLI (activate / status / verify / deactivate).
- **R-6 (out of scope)**: Usage metering / API quota (Phase 2), AI Companion licensing (separate repo), refund/cancellation policy (Keygate server-side), white-label / resale.
- **R-7 (testable requirements)**: See `GATE_C_SPECIFICATION.md` §3 (R1–R27).
- **R-8 (acceptance)**: See `GATE_C_SPECIFICATION.md` §6.
- **R-9 (version)**: `pyproject.toml` version 0.1.0 → 0.2.0.
- **R-10 (governance)**: Full DS-EO workflow G0–G5. Artifacts in `docs/development/reports/TASK_MEE_015/`.

## Context / Predecessors

- **Keygate Gate B**: completed 2026-10-21, including the `RELEASE_KEY_ENCRYPTION_KEY` hardening item (license keys encrypted at rest, AES-256-GCM, backfilled for both existing licenses). See `/home/deepsim/keygate_vps/KEYGATE_GATE_B_REPORT.md`.
- **Keygate live instance**: `https://licenses.deepsim.ai:8443` (Let's Encrypt, HSTS). Health: `{"status":"ok","database":"ok","version":"0.1.15"}`.
- **MEE product** registered in Keygate with plan "Pro" (`max_activations=3`, Stripe live price `price_1USnuOC0UMgquCywJEHP30Gw`).
- **Two active MEE licenses** (both encrypted at rest): `KG-V4ACZV6J-...` (manual) and `KG-F42UK5KE-...` (test-mode Stripe webhook).
- **MEE repo**: `/home/deepsim/multimodal-emotion-engine` (master, clean except the in-flight `LICENSE.txt` / `LICENSE_1.0` swap + `tools/download_models.py` fix from the model-consolidation task).
- **License swap in flight**: `LICENSE` (deleted) → `LICENSE.txt` (v1.1) + `LICENSE_1.0` (reference). This task's R-26/R-27 formalizes that swap.

## What the CTO must do (G1)

1. Read `GATE_C_SPECIFICATION.md` in full.
2. Verify Keygate 0.1.15 API endpoints (activate / verify / deactivate / pubkey) against the live instance.
3. Verify the ed25519 signed-token format (capture a real signed token).
4. Decide: trial key issuance (client-local vs server-recorded), device ID transmission format, token TTL policy, retry policy.
5. Produce `CTO_PLAN.md` with exact file/symbol/line-range guidance (R-SI-2), task breakdown, test strategy, acceptance criteria.
6. Do **not** write implementation code.

## Intake boundary

**G0 is complete. Stop here at the intake boundary — the CTO owns independent G1 planning.** PM did not perform architectural analysis, component selection, or solution design. The `GATE_C_SPECIFICATION.md` is a *proposal* for CTO review, not a CTO plan.
