# CTO Plan — TASK_MEE_017: Camera Toggle + Voice Emotion "No Data" Fix

**Task ID:** TASK_MEE_017  
**Gate:** G1 — Plan Approval Pending  
**Phase:** Phase 9 (User Experience + Voice Pipeline Fixes)  
**Date:** 2026-09-26  
**Planned By:** CTO / Architect  

---

## 1. User Reports

### Issue A: Microphone Toggle Exists, But Camera Does Not
**Symptom:** "It is better to add a button on/off camera like the mute micr"
- When microphone is ON → face emotion recognition changes too fast (flashing), hard to read
- When microphone is OFF → face emotion is clear and stable (verified in TASK_MEE_016)
- User needs ability to toggle camera on/off independently to test each modality separately

**Root cause:** The demo currently has a mute-mic toggle, but no equivalent camera toggle. When both channels are active, the UI updates rapidly and makes emotions impossible to read. Adding a camera toggle lets users isolate testing to one channel at a time.

### Issue B: Voice Emotion Shows "No Data" Despite Microphone Working
**Symptom:** "Microphone on the left panel flashing, but right panel displays no data"
- Microphone indicator shows activity (flashing = audio frames being received)
- BUT voice emotion panel shows "no data" (neutral/static)

**Hypothesis (requires investigation):** This could be one of several causes:
1. Audio format mismatch between browser and server (sample rate, channels, encoding)
2. The voice pipeline model returning neutral/empty for the audio format received
3. Server-side processing error being silently swallowed

---

## 2. Implementation Plan

### Task A: Add Camera On/Off Toggle to index.html

**File:** `mee/remotedemo/index.html` — add near existing mute-mic toggle (~line where mic toggle exists)

#### A1. HTML — Add camera toggle button
Place it right before or after the existing mute-mic toggle in the Controls card:

```html
<!-- TASK_MEE_017 Task A: Camera On/Off Toggle -->
<div class="control-row">
    <label for="camToggle" style="cursor:pointer; display:flex; align-items:center; gap:6px;">
        <input type="checkbox" id="camToggle" checked> 
        📷 <span id="camToggleLabel">Camera ON</span>
    </label>
</div>
```

#### A2. CSS — Style for camera toggle
In `<style>` block, add styles to match existing toggle style:

```css
/* Camera toggle */
.control-row { margin-bottom: 8px; }
.cam-toggle-on { color: #6f6; font-weight: bold; }
.cam-toggle-off { color: #999; text-decoration: line-through; }
```

#### A3. JavaScript — Camera toggle logic
Update the camera stream management functions:

```javascript
// NEW: Camera toggle state (in existing variables section)
let camEnabled = true;  // default: camera ON

// UPDATE: startCamera() — only start if toggled on
async function startCamera() {
    if (!camEnabled) return;  // skip if camera is off
    
    try {
        let constraints = { video: { facingMode: "user" } };
        // Add audio constraint only when mic is enabled AND cam is enabled
        if (micMuted) {
            constraints.audio = false;
        } else {
            constraints.audio = true;  // keep existing logic
        }
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        // ... rest of existing camera setup ...
    } catch (err) {
        console.warn("Camera error:", err);
    }
}

// UPDATE: camToggle listener (new)
document.getElementById('camToggle').addEventListener('change', function() {
    camEnabled = this.checked;
    const label = document.getElementById('camToggleLabel');
    
    if (this.checked) {
        label.textContent = "Camera ON";
        label.className = "cam-toggle-on";
        updateScenarioLabel();  // refresh scenario label
        startCamera();  // restart camera stream if needed
    } else {
        label.textContent = "Camera OFF";
        label.className = "cam-toggle-off";
        updateScenarioLabel();  // refresh scenario label
        
        // Stop camera stream
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
            stream = null;
        }
    }
});

// UPDATE: sendFrameLoop() — only send if cam is enabled
function sendFrameLoop() {
    if (!camEnabled || !videoEl?.srcObject) {
        requestAnimationFrame(sendFrameLoop);  // keep looping but don't send
        return;
    }
    
    // ... rest of existing frame capture logic ...
}

// UPDATE: updateScenarioLabel() — respect camera toggle state
function updateScenarioLabel() {
    const camOn = camEnabled && videoEl?.srcObject;
    const micOn = $("micIndicator").classList.contains("on");
    
    if (camOn && micOn) scenario = "🎬 both";
    else if (camOn) scenario = "📷 face only";
    else if (micOn) scenario = "🎤 voice only";
    else scenario = "⏳ waiting";
}
```

### Task B: Diagnose and Fix Voice Emotion "No Data" Issue

**File:** `mee/remotedemo/server.py` — add voice debug logging  
**File:** `mee/voice/emotion_model.py` — check processing pipeline

#### B1. Add audio frame debug logging to server
In `_handle()` method of RemotedemoServer, add detailed audio debugging:

