# TASK_REQUEST — TASK_MEE_014

**Submitted by**: gateway-owner (user)
**Submitted at**: 2026-09-23T22:20:00Z (2026-09-23 15:20 PDT)
**Priority**: P1
**Intake agent**: PM
**Task ID**: TASK_MEE_014
**Task name**: MEE Remote Browser Demo Client

---

## Verbatim User Request

> I create new task folder and TASK_MEE_014, and put my requirement at
> /home/deepsim/multimodal-emotion-engine/docs/development/reports/TASK_MEE_014/MEE_REMOTE_BROWSER_DEMO_PM_TASK_REQUEST.md.
> Please read it and start this task.

The full original requirement is preserved verbatim in the attached file
`MEE_REMOTE_BROWSER_DEMO_PM_TASK_REQUEST.md` in this task directory. It is reproduced
here in full below for a single-source reference at intake.

---

### [Full original requirement — verbatim, from MEE_REMOTE_BROWSER_DEMO_PM_TASK_REQUEST.md]

```markdown
# PM Task Request — MEE Remote Browser Demo Client

PM, please create a new task for the **Multimodal Emotion Engine (MEE) Remote Browser Demo Client**
and start the task through the normal DS-EO workflow.

## Background

We are developing the Multimodal Emotion Engine (MEE) as a reusable AI perception capability for the
future Deepsim AI Companion Platform.

I need a way for an external partner, Mr. Xu's team in China, to test MEE remotely from their own
computers **without giving them access to our source code, model weights, SSH, Tailscale tailnet, or
internal network**.

The immediate goal is a prototype/test system, not a production public API.

## Requirement

Create a **browser-based remote MEE test client** that allows a remote tester to use their own
computer's:

- Webcam
- Microphone

The tester should only need to open a web page and grant browser camera/microphone permissions.
No local software installation should be required.

The browser client should communicate with the MEE backend running on our controlled
infrastructure/Jetson.

## Expected functionality

1. Browser camera access and live camera preview
2. Browser microphone access
3. Start/Stop testing controls
4. Transmission of camera frames to MEE
5. Transmission of microphone/audio data to MEE
6. Facial-expression estimation results
7. Voice/acoustic emotion estimation results
8. Multimodal/fused affective-state result
9. Confidence scores
10. Temporal state/trend information
11. Connection status
12. Basic latency/performance information
13. Clear indication when camera/microphone are active
14. Graceful handling of permission denial, disconnects, and backend errors

The prototype should preserve the existing MEE architecture and API boundaries rather than
embedding model logic directly into the browser client.

## Security / IP boundary

The remote tester must NOT receive:

- MEE source code
- Model weights
- SSH access
- Tailscale tailnet membership
- Access to the Jetson filesystem
- Access to internal services

The remote client should interact only with an explicitly exposed MEE test interface.

The design should also consider authentication/access control, rate limiting, input validation,
and preventing arbitrary access to backend services.

## Transport

For the prototype, evaluate the simplest reliable transport suitable for browser
camera/microphone access.

Potential approaches include:

- HTTPS + HTTP image/audio chunks
- WebSocket streaming
- A temporary Tailscale/Tailcat-based connection if technically appropriate

However, the browser security requirement for camera/microphone access must be considered.
Do not assume that a plain HTTP endpoint is sufficient.

The design should keep the transport layer replaceable so that the prototype can later evolve into
a proper Deepsim API.

## Future architecture

Client Devices (browser / robot / mobile)
          │
          ▼
   Deepsim Companion API
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  Chat   MEE  Memory
          │
          ▼
   Affective State

The immediate task should implement the **remote MEE demo client**, while avoiding unnecessary
coupling to the future production API.

## Deliverables

- Remote browser demo client
- Required backend/API endpoints
- Authentication/access mechanism appropriate for a controlled prototype
- Camera/audio transport implementation
- Integration with the existing MEE engine
- Automated tests
- End-to-end local testing
- Remote-access testing procedure
- Security/IP-boundary documentation
- Deployment instructions
- Documentation explaining how Mr. Xu's team can test it from their own computers

## Important constraint

This is an **MEE capability test**, not a request to build a complete commercial AI Companion platform.

Keep the implementation focused and modular. Do not introduce LLM, robot-control, TTS,
long-term memory, cloud-scale infrastructure, or other unrelated functionality unless CTO
identifies a specific dependency that is genuinely required.
```

---

## Captured Requirements

Discrete, testable requirements gathered during intake (derived verbatim from the source request):

1. **Web client delivered via browser** — tester accesses functionality by opening a URL and
   granting camera/microphone permissions; no local software installation required.
2. **Camera access + live preview** in the browser.
3. **Microphone access** in the browser.
4. **Start/Stop testing controls.**
5. **Camera frame transport** from browser to the MEE backend.
6. **Audio transport** from browser to the MEE backend.
7. **Facial-expression estimation results** displayed.
8. **Voice/acoustic emotion estimation results** displayed.
9. **Fused/multimodal affective-state result** displayed.
10. **Confidence scores** displayed.
11. **Temporal state / trend information** displayed.
12. **Connection status** displayed.
13. **Latency / performance information** displayed.
14. **Active camera/microphone indicators** in the UI.
15. **Graceful handling** of permission denial, disconnects, and backend errors.
16. **IP/security boundary**: tester receives no source code, model weights, SSH, Tailscale
    tailnet, Jetson filesystem access, or access to internal services.
17. Tester interacts only with an **explicitly exposed MEE test interface**.
18. **Authentication / access control, rate limiting, and input validation** must be considered.
19. **Transport must keep camera/microphone browser requirements in mind** (HTTPS/WebSocket),
    not plain HTTP.
20. **Transport layer must be replaceable** so the prototype can later evolve into a proper API.
21. **Preserve existing MEE architecture and API boundaries** — do not embed model logic in the
    browser client.
22. **Avoid coupling to the future production Deepsim API.**
23. **Automated tests** included.
24. **End-to-end local testing** performed.
25. **Remote-access testing procedure** documented.
26. **Security/IP-boundary documentation** produced.
27. **Deployment instructions** produced.
28. **User documentation** for Mr. Xu's team explaining how to test from their own computers.
29. **Scope constraint**: this is an MEE capability test, not a full commercial AI Companion
    platform. Do not introduce LLM, robot-control, TTS, long-term memory, or cloud-scale
    infrastructure unless the CTO identifies a genuinely required dependency.

---

## Supporting Materials

- `/docs/development/reports/TASK_MEE_014/MEE_REMOTE_BROWSER_DEMO_PM_TASK_REQUEST.md`
  (original requirement document submitted by the user)

**Materials the user may add later**: MEE existing API surface / endpoint contracts, MEE
deployment diagram, Jetson network/exposure details, MEE auth model (if any), and any Deepsim
Companion Platform interface stub that MEE must plug into.

---

## Notes

- Stakeholder end user is Mr. Xu's team in China (remote testers).
- Target backend runs on the controlled Jetson infrastructure.
- Prototype/test system — not a production public API at this stage.
- PM performed **administrative intake only (G0)**: folder scaffold, `LOCK.md`, and
  `TASK_REQUEST.md`. No architectural analysis, component selection, or solution design was
  performed by PM. CTO owns independent G1 planning.
- CTO must independently inspect the MEE repository and confirm existing API/transport options
  before producing `CTO_PLAN.md` (R-SI-1 / R-SI-2 source-inspection rules).

---

*Intake completed by PM on 2026-09-23. G0 boundary reached — handed off to CTO for G1 planning.*
