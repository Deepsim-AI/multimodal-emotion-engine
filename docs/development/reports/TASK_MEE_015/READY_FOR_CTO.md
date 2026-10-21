# READY_FOR_CTO — TASK_MEE_015

```json
{
  "type": "READY_FOR_CTO",
  "taskId": "TASK_MEE_015",
  "taskPath": "/home/deepsim/multimodal-emotion-engine/docs/development/reports/TASK_MEE_015",
  "intakeAgent": "PM",
  "artifactsAvailable": ["TASK_REQUEST.md", "GATE_C_SPECIFICATION.md", "LOCK.md", "READY_FOR_CTO.md"],
  "lockStatus": "released",
  "status": "INTAKE_COMPLETE",
  "stopReason": "Intake boundary reached. CTO must independently perform G1 technical analysis.",
  "pmDidNotPerformArchitecturalAnalysis": true
}
```

## Handoff Notes (PM → CTO)

**G0 is complete. Stop here at the intake boundary — the CTO owns independent G1 planning.**

### Intake summary
- Task: **MEE License Integration (Gate C)** — add client-side license enforcement to MEE against the live Keygate instance.
- Owner's explicit decisions captured:
  - **Trial**: 14 days, then hard stop (raise `LicenseExpiredError`).
  - **Device limits**: Keygate server-side activation cap (`max_activations=3`) is the authority. Client reports a stable device ID.
  - **License of record**: `LICENSE.txt` (v1.1). `LICENSE_1.0` retained for reference.
- 27 testable requirements in `GATE_C_SPECIFICATION.md` §3 (R1–R27).
- Acceptance criteria in `GATE_C_SPECIFICATION.md` §6.
- Version bump: 0.1.0 → 0.2.0.

### What the CTO must NOT do (intake boundary)
- Do not perform architectural analysis, component selection, or solution design here.
- Do not write implementation code (CTO is read-only by policy).
- Do not assume the `GATE_C_SPECIFICATION.md` is a CTO plan — it is a *proposal* for CTO review.

### What the CTO MUST do (G1)
1. Read `GATE_C_SPECIFICATION.md` in full.
2. Verify Keygate 0.1.15 API endpoints (activate / verify / deactivate / pubkey) against the live instance at `https://licenses.deepsim.ai:8443`.
3. Verify the ed25519 signed-token format (capture a real signed token with a valid license key).
4. Decide: trial key issuance (client-local vs server-recorded), device ID transmission format, token TTL policy, retry policy.
5. Produce `CTO_PLAN.md` with:
   - Exact file/symbol/line-range guidance for every change (R-SI-2).
   - Task breakdown (Implementer sessions, ≤ 3 model-pressure windows).
   - Test strategy (unit + integration + E2E smoke).
   - Acceptance criteria derived from `GATE_C_SPECIFICATION.md` §6.
6. Read `/home/deepsim/keygate_vps/KEYGATE_GATE_B_REPORT.md` for the live Keygate state (products, plans, licenses, endpoints).

### Context for CTO
- Keygate live instance: `https://licenses.deepsim.ai:8443` (Let's Encrypt, HSTS, healthy).
- MEE product registered with plan "Pro" (`max_activations=3`, Stripe live price `price_1USnuOC0UMgquCywJEHP30Gw`).
- Two active MEE licenses (both encrypted at rest): `KG-V4ACZV6J-...` (manual) and `KG-F42UK5KE-...` (test-mode Stripe webhook).
- MEE repo: `/home/deepsim/multimodal-emotion-engine` (master).
- `EmotionEngine` public API: `mee/api/engine.py` — `EmotionEngine.process()` is the primary entry point (line ~216). `health()` at line ~339.
- No license check exists today — `process()` runs unconditionally.
