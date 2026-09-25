# PM Task Request — MEE Remote Browser Demo Client

PM, please create a new task for the **Multimodal Emotion Engine (MEE) Remote Browser Demo Client** and start the task through the normal DS-EO workflow.

## Background

We are developing the Multimodal Emotion Engine (MEE) as a reusable AI perception capability for the future Deepsim AI Companion Platform.

I need a way for an external partner, Mr. Xu’s team in China, to test MEE remotely from their own computers **without giving them access to our source code, model weights, SSH, Tailscale tailnet, or internal network**.

The immediate goal is a prototype/test system, not a production public API.

## Requirement

Create a **browser-based remote MEE test client** that allows a remote tester to use their own computer's:

- Webcam
- Microphone

The tester should only need to open a web page and grant browser camera/microphone permissions. No local software installation should be required.

The browser client should communicate with the MEE backend running on our controlled infrastructure/Jetson.

## Expected functionality

The remote demo should provide:

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

The prototype should preserve the existing MEE architecture and API boundaries rather than embedding model logic directly into the browser client.

## Security / IP boundary

The remote tester must NOT receive:

- MEE source code
- Model weights
- SSH access
- Tailscale tailnet membership
- Access to the Jetson filesystem
- Access to internal services

The remote client should interact only with an explicitly exposed MEE test interface.

The design should also consider authentication/access control, rate limiting, input validation, and preventing arbitrary access to backend services.

## Transport

For the prototype, evaluate the simplest reliable transport suitable for browser camera/microphone access.

Potential approaches include:

- HTTPS + HTTP image/audio chunks
- WebSocket streaming
- A temporary Tailscale/Tailcat-based connection if technically appropriate

However, the browser security requirement for camera/microphone access must be considered. Do not assume that a plain HTTP endpoint is sufficient.

The design should keep the transport layer replaceable so that the prototype can later evolve into a proper Deepsim API.

## Future architecture

The long-term direction is:

```text
Client Devices
(browser / robot / mobile)
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
```

The immediate task should therefore implement the **remote MEE demo client**, while avoiding unnecessary coupling to the future production API.

## Deliverables

Please have CTO determine the detailed implementation plan and have the appropriate agents implement and review it.

Expected deliverables include:

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

Keep the implementation focused and modular. Do not introduce LLM, robot-control, TTS, long-term memory, cloud-scale infrastructure, or other unrelated functionality unless CTO identifies a specific dependency that is genuinely required.

Please create the task according to the standard DS-EO PM intake process, including the task folder and `TASK_REQUEST.md`, then hand it to CTO for planning.