```python
# In server.py _handle() method, inside the 'audio' case (~line 280):
if msg.get("type") == "frame" and msg.get("subtype") == "audio":
    audio_data = base64.b64decode(msg["data"])
    
    # NEW DEBUG: Log raw audio stats for diagnosing "no data" issue
    import numpy as np
    arr = np.frombuffer(audio_data, dtype=np.int16)
    if len(arr) > 0:
        mean_val = float(np.mean(np.abs(arr)))
        max_val = float(np.max(np.abs(arr)))
        non_zero = np.count_nonzero(arr)
        
        self.logger.debug(
            f"WS-KA-audio ip={client.ip} "
            f"samples={len(arr)} mean_abs={mean_val:.2f} max={max_val:.2f} "
            f"non_zero_ratio={non_zero/len(arr):.2%}"
        )
    
    # Log what voice pipeline returns (not just errors)
    try:
        result = await self._process_audio(audio_data)
        
        if result and isinstance(result, dict):
            emotion = result.get("emotion", "neutral")
            confidence = result.get("confidence", 0.0)
            
            if confidence < 0.01:
                self.logger.warning(
                    f"WS-VOICE-WARN ip={client.ip} "
                    f"voice_result: emotion={emotion} confidence={confidence:.4f} "
                    f"(suspiciously low — possible model returning default)"
                )
            else:
                self.logger.debug(
                    f"WS-KA-voice ip={client.ip} "
                    f"result: {emotion} @{confidence:.2%}"
                )
    except Exception as e:
        self.logger.error(f"WS-VOICE-ERR ip={client.ip}: {e}")
```

#### B2. Add client-side voice panel display enhancement
In `index.html` `renderResult()` function, update the voice panel text when confidence is very low:

```javascript
// In renderResult() — update voice panel section (~line where voice bars are rendered):
if (data.voice) {
    const conf = data.voice.confidence || 0;
    const emotion = data.voice.emotion || "neutral";
    
    // If confidence is suspiciously low, show debug hint
    if (conf < 0.01) {
        voiceEmotionEl.textContent = `${emotion} ${Math.round(conf*100)}% ⚠️ low`;
        // Add tooltip explaining the issue
        voiceEmotionEl.title = `Very low confidence (${conf:.4f}) — check mic hardware and audio format`;
    } else {
        voiceEmotionEl.textContent = `${emotion} ${Math.round(conf*100)}%`;
    }
    
    // Show bars for top emotions
    if (data.voice.top_emotions) {
        // ... existing bar rendering logic unchanged ...
    }
} else if (micMuted) {
    voiceEmotionEl.textContent = "🔇 muted";
} else if ($("micIndicator").classList.contains("muted")) {
    voiceEmotionEl.textContent = "⏳ camera not sending voice data";
}
```

#### B3. Add audio format logging to identify mismatch
In the server log, capture what format the browser sends:

```python
# In _handle() for audio frames, also log browser-sent metadata:
if msg.get("type") == "frame" and msg.get("subtype") == "audio":
    # Log the format info from the client message
    self.logger.info(
        f"WS-KA-audio-format ip={client.ip} "
        f"samples={len(audio_data)} bitrate={msg.get('bitrate','?')} "
        f"sample_rate={msg.get('sampleRate','?')} channels={msg.get('channels','?')}"
    )
```

---

## 3. Acceptance Criteria

### Task A: Camera Toggle
| # | Criterion | Verification Method |
|---|-----------|-------------------|
| A1 | Camera toggle button appears in Controls card | Visual inspection of UI |
| A2 | Toggling OFF stops camera and shows "Camera OFF" | Verify video feed stops, label changes |
| A3 | Scenario label updates correctly: camera-off → "🎤 voice only" (if mic on) | Toggle each combination |
| A4 | Toggling ON restores camera stream without reconnecting WebSocket | Toggle off then on — no WS disconnect |
| A5 | Face emotion is readable when mic is OFF and camera is ON | User confirms face bars don't flash |

### Task B: Voice Emotion Debug/Fix
| # | Criterion | Verification Method |
|---|-----------|-------------------|
| B1 | Server logs show raw audio stats (samples, mean, non-zero ratio) | Check `/tmp/mee-ws.log` for `WS-KA-audio` entries |
| B2 | Low-confidence voice results show ⚠️ hint in UI | Check that "no data" shows confidence value and warning |
| B3 | Root cause identified from logs | Determine if issue is format mismatch, model defaulting, or silent error |

---

## 4. Implementation Order for Implementer 💻

1. **Task 1:** Add camera toggle button to `index.html` (HTML + CSS)
2. **Task 2:** Add camera toggle JavaScript logic (`startCamera`, `camToggle` listener, stream management)
3. **Task 3:** Add voice emotion debug logging to `server.py`
4. **Task 4:** Enhance voice panel UI to show confidence level and warning when very low

---

## 5. CTO Notes

- **Camera toggle is a UX improvement** — users need to isolate testing to one modality at a time. The current "always streaming both" mode makes it hard to distinguish which channel produces results.
- **Voice emotion "no data" is a diagnostic task, not necessarily a fix** — we may discover the audio format sent by the browser is incompatible with the voice pipeline, or the model is returning default neutral because of format mismatch (e.g., wrong sample rate). The debug logging will reveal this quickly.

**Plan submitted for approval.**
