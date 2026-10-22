# Changelog — Multimodal Emotion Engine (MEE)

All notable changes to this project will be documented in this file.

## [v0.2.0] — 2026-10-21

### Added

**MEE_015 — License Integration (Gate C) — v0.2.0 (CLOSED, all gates complete):**
- Full license integration delivered on schedule after G4 APPROVED (all 20 checks pass).
- `mee/licensing/` package (8+ files): `client.py` (LicenseClient activate/verify/status/deactivate), `config.py` (config + TrialConfig with Keygate-feature > env > 14-day precedence), `device.py` (stable persistent device ID), `errors.py` (LicenseExpiredError, ActivationLimitError), `offline.py` (ed25519 verification + base64url decode), `trial.py` (14-day trial lifecycle, immutable marker), `cli.py` (`mee-lic` CLI + entry point), `results.py` (VerificationResult dataclass, 7 fields).
- `mee/api/engine.py` — `_license_check()` gate in `process()`, `_license_status_block()` in `health()` (backward compatible: returns None when no license client).
- `mee/api/license.py` — `license_status()` public wrapper.
- `tools/license_smoke_test.py` — 6-step end-to-end acceptance smoke.
- Entitlement model: Keygate feature-map driven, single code path, no `plan_name` matching (extensibility-compliant); unknown features stored-but-ignored; missing entitlements default to disabled.
- Offline fallback via ed25519 (verified on host; `cryptography` already transitive, no new dependency).
- **Tests:** 80 licensing tests (22 client, 16 config, 5 device, 10 trial, 7 offline, 3 security, 8 CLI) + 9 engine-integration tests + 6 E2E smoke; 170 regression tests pass (5 pre-existing skips unchanged). Frozen contracts 0-line diff.
- LICENSE alignment: `LICENSE.txt` (Deepsim Commercial Software License v1.1) canonical; `LICENSE_1.0` retained.
- Version bump: 0.1.0 → 0.2.0 (minor — new licensing capability).
- Phase 7 (License Integration, Gate C) now COMPLETE. Remote push pending user confirmation of target URL + branch.

### Changes

- `pyproject.toml` version: `0.1.0 → 0.2.0`.

## [Unreleased]

### Added

**MEE_015 — License Integration (Gate C) — v0.2.0 (2026-10-21, CLOSED):****
- G0 intake complete. `docs/development/reports/TASK_MEE_015/GATE_C_SPECIFICATION.md` — 27 testable requirements (R1–R27).
- License of record: `LICENSE.txt` (Deepsim Commercial Software License v1.1, October 2026). `LICENSE_1.0` retained for reference.
- Owner decisions: 14-day trial → hard stop; Keygate server-side activation cap (`max_activations=3`) is the device-limit authority; client reports a stable device ID.
- Planned: `mee/licensing/` package (client, config, device, errors, offline, trial, cli) + `EmotionEngine` integration + `mee-lic` CLI + unit/integration/E2E tests.
- Version bump planned: 0.1.0 → 0.2.0 (minor — new licensing capability).
- Status: awaiting CTO G1 (`CTO_PLAN.md`).

**Model Storage Consolidated to a Canonical `models/` Tree + Resolver Layer (2026-10-17):**
- All production weights now live under `<repo>/models/` (`vision_emotion/`, `voice/`, `voice_gpu/`) — no longer scattered per-library home caches (`~/.emotiefflib/`, `~/.insightface/...`).
- `tools/download_models.py` (new) — one command populates + verifies `models/` on a fresh host (idempotent; `--mirror` copies existing local weights; `--link` restores legacy backend symlinks).
- `mee/api/engine.py` — `MEEConfig` defaults resolve `model_root`/`vision_model_path`/`voice_model_path` to the canonical tree (helpers `_default_model_root`/`_sub_model_dir`; env `MEE_MODEL_ROOT` / `MEE_VISION_MODEL_PATH` / `MEE_VOICE_MODEL_PATH` override; falls back to `None` if the dir is absent).
- `mee/vision/emotion_model.py` — `_stage_weights()` stages an explicit `model_path` into EmotiEffLib's hardcoded `~/.emotiefflib/` cache (which has no env override) before load.
- `mee/voice/voice_worker_client.py` — accepts `model_path`, exports `MEE_VOICE_MODEL_PATH` into the worker env; `mee/voice/voice_worker.py` builds the `EmotionModel` from it.
- `docs/MODELS.md` + `models/README.md` — canonical layout + resolver layer; `README.md`, `docs/JETSON_DEPLOYMENT.md`, `PROJECT_STATUS.md` updated to the new layout.
- `.gitignore` — keeps `models/README.md` + the small ONNX graph; ignores weight binaries.

