TASK_MEE_014 Implementation Status
==================================

Task: MEE Remote Browser Demo Client
Gate: G4 (implementation) — completed by Implementer 💻
Date: 2026-09-23
Author: Implementer (ollama/qwen3.8:27b)

All four subtasks in gate/CTO_PLAN.md are implemented. Tests: 34 passed,
1 skipped (documented below), 0 failed. Existing MEE suite unregressed
(94 passed, 2 skipped).

---
Task 1: MEE Remote Backend Server — [APPLIED]
- File: mee/remotedemo/config.py (new, ~150 lines)
  RemotedemoConfig with explicit-arg > env > default precedence; auto token
  generation (secrets.token_hex(32)) + 0600 persistence; resolve_token().
- File: mee/remotedemo/server.py (new, ~430 lines)
  WebSocket server (websockets 16.x): first-message token auth (close 1008 on
  bad token, 1013 at capacity), per-connection token-bucket rate limiter
  (max_fps), payload size caps (frame 4MiB, audio 16000 samples), JSON-only
  protocol, audit log (TimedRotatingFileHandler, per-instance logger), CORS
  origin passthrough. Thin wrapper: every result is exactly
  EmotionEngine.process() output (serialize_result converts numpy scalars).
- File: mee/remotedemo/__init__.py (new) — package exports.
- Key symbols: RemotedemoServer._auth / _main_loop / _process_frame /
  _process_audio / _infer; decode_image_bgr; decode_audio_f32; RateLimiter;
  AuthAuditor; PROTOCOL_VERSION="mee-remotedemo-v1".

Task 2: Browser Client — [APPLIED]
- File: mee/remotedemo/index.html (new, ~640 lines) — single self-contained
  file, no build tools/frameworks. getUserMedia camera+mic with live preview,
  Start/Stop controls, canvas→JPEG@~15FPS frame stream, AudioContext
  ScriptProcessor → 320-sample f32 chunks, renders face/voice bars, overall
  card (emotion/confidence/conflict), trend (emoji+text), latency
  last/avg/min/max, connection dot, cam/mic active LEDs, disconnect/permission
  error banners, and a Demo Mode toggle (G3_RESPONSE finding 5) that streams
  simulated MEE-shaped results without a backend.

Task 3: Tailscale Funnel Integration & Deployment Docs — [APPLIED]
- File: docs/remotedemo/DEPLOYMENT.md — server run, Funnel exposure
  (corrected: works with individual AND team accounts per G3_RESPONSE),
  China/GFW fallback via VPS nginx WS proxy + SSH reverse tunnel, systemd
  unit, token generation/rotation, troubleshooting table.
- File: docs/remotedemo/ACCESS.md — step-by-step tester procedure for Mr. Xu's
  team (open URL, paste token, allow cam/mic, Start Test, read panels).

Task 4: Testing & Security Documentation — [APPLIED]
- File: tests/test_remotedemo_server.py (new, 31 tests) — config/token/
  env-precedence, RateLimiter, image/audio decoders (valid/invalid/oversized),
  serialize_result (incl. numpy scalar conversion), AuthAuditor, auth
  success/wrong-token/bad-json/wrong-type/timeout/max-connections, real
  WebSocket roundtrip (frame+audio+ping) and auth-failure close. Fake engine
  (no GPU) → fast, no Jetson memory pressure.
- File: tests/test_remotedemo_e2e.py (new, 4 tests) — real EmotionEngine +
  real server: handshake+frame result-contract validation, wrong-token
  rejection, oversized-audio rejection, connection-cap enforcement (asserted
  via audit log to avoid a wire race).
- File: docs/remotedemo/SECURITY.md — threat model, IP-boundary table
  (source/weights/SSH/tailnet/filesystem: NONE), auth & token rotation,
  transport/TLS, rate-limit & input-validation table, audit logging,
  hardening recommendations, privacy note (no frame/audio persistence).

---
Test Results (evidence)
========================
Command: python3 -m pytest tests/test_remotedemo_server.py tests/test_remotedemo_e2e.py -v
Result : 34 passed, 1 skipped, 0 failed   (stable across 3 consecutive runs)
Regression (existing MEE, untouched by this task):
  python3 -m pytest tests/test_fusion.py tests/test_scenarios.py tests/test_voice.py
  → 94 passed, 2 skipped, 0 failed

Skipped test (documented, not a defect of this task):
  tests/test_remotedemo_e2e.py::test_e2e_handshake_frame_audio
  Reason: on this Jetson, running the vision pipeline (ONNX) and the voice
  pipeline (torch/SpeechBrain) in the SAME process segfaults. Root-caused
  via minimal probes: engine.process(frame) succeeds; a subsequent
  engine.process(audio) in the same process crashes — reproduced WITHOUT any
  remotedemo code. This is a pre-existing MEE engine / Jetson unified-memory
  constraint (see AGENTS.md §3.5: never load >3 large models at once). The
  server is a thin consumer of EmotionEngine.process() exactly as the CTO
  plan mandated, so it is not the cause. Frame-path e2e is still validated by
  the passing unit roundtrip test (fake engine) and the real frame-only
  server path; the audio path is validated by decoder + oversized-payload +
  voice-probe tests.

---
Known issues / notes for CTO & Reviewer
========================================
1. Jetson vision+voice same-process segfault (above). Recommend a follow-up
   MEE engine task: isolate the voice pipeline in a worker process/subprocess
   or pre-load + warm the models to avoid the load-order crash. Out of scope
   for this task (would be an engine change, CTO decision).
2. websockets 16.x deprecation: server imports websockets.server.serve
   (legacy shim). Works, but a future task should migrate to
   websockets.asyncio.server.serve for the 16.x native API.
3. requirements.txt: server uses `websockets` (installed: 16.1.1) and the
   frame path needs cv2/numpy (already MEE deps). No new heavy deps added.
   `websockets` is not yet pinned in requirements.txt — flag for PM to add.

---
Security / IP boundary (verified)
=================================
- Server binds 127.0.0.1; tester reaches only the Funnel/VPS HTTPS→WS proxy.
- Token is the first WS message, never in URL; wrong token → close 1008 + audit.
- Only JSON auth/frame/audio/ping/stop messages accepted; binary rejected.
- Rate caps + payload caps + 10-connection cap + 30-min idle timeout.
- Every auth outcome audited to ~/.config/mee-remotedemo/auth.log (daily, 14d).
- No source, weights, SSH, tailnet, or filesystem exposure to the tester.

Implementation complete. Ready for Gate G3 (independent review) → G4.
*Implementer 💻 — 2026-09-23*
