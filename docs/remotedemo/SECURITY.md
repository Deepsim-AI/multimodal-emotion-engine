# TASK_MEE_014 — Security & IP-Boundary Documentation

This document describes the security design and the intellectual-property (IP)
boundary of the MEE Remote Browser Demo. It is the authoritative reference for
what a remote tester can and cannot see, and how the prototype is protected.

## Threat model

The demo is a **controlled prototype**, not a production public API. The threat
model is deliberately narrow:

- **Threat actor**: an untrusted remote tester (Mr. Xu's team) with only a
  browser and the shared URL + token.
- **Assets to protect**: MEE source code, model weights, the Jetson filesystem,
  internal network services, SSH access, Tailscale tailnet membership.
- **Out of scope**: nation-state adversaries, sophisticated network attacks,
  multi-tenant abuse. The prototype is not exposed to the open internet beyond
  a single Funnel/VPS endpoint and is used by a known, vetted party.

## IP boundary (what the tester NEVER receives)

| Asset | Exposure | Mechanism |
|-------|----------|-----------|
| MEE source code | **None** | Server runs on the Jetson; only JSON results cross the wire. The browser client is a generic renderer that ships with no MEE code. |
| Model weights (ONNX/RavNet) | **None** | Loaded in-process on the Jetson by `EmotionEngine`; never serialized or sent. |
| Jetson filesystem | **None** | No file-serving endpoint. The browser client is a single static `index.html`; the WebSocket endpoint accepts only auth/frame/audio/ping/stop messages. |
| SSH | **None** | Port 22 is not exposed to the tester. Only the demo port (via Funnel/VPS) is reachable. |
| Tailscale tailnet | **None** | The tester is never added to the tailnet. Access is via a Funnel public URL (or VPS proxy) — no Tailscale client required on the tester's machine. |
| Internal services | **None** | The server binds to `127.0.0.1`. It is not reachable from the LAN or internet except through the single explicit proxy path. |

**Bottom line**: the only thing that crosses the network boundary is a small
JSON result object plus the tester's own camera/mic bytes. Nothing about the
engine, its models, or the host is ever disclosed.

## Authentication & access control

- **Shared access token** (`secrets.token_hex(32)`), auto-generated on first
  boot and persisted to `~/.config/mee-remotedemo/token` (mode 0600).
- Token is the **first** WebSocket message: `{"type":"auth","token":"***"}`.
  Any other first message is rejected with close code `1008`.
- Token is **not** in the URL, so it does not leak into browser history,
  Referer headers, or server access logs of the proxy.
- Wrong/missing token → immediate close, audited.
- **Rotation**: delete the token file and restart the server to force a new
  token. Share the new token with the tester.

## Transport security

- **TLS is mandatory**: browser `getUserMedia` (camera/mic) only works on
  `https://` (or `localhost`). The Funnel/VPS endpoint terminates TLS.
- **WebSocket** carries the authenticated, frame/audio/result traffic.
- The server binds to `127.0.0.1` — there is no direct LAN or internet path
  to it without the proxy.

## Rate limiting & input validation

| Control | Limit | Rationale |
|---------|-------|-----------|
| Concurrent connections | 10 | Bounds server memory + inference load. |
| Per-connection frame rate | 15 FPS (token bucket) | Matches engine throughput; rejects bursts. |
| Audio chunk size | ≤ 16000 samples (1 s @ 16 kHz) | Bounds decode cost. |
| Frame payload size | ≤ 4 MiB | Rejects oversized images. |
| Idle timeout | 30 min | Reclaims abandoned sessions. |
| Auth timeout | 5 s | Prevents slow-loris style auth stalls. |
| Binary WS frames | Rejected | Enforces the JSON-only protocol. |

All rejections are audited with client IP + reason.

## Audit logging

- Every auth outcome (success, failure, timeout, cap-reject) is appended to
  `~/.config/mee-remotedemo/auth.log`.
- Daily rotation, 14 days retained (`TimedRotatingFileHandler`).
- Format: `<timestamp> client=<ip> outcome=<result> <detail>`.

## Hardening recommendations (before wider rollout)

The following are **out of scope for the prototype** but recommended before any
broader exposure:

1. **Per-tester tokens** instead of a single shared token, so sessions can be
   individually revoked and attributed.
2. **mTLS or a short-lived signed cookie** issued after token auth, to bound
   token reuse.
3. **IP allow-list** on the Funnel/VPS endpoint if the tester's network is
   stable.
4. **Request size + rate limiting at the proxy** (nginx) as a first line of
   defense in front of the Python server.
5. **CSP + minimal static hosting** for `index.html` (the current file is
   self-contained, but hosting it behind the same origin as the WS is
   preferable to a separate static host).
6. **Automated token expiry** (e.g. 7 days) for shared tokens.
7. **Metrics/alerting** on auth-failure rate to detect brute-force attempts.

## Compliance note

This prototype collects camera + microphone data in transit for emotion
estimation only. The server does **not** persist frames or audio — they are
decoded, passed to `EmotionEngine.process()`, and discarded. No biometric
storage occurs. Confirm local privacy requirements before enabling the mic
path for any regulated use.

---

*Prototype-grade security. See `DEPLOYMENT.md` for operational steps and
`ACCESS.md` for the tester procedure.*