**Remote Demo — Voice in a Separate Worker Process + Mic-Silence Diagnostics (2026-10-17):**
- Root-caused two remote-demo voice issues: (a) the browser's `{type:"mute"}` mic-toggle message was unhandled and rendered as a `"Server error"` banner; (b) on this Jetson, loading the SpeechBrain/torch voice runtime and the MediaPipe vision runtime in the *same* process **segfaults** (native C-runtime collision — verified each works alone, combined load dumps core).
- `mee/voice/voice_worker.py` (new) — out-of-process voice worker: loads the voice runtime, speaks newline-delimited JSON over stdin/stdout, never imports the vision stack.
- `mee/voice/voice_worker_client.py` (new) — thread-safe client that spawns/drives the worker, serializes audio as base64, returns a result dict; degrades gracefully if the worker can't start.
- `mee/api/engine.py` — `MEEConfig.voice_enabled` (env `MEE_VOICE_ENABLED`); voice now routes through the worker client (`_ensure_voice_worker`) so camera + mic recognition are **both available at once**; `shutdown()` releases the worker.
- `mee/remotedemo/server.py` — added `mute`/`unmute` branch that acks the client's mic-toggle with `mute_ok` (no more `unknown message type 'mute'` / "Server error").
- `mee/remotedemo/index.html` — **live mic-level meter** next to the Microphone indicator, and the voice panel now distinguishes `🎤 mic silent (no voice energy…)` from a real low-confidence result (fixes the ambiguous "no voice data").
- `mee-remotedemo-start.sh` — PID-file + port-kill cleanup (replaces the aarch64-unreliable `pkill` bracket idiom), `wait_port` verification, exports `MEE_VOICE_ENABLED=1`.
- `mee-remotedemo-stop.sh` (new) — companion stop script (watchdog first, then by PID, then release ports 8910/8443).
- Docs updated: `docs/remotedemo/DEPLOYMENT.md`, `docs/remotedemo/ACCESS.md`, `docs/DEMO.md` (voice-worker isolation, stop script, mic-silence troubleshooting).

### Notes

- **Voice isolation is the enabling fix for both channels on this host.** The worker process keeps the SpeechBrain/torch and MediaPipe runtimes in separate address spaces, which is what makes camera + mic work together. `MEE_VOICE_ENABLED=0` disables voice.
- The "no voice data" symptom was confirmed to be a **silent mic track** (146/148 segments `mean_abs < 0.01`), not a pipeline bug — most often the browser blocking `getUserMedia` on the self-signed `https://` origin. The new mic-level meter + `WS-KA-audio mean_abs` log line let the operator verify it.

**Remote Demo Public Access Migration to Pangolin (TASK_MEE_035):**
- Public access moved from **Tailscale Funnel** (`jetson-agx.tail0d394d.ts.net`) to **Pangolin** on `deepsim.ai`: page `https://mee.deepsim.ai:8443/`, WebSocket `wss://meews.deepsim.ai:8443/`
- `index.html` — default Server URL is now `wss://meews.deepsim.ai:8443/` (auto-filled); dead Tailscale-Funnel default removed; `meews`/`mee` host branch added; placeholder updated
- `mee-remotedemo-start.sh` — 3-step start (WS → page → watchdog); Funnel demoted to optional legacy; prints new public URLs + live `/healthz` check
- `docs/remotedemo/ACCESS.md`, `DEPLOYMENT.md`, `SECURITY.md` — public path rewritten to Pangolin; Funnel marked deprecated/legacy

