# CTO Plan — TASK_MEE_014

**Task**: MEE Remote Browser Demo Client  
**Author**: CTO 🏗️ (ollama/qwen3.6:35b)  
**Date**: 2026-09-23  
**Gate**: G1 — Planning & Specification  

---

## Source Inspection Summary

### Existing MEE Architecture (verified from source)

| Component | Path | What It Does |
|-----------|------|-------------|
| `EmotionEngine` | `mee/api/engine.py:84` | Stable public API — `process(video_frame, audio)` → `{face, voice, overall, trend, latency_ms}` |
| `MEEConfig` | `mee/api/engine.py:23` | Configurable fusion weights, thresholds, model paths, sample rate, output format |
| Vision Processor | `mee/vision/processor.py` | Face detection + expression estimation via ONNX retina-face/emotiefflib pipeline |
| Voice Processor | `mee/voice/processor.py` | Acoustic emotion estimation via SpeechBrain RavNet |
| Fusion | `mee/fusion/emotion_fusion.py:32` | Deterministic weighted fusion (default 50/50) with explicit conflict reporting |
| Temporal State | `mee/state/history.py`, `mee/state/estimator.py:30` | EmotionHistory buffer + analyze_trend over last N samples |
| Existing Demo | `demo/emotion_demo.py:1` | Streamlit local-only demo — uses camera/mic capture + calls engine directly. **No network layer.** |

### Key API Contract (must be preserved)

```python
engine = EmotionEngine(config=MEEConfig())
result = engine.process(video_frame=frame, audio=audio_chunk)
# result keys: face{emotion,confidence,scores,has_face}, voice{emotion,confidence,scores},
#              overall{emotion,confidence,conflict}, trend(str), latency_ms(float)
```

The remote client **must** be a consumer of this API — no model embedding in the browser.

### Network Reality (verified via ss/ip/tailscale)

- Jetson local IP: `192.168.1.104` (private LAN only)
- Tailscale IP: `100.97.141.103` (tailnet only)
- No public-facing ports; SSH on port 22 (not usable for remote testers)
- Mr. Xu's team is in China — cannot reach private LAN, and tailnet membership was explicitly excluded

### Transport Decision

**Chosen approach: `HTTPS → reverse proxy via Tailscale Funnel + Python WebSocket server`**

Rationale:
1. **Browser camera/mic requires HTTPS (or localhost)** — plain HTTP won't work in production browsers for getUserMedia
2. **Tailscale Funnel** exposes a single HTTPS endpoint to the public internet without port forwarding or firewall changes on the Jetson
3. **WebSocket** is ideal for bidirectional streaming of camera frames + audio chunks with low overhead
4. **Python-based backend** — uses only standard libraries + existing MEE engine, no new runtime dependencies beyond what MEE already pulls

Alternative rejected: "Simple HTTPS + HTTP image/audio chunks" was evaluated but WebSocket provides lower latency, better frame-rate synchronization, and simpler state management for continuous streaming.

### Architecture

```
┌─────────────────────────┐       ┌──────────────────────────┐       ┌──────────────────────┐
│  Mr. Xu's Browser       │       │  Jetson (MEE Backend)    │       │  MEE Engine          │
│                         │       │                          │       │                      │
│  • getUserMedia (cam/mic)│──────▶│  WebSocket server       │───────▶│  EmotionEngine       │
│  • send frame chunks    │HTTP/WSS│  port :8910             │       │  .process()            │
│  • receive JSON results │       │                          │       │                      │
│  • render UI            │       │  + simple token auth     │       │                      │
└─────────────────────────┘       └──────────────────────────┘       └──────────────────────┘
                                         ▲
                                   Tailscale Funnel
                                   (HTTPS → :8910)
```

### Security Design (Prototype-Grade)

| Concern | Mitigation |
|---------|-----------|
| Authentication | Single shared access token (configurable via env var `MEE_DEMO_TOKEN`). Token sent as first WebSocket message after connection. |
| Rate limiting | Per-connection frame rate cap: max 15 FPS, audio chunks at fixed 50 Hz. Rejects beyond these rates. |
| Input validation | Frame size capped at 640×480 (scaled from browser capture). Audio chunk size bounded to 320 samples (20ms @ 16kHz). Reject oversized payloads immediately. |
| IP boundary | No SSH/tailnet exposure needed for testers — only the Tailscale Funnel HTTPS endpoint is shared. Source code and weights never leave the Jetson filesystem. |
| Denial of service | Hard limit: 10 concurrent WebSocket connections. Connection idle timeout: 30 minutes. Memory bounded per-connection buffers (500ms audio cap). |

