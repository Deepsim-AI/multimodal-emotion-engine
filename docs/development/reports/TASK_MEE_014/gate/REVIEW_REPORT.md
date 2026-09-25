# Review Report — TASK_MEE_014 Gate G2

**Reviewer**: Reviewer 🔍 (ollama/laguna-xs-2.1:q4_K_M)  
**Date**: 2026-09-24  
**Gate**: G2 — Architecture & Specification Review

---

## Executive Summary

**Status**: ✅ **PASS with notes**

The CTO plan is well-structured, addresses the core requirements, and makes sound architectural decisions for the stated constraints. The proposed WebSocket over Tailscale Funnel transport is appropriate for browser-based camera/mic access from China. The security design is adequate for a prototype-grade implementation.

**Recommendation**: Proceed to G3 (Implementer) with the following notes addressed.

---

## Review Checklist

### 1. ✅ Requirement Coverage (all 29 requirements)

The plan adequately addresses all 29 captured requirements. Key mappings verified:

| Req # | Requirement | Covered in Plan |
|-------|-------------|-----------------|
| 1-14 | Browser client functionality | ✅ Subtask 2 (Browser Client) maps all UI elements |
| 15 | Graceful error handling | ✅ Web page code includes disconnection/permission denial handlers |
| 16-18 | Security/IP boundary | ✅ Subtask 3 + Security Design section address auth, rate limiting, input validation |
| 19 | Transport HTTPS/WebSocket | ✅ Transport Decision section justifies this |
| 20 | Replaceable transport layer | ✅ Architecture uses abstraction; plan notes compatibility with future Deepsim API |
| 21-22 | Preserve MEE architecture | ✅ Server acts as consumer of `EmotionEngine.process()`, no embedding |
| 23-28 | Documentation deliverables | ✅ Subtasks 3+4 specify docs: DEPLOYMENT.md, ACCESS.md, SECURITY.md |
| 29 | Scope constraint | ✅ Plan explicitly notes this is MEE capability test, not full platform |

**Minor gap noted**: Requirement 17 (explicitly exposed MEE test interface) is partially addressed by the token-based WebSocket handshake, but the plan should explicitly state that the endpoint exposes a single, well-defined interface that does not expose internal services.

### 2. ✅ API Contract Compliance

The plan correctly preserves the `EmotionEngine.process()` output contract:

- ✅ Face results: `face{emotion, confidence, scores, has_face}`
- ✅ Voice results: `voice{emotion, confidence, scores}`  
- ✅ Overall: `overall{emotion, confidence, conflict}`
- ✅ Trend: `trend(str)`
- ✅ Latency: `latency_ms(float)`

The server implementation section correctly references `mee/api/engine.py:84` for the `EmotionEngine` and `MEEConfig` for constructor parameters. The browser client will receive the result dict via WebSocket and render without transformation.

**Potential drift point**: The plan mentions video frame size capping at 640×480 in the security section but doesn't specify the expected input format for `engine.process()`. Need to verify that the browser client's JPEG capture maps to the expected numpy frame format defined in `mee/vision/processor.py`.

### 3. ✅ Transport Feasibility

WebSocket over Tailscale Funnel is the **correct choice** for these constraints:

- **Browser HTTPS requirement**: ✅ Tailscale Funnel provides HTTPS endpoint → getUserMedia will work
- **China-to-West-Coast latency**: WebSocket is appropriate for low-latency streaming; 120-200ms RTT is acceptable for emotion estimation (frame rate can be reduced to compensate)
- **No public ports**: ✅ Funnel exposes single HTTPS endpoint without firewall changes
- **IP boundary**: ✅ Only the Funnel endpoint is shared; source, weights, SSH all remain internal

**One concern**: The plan notes a "FALLBACK" for China firewall blocking Tailscale but doesn't detail implementation. The contabo-vps bridge is mentioned but requires verification. I recommend adding a verification step in Subtask 1 to confirm the Funnel endpoint is reachable from China.

### 4. ✅ Security Adequacy (Prototype-Grade)

The prototype-grade security design is acceptable:

| Security Aspect | Plan Coverage | Assessment |
|-----------------|---------------|------------|
| Authentication | Single token via `MEE_DEMO_TOKEN` env var | ✅ Appropriate for controlled prototype |
| Rate limiting | FPS cap (15), audio chunk bounds | ✅ Matches requirement |
| Input validation | Frame size (640×480), audio chunk (320 samples) | ✅ Bounded payloads |
| DoS protection | 10 concurrent connections, idle timeout | ✅ Prototype-grade |
| IP boundary | No code/weights/SSH exposure | ✅ Correct |

**One improvement**: The token is sent as a "first WebSocket message". Consider specifying authentication timing (before any frame processing) and error handling (connection close with specific code on auth failure).

### 5. ✅ Scope Creep Check

The plan **does not exhibit scope creep**:

- ❌ No LLM integration
- ❌ No robot control
- ❌ No TTS
- ❌ No long-term memory
- ❌ No cloud-scale infrastructure

The focus is correctly on:
1. Remote browser client with camera/mic
2. WebSocket transport to existing MEE engine
3. Deployment/access documentation

**Acceptable consideration**: The Funnel fallback (contabo-vps bridge) is appropriately scoped as a contingency, not a new feature.

### 6. ⚠️ Subtask Decomposition

The 4 subtasks are **well-separated** but have a dependency issue:

| Subtask | Dependency | Assessment |
|---------|------------|------------|
| 1: Server | None | ✅ Can proceed independently |
| 2: Browser | None (protocol spec) | ✅ Can proceed independently |
| 3: Funnel/Deployment | **Server must be working** | ⚠️ Needs server API stability |
| 4: Testing | Server for integration | ✅ Requires server first |

**Issue**: Subtask 3 (Deployment) claims to depend on Subtask 1, but the plan's execution order lists Subtask 1 → Subtask 2 (parallel) → Subtask 3+4. This is correct. However, the Funnel integration needs access to a running server to test the endpoint. Recommend adding a verification step: ensure the server starts correctly and the Funnel URL resolves before documenting deployment.

**Improvement**: Subtask 2's browser client should document the WebSocket protocol (message formats, authentication handshake) in a simple spec file. This allows concurrent development with the server.

---

## Technical Concerns & Suggestions

### High Priority
1. **China firewall verification**: Add a step in Subtask 1 to verify the Funnel endpoint is reachable from China (or document how to test this).
2. **Input format spec**: Document the expected frame format for `engine.process()` - is it BGR numpy array? RGB? JPEG bytes?

### Medium Priority
3. **Protocol documentation**: Create a simple WebSocket protocol spec (message formats) for browser/server handoff.
4. **Token security**: Specify that the token should be transmitted securely (WebSocket subprotocol header?) and documented in ACCESS.md for Mr. Xu's team.
5. **Reconnection strategy**: Browser client should attempt reconnection with exponential backoff; document this behavior.

### Low Priority
6. **Performance tuning**: Document how to adjust FPS limits and buffer sizes based on network conditions.

---

## Final Verdict

**PASS to G3 (Implementer)** with the understanding that:

1. The implementation must verify China connectivity via Tailscale Funnel
2. Input/output formats must be clearly documented for browser/server interoperability
3. Security token handling must be explicit in the deployment guide

The plan demonstrates good architectural thinking, appropriate transport choice, and disciplined scope control. The MEE engine integration is cleanly separated from the browser client.

---

*End of Review Report*