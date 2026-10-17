# CTO Plan — TASK_MEE_015: Fix WebSocket Disconnect + Scenario-Aware Face Demo

**Task ID:** TASK_MEE_015  
**Gate:** G1 — Plan Approval Pending  
**Phase:** Phase 7 (Production Patch for Remote Demo)  
**Date:** 2026-09-25  
**Planned By:** CTO / Architect  

---

## 1. Objective

Fix two blockers in the MEE Remote Demo (TASK_MEE_014):
1. **"Connection closed" persists** — WebSocket drops despite ping_interval fix and client-side ping loop
2. **No scenario-aware handling** — demo doesn't distinguish between camera-only, mic-only, or both inputs

---

## 2. RetinaFace Status — HOLDING

| Component | Status | Notes |
|-----------|--------|-------|
| RetinaFace model (`retinaface.h5`) | ✅ Downloaded (114MB) at `/home/deepsim/.deepface/weights/` | |
| CUDA libraries | ✅ Installed (CUDA 12.6 + TensorRT 10.3) | |
| PyTorch | ❌ `2.14.0+cu130` built for CUDA 13.0 | L4T R36.4 kernel only supports up to CUDA 12.x → `CUDA: False` |
| Device nodes | ✅ `/dev/nvhost*`, `/dev/nvmap` exist | But PyTorch's version check blocks GPU access |

**Decision: HOLD RetinaFace fix for now.** This task focuses on the WebSocket disconnect and UI scenario handling first. We'll investigate CUDA compatibility (PyTorch downgrade vs recompilation) as a separate follow-up.

---

## 3. Issue 1 — "Connection closed" Persisting

### Root Cause Analysis

We applied three fixes earlier:
| Fix | File | What |
|-----|------|------|
| Server-side keepalive | `server.py:218` | `ping_interval=20` in websockets `serve()` call |
| Client-side ping | `index.html:428-438` | Sends WebSocket ping every 15s from browser |
| Tailscale Funnel | — | Proxying :443 → :8910 |

### The Problem Persists

You confirmed: **"Connection closed. Check URL/token and reconnect"** still appears in the demo UI, meaning the WebSocket is still being dropped despite both sides sending pings. This could be caused by:

**Possibility A: Tailscale Funnel idle timeout (60s)**
- Funnel has its own WebSocket idle timeout that may override websockets' `ping_interval`
- Even with pings, if the **application-level payload is silent**, Funnel may kill the connection before websockets can re-establish

**Possibility B: Token expiration or URL change**
- The `/home/deepsim/.config/mee-remotedemo/token` file could be stale
- Tailscale hostname resolution might intermittently fail

**Possibility C: Jetson network power management**
- The Orin's WiFi/Ethernet driver may have aggressive power-saving that drops connections

### Diagnosis Steps for Implementer

Before adding more ping layers, we need to **identify which layer is dropping**:

```bash
# Check if Funnel sees the connection as alive
cat /tmp/mee-funnel.log  # Look for disconnection entries

# Check if ws server still receives pings
grep "pong\|ping" /tmp/mee-ws.log 2>/dev/null | tail -5

# Check network power management
cat /sys/module/8192eus/parameters/ant_switch 2>/dev/null || true
ethtool --show-pipe 0.0.0.0:8910 2>/dev/null || true
```

**Implementer action:** Add debug logging to the server's WebSocket handler to record ping/pong timestamps and connection close reasons. This tells us *where* the drop happens.

### Fix Strategy (depends on diagnosis):

| If cause | Fix |
|----------|-----|
| Tailscale Funnel kills idle WS | Increase `ping_interval` to 10s, add **application-level heartbeat** (server sends small `{_ping: true}` every 30s) |
| Token expired | Auto-regenerate or extend token validity in `config.py` |
| Network power management | Disable WiFi power saving: `iw dev wlan0 set power_save off` |

---

## 4. Issue 2 — Scenario-Aware Browser UI (No Changes to Face Detection)

### Requirement

The face demo must clearly display which channels are active vs. dead:

| Scenario | Expected Display |
|----------|-----------------|
| Camera only (no voice) | "📷 face only" + green cam indicator, muted mic |
| Voice only (no camera) | "🎤 voice only" + green mic indicator, muted cam |
| Both active | "🎬 both" + both indicators green |

### Implementation Plan for index.html

**1. Add channel status indicators** in the existing HTML (~after streamBanner div):

```html
<!-- Scenario indicators — TASK_MEE_015 Task B -->
<div id="channelStatus" style="display:flex;gap:8px;margin-top:6px;font-size:12px;">
  <span id="camIndicator" class="indicator muted">📷 Camera</span>
  <span id="micIndicator" class="indicator muted">🎤 Mic</span>
  <span id="scenarioLabel" style="color:var(--muted);font-style:italic;">waiting for input</span>
</div>
```

**2. CSS for indicators** (in `<style>` block):

```css
.indicator {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 10px; font-size: 11px;
  transition: background 0.3s, color 0.3s;
}
.indicator.on { background: #2a5a2a; color: #6f6; }
.indicator.muted { background: #333; color: var(--muted); }
```

**3. Update `renderResult()` to set indicators:**