---

## Task Breakdown — 4 Subtasks

### Subtask 1: MEE Remote Backend Server
**Description**: Build the WebSocket server that sits between the browser client and EmotionEngine. Wraps camera/audio frames into `EmotionEngine.process()` calls. Returns JSON results to connected clients.

**Files to create/modify**:
- `mee/remotedemo/server.py` — WebSocket server (main entry point) ~200 lines
- `mee/remotedemo/config.py` — configuration loader for token, port, rate limits ~40 lines
- `mee/remotedemo/__init__.py` — package init with exported functions ~10 lines
- `requirements.txt` — append remotedemo deps (if any beyond existing)

**Key symbols/lines in existing code to reference**:
- `EmotionEngine` at `mee/api/engine.py:84` — create engine instance in server startup
- `MEEConfig` at `mee/api/engine.py:23` — pass through to engine constructor
- `EMOTION_LABELS` at `demo/emotion_demo.py:47` — reuse emotion label constants for output formatting

### Subtask 2: Browser Client (Single HTML File)
**Description**: A self-contained `remotedemo/index.html` that implements all UI requirements. No build tools, no framework dependencies — plain HTML + CSS + vanilla JavaScript. Works in Chrome/Edge/Safari on desktop.

**Files to create**:
- `mee/remotedemo/index.html` — complete browser client ~600 lines

**Key requirements mapping** (from TASK_REQUEST.md):
| Req # | Description | UI Element |
|-------|-------------|-----------|
| 1 | Browser access, no install | Single HTML file served by backend |
| 2 | Camera + live preview | `<video>` element with stream |
| 3 | Microphone access | getUserMedia audio track (hidden) |
| 4 | Start/Stop controls | Two buttons: "Start Test" / "Stop Test" |
| 5-6 | Frame/audio transport | Canvas capture → WebSocket binary frames; MediaRecorder → binary audio chunks |
| 7 | Facial expression results | Bar chart section for face emotions |
| 8 | Voice emotion results | Bar chart section for voice emotions |
| 9 | Fused affective state | Large highlighted result card |
| 10 | Confidence scores | Included in bar charts + raw score display |
| 11 | Temporal trend | Trend arrow emoji + text (stable/improving/declining) |
| 12 | Connection status | Green/amber/red indicator dot + connection state label |
| 13 | Latency/performance | Last latency value + rolling average |
| 14 | Active cam/mic indicators | Red LED dots that toggle during recording |
| 15 | Graceful error handling | Status messages for disconnect, permission denied, backend errors |

**Transport in browser**:
- Camera: `canvas.captureStream()` → JPEG snapshot every ~67ms (~15 FPS) → binary WebSocket frame (prefix with frame type byte + length)
- Audio: MediaRecorder → Ogg/Vorbis chunks → base64-encoded JSON payload over WebSocket
- Result reception: JSON per-message format `{type: "result", data: <MEE result dict>}`

### Subtask 3: Tailscale Funnel Integration & Deployment Docs
**Description**: One-shot setup script and documentation for deploying the demo to the Jetson. Covers Tailscale Funnel configuration, auto-start via systemd, and token management.

**Files to create**:
- `mee/remotedemo/setup_funnel.sh` — automated Tailscale Funnel + systemd service creation ~60 lines
- `docs/remotedemo/DEPLOYMENT.md` — step-by-step deployment guide ~150 lines
- `docs/remotedoo/ACCESS.md` — how Mr. Xu's team accesses the demo from China ~80 lines

### Subtask 4: Testing & Security Documentation
**Description**: Automated tests for the backend server, end-to-end local testing script, security/IP-boundary documentation, and test procedure for remote access validation.

**Files to create**:
- `tests/test_remotedemo_server.py` — unit tests for server config parsing, token validation, rate limiting logic ~200 lines
- `tests/test_remotedemo_e2e.py` — end-to-end local test (headless browser simulation via pytest) ~150 lines
- `docs/remotedoo/SECURITY.md` — security/IP-boundary documentation ~120 lines

---

## Implementation Notes for Subtask-Specific Guidance

### Subtask 1: Server (`mee/remotedemo/server.py`)