**Remote Demo Public Access & Stability (TASK_MEE_018):**
- `server.py` — public funnel now serves the client page (`GET /`) and `GET /healthz` on the same port as the WS upgrade (`_http_endpoint`); `GET /token` **removed** (token handed out-of-band only)
- `server.py` — CPU thread cap (`MEE_DEMO_MAX_THREADS`, default 2) applied before engine construction to tame inference CPU spikes on Jetson (`run_server()`)
- `server.py` — startup banner with PID (`TASK_MEE_034`) + signal diagnostics for SIGTERM/SIGINT/SIGABRT (`TASK_MEE_035`, `_install_signal_diagnostics()`)
- `index.html` — reconnect hardening (12 attempts → infinite 30 s retry), client-side ~10 FPS throttle, `rate_limited` banner silenced, manual token entry (no auto-fetch)
- `https_server.py` (new) — HTTPS static page on 8443 (self-signed cert)
- `mee-ws-watchdog.sh` (new) — auto-restarts the WS server within ~5 s if the listener disappears
- `mee-remotedemo-start.sh` — 4-step startup (WS → page → funnel → watchdog) with labeled PUBLIC vs TAILNET URLs
- `docs/remotedemo/ACCESS.md` + `docs/remotedemo/DEPLOYMENT.md` — public funnel URL primary, manual token entry, watchdog/stability/troubleshooting

**Detection Frequency Decoupling (TASK_MEE_013):**
- `detect_every_n_frames` knob in `VisionProcessor` (`mee/vision/processor.py`) and `MEEConfig` (`mee/api/engine.py`)
- Decouples Stage-1 face-detection frequency from emotion-pass frequency: detection runs once and its result (bbox + landmarks) is reused for the next `n-1` passes, then re-detected
- Default `1` preserves original per-call detection behavior exactly (backward compatible)
- Cache invalidated by frame identity/shape change; `force_detection=True` bypasses cache
- Addresses the TASK_MEE_012 finding that CPU-only retina-face detection (~1 s/face) gated end-to-end throughput
- 8 new focused tests + existing suite green (20 passed, 2 skipped)

### Notes

- MEE_013 is an orchestration-layer optimization only; no changes to `deepefflib`/emotion model, alignment, or detector backends (G1 gate freeze respected)

## [v0.1.0] — 2026-09-23

### Added

**Remote Browser Demo Client (TASK_MEE_014):**
- `mee/remotedemo/server.py` — WebSocket server (token auth, rate limiting, CORS, audit log)
- `mee/remotedemo/config.py` — configuration with token auto-generation
- `mee/remotedemo/index.html` — browser client (live preview, frame/audio streaming, result rendering, Demo Mode)
- `tests/test_remotedemo_server.py` — 31 unit tests
- `tests/test_remotedemo_e2e.py` — 4 e2e tests (1 skipped due to pre-existing Jetson constraint)
- `docs/remotedemo/DEPLOYMENT.md` — deployment guide (Tailscale Funnel + China fallback)
- `docs/remotedemo/ACCESS.md` — tester procedure for remote users
- `docs/remotedemo/SECURITY.md` — threat model and IP boundary documentation
- G5 closure: local commit only — remote push deferred pending user confirmation of target repository/branch

**Temporal State Tracking (TASK_MEE_007):****
- `mee/state/history.py` — EmotionHistory fixed-window ring buffer
- `mee/state/estimator.py` — analyze_trend() deterministic classifier
- Engine integration via _compute_trend() in process() output under "trend" key

**Packaging & Documentation (TASK_MEE_011):**
- LICENSE file (Apache-2.0)
- requirements.txt generation from pyproject.toml deps
- README.md with install, usage, architecture overview, limitations, disclaimer
- docs/THIRD_PARTY_LICENSES.md — complete third-party component inventory
- EmotiEffLib-based vision pipeline (replaces InsightFace buffalo_l)