```javascript
// Track channel states over last N messages for debouncing
let camActiveCount = 0, micActiveCount = 0, totalMessages = 0;
const DEBOUNCE = 3; // require 3 consecutive same-state messages

function updateIndicators(data, source) {
    // Debounce: only flip after 3 consecutive messages
    if (data.face && data.face.has_face !== undefined) camActiveCount++;
    else camActiveCount = 0;
    if (data.voice) micActiveCount++;
    else micActiveCount = 0;
    
    $("camIndicator").className = "indicator " + (camActiveCount >= DEBOUNCE ? "on" : "muted");
    $("micIndicator").className = "indicator " + (micActiveCount >= DEBOUNCE ? "on" : "muted");
    
    // Set scenario label based on debounced states
    let scenario;
    const camOn = camActiveCount >= DEBOUNCE;
    const micOn = micActiveCount >= DEBOUNCE;
    if (camOn && micOn) scenario = "🎬 both";
    else if (camOn) scenario = "📷 face only";
    else if (micOn) scenario = "🎤 voice only";
    else scenario = "⏳ waiting";
    $("scenarioLabel").textContent = scenario;
}
```

**4. Update the face panel text to distinguish camera-off vs no-face-in-frame:**

In the existing `renderBars` call for face (~line 276), change:

```javascript
// Before (ambiguous):
face.has_face ? "detected · ..." : "no face detected"

// After (clear):
face.has_face 
    ? "✅ detected · " + face.emotion + " · " + Math.round((face.confidence||0)*100) + "%" 
    : ($("camIndicator").classList.contains("on") 
        ? "📷 no face in frame"  // camera is on but no face
        : "⏳ camera not sending");  // camera stream stopped
```

---

## 5. Acceptance Criteria

### Task A: WebSocket Disconnect Fix
| # | Criterion | Verification |
|---|-----------|-------------|
| A1 | Server logs show ping/pong roundtrips | `grep pong /tmp/mee-ws.log` returns entries |
| A2 | "Connection closed" no longer appears after >3 minutes of streaming | Manual test: stream for 5 min, no disconnect |
| A3 | If Funnel kills connection, auto-reconnect succeeds within 10s | Demo shows reconnecting → connected, not "check URL/token" |

### Task B: Scenario-Aware UI
| # | Criterion | Verification |
|---|-----------|-------------|
| B1 | Channel indicators turn green when their channel is active | Observe live demo |
| B2 | Scenario label updates correctly in all 3 states | Test each scenario individually |
| B3 | "No face" distinguishes camera-off vs no-face-in-frame | Toggle camera, observe text change |

---

## 6. Implementation Order for Implementer 💻

1. **Task 1:** Add ping/pong debug logging to server + diagnose which layer drops the connection
2. **Task 2:** Apply fix based on diagnosis (application heartbeat / token refresh / power management)
3. **Task 3:** Update `index.html` with channel indicators and scenario label

---

## 7. CTO Notes

- **RetinaFace hold:** Do NOT swap to MediaPipe this round. The CUDA mismatch issue needs investigation (PyTorch downgrade vs recompilation vs JetPack reflash) as a separate follow-up task.
- **Disconnect first:** If the WebSocket keeps dying, scenario awareness is moot because there's no data to display. Diagnose and fix disconnect before adding UI complexity.

**Plan submitted for approval.**

---

## 8. Appendix — Voice Pipeline Blocker (Not a Code Bug)

### Discovery: No Audio Input Device Detected

| Check | Result |
|-------|--------|
| PulseAudio sources | All SUSPENDED or monitor-only — no active mic device |
| USB enumeration | No headset/audio devices found on any USB port |
| ALSA cards | Only built-in NVIDIA HDA + APE (no external audio interface) |

**This means the "voice emotion = neutral" on your right panel is not a code issue.** The `getUserMedia()` call in the browser successfully requests a mic, but:

1. If you're using a **USB headset** — it's either unplugged, on a non-functional port, or PulseAudio isn't seeing it
2. If you're using a **Bluetooth headset** — it may not be paired/connected to PulseAudio
3. If the mic hardware is broken — no amount of code will fix it

### Recommendation Before Code Changes:

1. Verify the headset actually produces input by running `arecord` or `pavucontrol` on the Jetson directly
2. If Bluetooth — pair and trust the headset via `bluetoothctl` + PulseAudio profile switch
3. Once a real mic is detected → voice emotion will work (the speech pipeline itself is functional, just gets 0-length audio segments)

---

## Updated Acceptance Criteria (revised for reality)

### Task B: Scenario-Aware UI (still valid — priority unchanged)
| # | Criterion | Verification |
|---|-----------|-------------|
| B1 | Channel indicators turn green when their channel is active | Observe live demo with **any** working input |
| B2 | Scenario label updates correctly in all states | Test each scenario individually |
| B3 | "No face" distinguishes camera-off vs no-face-in-frame | Toggle camera, observe text change |

### Task A: WebSocket Disconnect (still valid)
| # | Criterion | Verification |
|---|-----------|-------------|
| A1 | Server logs show ping/pong roundtrips | `grep pong /tmp/mee-ws.log` |
| A2 | No "Connection closed" after 5 min streaming | Manual test with **camera-only** (face detection holds until CUDA fix) |

---

## Updated Implementation Order for Implementer 💻

1. **Task 1:** Add ping/pong debug logging to server + diagnose WebSocket disconnect
2. **Task 2:** Apply fix based on diagnosis (app-level heartbeat / token refresh / power save)
3. **Task 3:** Update `index.html` with channel indicators and scenario label

**RetinaFace/CUDA: HOLD for separate TASK_MEE_016.**  
**Voice pipeline: BLOCKED by hardware — user must verify headset works on Jetson first.**

