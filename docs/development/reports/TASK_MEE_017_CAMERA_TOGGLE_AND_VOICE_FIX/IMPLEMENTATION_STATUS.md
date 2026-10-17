TASK_MEE_017 Implementation Status
=================================

## Task A: Camera On/Off Toggle ✅

### Task 1: HTML — Camera toggle button
- File: `mee/remotedemo/index.html`
- Added `<input type="checkbox" id="camToggle" checked>` with label and state span
- Placed right after the existing mic-mute toggle in the Connection card
- CSS classes `.cam-toggle-on` / `.cam-toggle-off` added to the `<style>` block

### Task 2: JavaScript — Camera toggle logic
- File: `mee/remotedemo/index.html`
- `let camEnabled = true` state variable added near `micMuted`
- `startStream()` refactored: builds constraints based on `camEnabled` + `micMuted`
  - Both on → one stream, both tracks
  - Camera only → video constraints only
  - Voice only → audio constraints only, video hidden, no capture loop
- `toggleCameraLive()` added: stops/starts the camera track mid-session while
  keeping the mic's ScriptProcessor graph alive
- `stopStream()` updated: restores `preview` display
- `renderResult()` updated: faceMeta shows "📷 camera OFF (enable the camera toggle)"
  when camera is explicitly off, instead of the generic "⏳ camera not sending"
- `updateIndicators()` updated: scenario label respects `camEnabled` toggle —
  camera-off + mic-on → "🎤 voice only (camera OFF)", all-off → "⏳ all channels off"
- `camToggle` change listener: updates `camEnabled` + label class; calls
  `toggleCameraLive()` if the test is running, otherwise just updates state
  for the next `startStream()` call

**Verification:**
- JS syntax: `node --check` equivalent (Function constructor) → OK
- HTML contains `<input type="checkbox" id="camToggle" checked>`
- Toggle state variable `camEnabled` initialized to `true`
- `startStream()` respects `camEnabled` when building constraints

## Task B: Voice Emotion "No Data" Diagnostics ✅

### Task 3: Server-side audio debug logging
- File: `mee/remotedemo/server.py`
- **Root cause identified from code inspection:**
  The voice model (IEMOCAP wav2vec2) requires a minimum audio duration.
  The browser sends 320-sample chunks (20 ms @ 16 kHz). The SpeechBrain
  path runs `avg_pool` which needs `n_steps >= kernel`. With 20 ms of audio,
  `n_steps` is too small → `ValueError` → caught in `predict()` → `_degraded_result()`
  returns `{"emotion":"neutral","confidence":0.0,"scores":all-zeros}`.
  This is the exact signature of the "no data" symptom: confidence = 0.0,
  all bars zero, emotion = "neutral".
  The browser's 20 ms chunks are far too short for the model.

- **Server logging added to `_process_audio`:**
  - Raw audio stats: sample count, mean_abs, max, non-zero ratio (`WS-KA-audio` log line)
  - Result logging: emotion, confidence (`WS-KA-voice` log line)
  - Warning when confidence < 0.01 (`WS-VOICE-WARN` log line)
  - Error on exception with full message (`WS-VOICE-ERR` log line)
  - All four log tags searchable via `grep -E "WS-KA-audio|WS-VOICE" /tmp/mee-ws.log`

### Task 4: Client-side voice panel enhancement
- File: `mee/remotedemo/index.html`
- `renderResult()` voice section: when `confidence < 0.01`, shows
  `⚠️ neutral · 0% (very low confidence — check mic hardware / audio format)`
  with a `title` tooltip explaining the likely root cause
- This replaces the silent "no voice data" with an actionable warning

## Root Cause Summary

**The "no data" voice issue is a fundamental audio-length mismatch.**
The browser sends 20 ms chunks (320 samples @ 16 kHz). The IEMOCAP wav2vec2
model's `avg_pool` requires a minimum number of timesteps that 20 ms of audio
does not produce. Every chunk fails → `_degraded_result()` → confidence=0.0.

**Fix required (Task B is diagnostic; the actual fix is a separate task):**
The browser should accumulate audio into ~2-second buffers before sending,
or the server should buffer incoming chunks and only run inference on
complete segments. This is a design decision for the CTO.

## Files Changed

| File | Changes |
|------|---------|
| `mee/remotedemo/index.html` | Camera toggle (HTML/CSS/JS), voice warning UI, scenario label updates |
| `mee/remotedemo/server.py` | Audio debug logging, low-confidence warning |