**End-to-End Validation (TASK_MEE_009):**
- `tools/evaluate_scenarios.py` — Runnable end-to-end evaluation harness
- `tests/scenario_data.py` — Scenario definitions (5 standardized scenarios: Neutral, Happy, Sad, Frustrated/Conflict, Cross-over)
- `tests/test_scenarios.py` — 38 tests validating full pipeline integration via monkey-patched process()
- `docs/TEST_PROTOCOL.md` — Evaluation methodology, expected results, pass/fail criteria
- Full suite: 106 tests (was 68 → +38 new, zero regressions)

**Jetson AGX Orin Deployment (TASK_MEE_010):**
- `tools/export_models.py` — SpeechBrain IEMOCAP + Wav2Vec 2.0-base export utilities
- `tools/build_trt_engine.py` — TensorRT engine builder with 3 fallback paths
- `tools/bench_jetson.py` — Performance benchmark harness (5-component timing)
- `tools/run_stability_test.py` — Extended stability runner with crash + drift detection
- `docs/JETSON_DEPLOYMENT.md` — Complete deployment guide (8 sections, hardware/software/perf/limitations)
- `mee/voice/emotion_model.py` — INT8 TensorRT auto-detection and graceful fallback
- `tests/helpers.py` — Jetson environment detection helper (`is_jetson()`)
- Test updates with `@pytest.mark.skipif` markers for non-Jetson hosts

**Emotion Demonstration UI (TASK_MEE_008):**
- `demo/emotion_demo.py` — Single-file Streamlit demo driving the public EmotionEngine API (589 lines)
- Live camera + mic input, real-time face/voice/overall emotion bars, trend indicator, conflict banner, debug JSON panel
- Headless/JSON-output mode for scripted evaluation (`--headless`)
- Graceful degradation when camera/microphone/hardware unavailable (synthetic-input fallback)
- `pyproject.toml` — demo extras: `streamlit>=1.28`, `sounddevice>=0.4`, `opencv-python>=4.8`
- `docs/DEMO.md` — one-page install/run guide (GUI + headless, hardware fallbacks)

**Voice Subsystem (TASK_MEE_005):**
- `mee/voice/recorder.py` — AudioRecorder + MicRecorder for audio capture
- `mee/voice/features.py` — FeatureExtractor (9 acoustic features via librosa)
- `mee/voice/emotion_model.py` — EmotionModel with SpeechBrain RavNet primary + Wav2Vec 2.0 fallback
- `mee/voice/processor.py` — VoiceProcessor pipeline
- Engine integration via `_infer_voice()` in EmotionEngine
- Graceful degradation when speechbrain unavailable
- 13 unit tests (`tests/test_voice.py`)

**Vision Subsystem (TASK_MEE_004):**
- `mee/vision/detector.py` — FaceDetector + Face dataclass (SCRFD via InsightFace)
- `mee/vision/emotion_model.py` — EmotionModel with 7-class prediction
- `mee/vision/processor.py` — VisionProcessor pipeline
- Engine integration via `_infer_vision()` in EmotionEngine
- Graceful degradation when insightface unavailable
- 12 unit tests (`tests/test_vision.py`)

### Changes

**License & Packaging (TASK_MEE_011):**
- MEE application code license changed to Apache-2.0 (from Proprietary)
- EmotiEffLib replaces InsightFace buffalo_l for production facial expression estimation
- Third-party license inventory added to docs/THIRD_PARTY_LICENSES.md

### Documentation
- `docs/MODEL_EVALUATION.md` — Vision and voice model comparison tables
- `docs/ARCHITECTURE.md` — Final architecture documentation (260 lines)
- `docs/TEST_PROTOCOL.md` — Testing methodology and pass/fail criteria

---
*All gates G1→G5 complete for tasks MEE_001 through MEE_011.*
*MEE remains an independent capability, not tied to the AI Companion book or any specific robot.*
