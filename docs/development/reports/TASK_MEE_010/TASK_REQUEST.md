# TASK_REQUEST — TASK_MEE_010: Jetson AGX Orin Deployment

**Task ID:** TASK_MEE_010
**Status:** Ready → awaiting CTO plan
**Requested By:** PM · **Assignee:** CTO (plan) · Implementer (build) · Reviewer (verify)

## Objective
Validate and optimize MEE on the **Jetson AGX Orin (64GB unified memory)** after the PC prototype is proven. Measure resource use and latency; produce a deployment guide.

## Detailed Requirements
- Optimize models for edge: quantization (INT8 where possible), ONNX/TensorRT paths (see TASK_MEE_002/003 license + Jetson notes).
- Measure: GPU utilization, CPU utilization, memory consumption, FPS, face-detection latency, facial-expression inference latency, voice inference latency, fusion latency, end-to-end latency, concurrent camera+audio stability, stability over an extended run.
- Keep within the hardware constraint: **never load more than ~3 large models at once**; unload idle models between agent phases.
- Produce `docs/JETSON_DEPLOYMENT.md` covering: hardware config, software versions, installation steps, model versions, runtime config, performance measurements, known limitations.

## Key Files (to create/modify)
- `docs/JETSON_DEPLOYMENT.md`
- Model optimization scripts / config in `mee/` (e.g. ONNX export utilities) — minimal, behind the API.

## Acceptance Criteria
- [ ] MEE runs on Jetson AGX Orin with local inference (no cloud).
- [ ] Latency and resource metrics measured and documented.
- [ ] Extended-run stability verified.
- [ ] `docs/JETSON_DEPLOYMENT.md` complete (install + perf + limitations).
- [ ] Model sizes / memory budget documented; INT8 quantization applied where beneficial.

## Dependencies
- TASK_MEE_009 (PC prototype validated first).

## Notes / Constraints
- Jetson deployment must not depend on the AI Companion book.
- "Affective-state estimation"; never "reads true emotion."
- Performance numbers are engineering parameters, not scientific ground truth.
