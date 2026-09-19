# TASK_REQUEST — TASK_MEE_011: Packaging & Documentation

**Task ID:** TASK_MEE_011
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Finalize MEE as a **reusable, installable capability**: packaging, complete documentation, license/compliance notes, and an integration seam for future systems. This closes the project (Post-G4).

## Detailed Requirements
- Finalize packaging: `pyproject.toml` (installable package, correct optional-deps), a clean `README.md` (install, usage, architecture overview, limitations), `requirements.txt`.
- Ensure `docs/ARCHITECTURE.md` (final), `docs/MODEL_EVALUATION.md`, `docs/JETSON_DEPLOYMENT.md`, and `docs/TEST_PROTOCOL.md` are complete and consistent.
- **License & commercialization**: finalize the package license; document that recommended models use commercial-safe licenses (MIT/Apache-2.0 per TASK_MEE_002/003) and that AGPL/NC models were excluded. Add the required disclaimer that emotion estimates are probabilistic, not psychological assessments.
- Define a clear **integration seam**: how a future system consumes MEE output (vision/voice/overall/trend/conflict) without coupling to model internals (per plan §22).
- Clean git history (squash the MEE work into a coherent set of commits), update CHANGELOG.

## Key Files (to create/modify)
- `README.md`, `pyproject.toml`, `requirements.txt`, `CHANGELOG.md`, `LICENSE`
- `docs/ARCHITECTURE.md` (final), `docs/MODEL_EVALUATION.md` (final), `docs/TEST_PROTOCOL.md`
- Any final packaging adjustments.

## Acceptance Criteria
- [ ] `pip install .` works; package imports and runs.
- [ ] README covers install, usage, architecture, and limitations.
- [ ] License and commercial-use notes documented; disclaimer present.
- [ ] Documentation set is complete and internally consistent.
- [ ] Integration seam documented; models remain replaceable.
- [ ] CHANGELOG updated; git history clean.

## Dependencies
- TASK_MEE_010 (Jetson validated), all prior tasks complete.

## Notes / Constraints
- MEE remains an independent capability, not tied to the AI Companion book or any specific robot.
- "Affective-state estimation"; never "reads true emotion."