```
File: mee/remotedemo/server.py
Lines ~1-30:     imports (asyncio, websockets, json, os, time, logging)
Lines ~31-60:    RemotedemoConfig dataclass (token, port, max_connections, fps_limit, audio_chunk_ms)
Lines ~61-90:    connection pool + rate limiter logic
Lines ~91-150:   WebSocket message handler coroutine — decode frame type, validate token, cap frame rate
Lines ~151-200:  MEE engine invocation — convert frame bytes → numpy array, call engine.process()
Lines ~201-230:  Result serialization → JSON via WebSocket send back to client
Lines ~231-260:  Graceful shutdown — close connections, release resources
```

### Subtask 2: Browser Client (`mee/remotedemo/index.html`)

```
File: mee/remotedemo/index.html  
Lines ~1-40:     HTML structure — video element, controls div, status bar, result panels
Lines ~41-80:    CSS — grid layout for camera preview + results, active indicators, status colors
Lines ~81-150:   Camera init — navigator.mediaDevices.getUserMedia({video:true, audio:true})
Lines ~151-220:  WebSocket connection — URL construction, token auth first message
Lines ~221-300:  Frame capture loop — canvas.captureStream(), createImageBitmap(), JPEG encode → send
Lines ~301-370:  Audio capture — MediaRecorder on mediaStream, binary chunks → base64 JSON → send
Lines ~371-440:  Result renderer — parse MEE dict, update DOM bars/status/trend/latency
Lines ~441-480:  Error handlers — permission denial (user visible banner), disconnect (reconnect logic)
```

### Subtask 3: Deployment

- systemd service file goes in `mee/remotedemo/mee-remotedemo.service` (~30 lines)
- setup_funnel.sh uses `tailscale funnel :<port>` command — verified syntax with `tailscale help` on the target Jetson
- Tailscale Funnel requires account-type "individual" (not team) — confirm on Jetson before automation

### Subtask 4: Testing

- Use `pytest-asyncio` for WebSocket server tests (may add to pyproject.toml dev deps)
- For browser client testing, use a minimal headless Python HTTP test harness that emulates WebSocket connection without actual browser
- E2E test runs local backend + simulated WebSocket client on the same Jetson

---

## Acceptance Criteria

1. **Remote access**: Mr. Xu's team can open the Tailscale Funnel URL from any computer in China, grant camera/mic permissions, and see live MEE results — no SSH, no software installation
2. **Camera + audio transport**: Frames stream at 5-15 FPS; audio streams continuously; both survive transient network interruptions with graceful degradation
3. **MEE integration**: Results match the EmotionEngine output contract exactly (face/voice/overall/trend/latency_ms)
4. **Security boundary**: Tester cannot access MEE source, model weights, filesystem, SSH, or internal services from the browser client — all interactions are via the explicitly exposed WebSocket endpoint only
5. **No build tools**: Browser client is a single HTML file; server has no build step
6. **Tests pass**: All automated tests for subtasks 1 and 4 pass
7. **Documentation complete**: DEPLOYMENT.md, ACCESS.md, and SECURITY.md present

---

## Dependencies Between Subtasks

Subtask 2 depends on: None (can be coded against the protocol spec; server handshake is documented)
Subtask 3 depends on: Subtask 1 (needs working server to deploy)
Subtask 4 depends on: Subtask 1 (needs server for tests)

**Recommended execution order**: Subtask 1 → Subtask 2 (parallelize with Subtask 1) → Subtask 3+4 (after 1+2 complete)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Tailscale Funnel requires team account for HTTPS endpoint | Low | Medium | Verify on Jetson first; fall back to self-signed cert + http:// if needed with a warning banner |
| Browser getUserMedia requires HTTPS or localhost | Confirmed high | High | Tailscale Funnel provides HTTPS; no workaround needed |
| China firewall blocks Tailscale | Medium | High | **FALLBACK**: Provide alternative — reverse proxy via an intermediate VPS (contabo-vps in tailscale) as bridge. contabo-vps is available on tailnet (see runtime context). Document both paths. |
| Large frame sizes kill bandwidth | Medium | Medium | Client caps at 640×480 JPEG; auto-adjusts quality based on detected bandwidth |
| Jetson CPU load from concurrent MEE inference + WS server | Low | Low | Server runs engine synchronously per frame (non-concurrent); engine is already optimized |

---

*CTO G1 plan complete. Gate G2 (review) pending Reviewer verification. Gate G3 (approve/reject) pending CTO decision on reviewer findings.*
