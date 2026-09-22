# Implementation Instructions — TASK_MEE_008: Emotion Demonstration UI

**Task ID:** TASK_MEE_008  
**Phase:** Phase 6 (Demo UI)  
**Assignee:** Implementer 💻 (ollama/qwen3.8:27b)  
**Status:** Ready for Build  

---

## What to Build

A single-file streamlit demo (`demo/emotion_demo.py`) that drives `EmotionEngine.process()` with live camera + microphone input and displays all outputs in real-time. The UI is a consumer of the public API — it never touches model internals.

**Deliverables:**
1. `demo/emotion_demo.py` (~300-400 lines) — streamlit app
2. `pyproject.toml` update — add sounddevice + opencv-python to demo deps
3. `docs/DEMO.md` (~50 lines) — one-page usage guide

**NO other files.** Single file for all demo logic. No sub-packages, no conftest changes.

---

## Key Technical Details

### 1. Public API Contract (READ THESE EXACT LOCATIONS)

When you need to understand what `process()` returns or what channel dicts look like:

| What | File | Lines |
|------|------|-------|
| `process()` return dict | `mee/api/engine.py:L130-155` | `{face, voice, overall, trend, latency_ms}` |
| `face.to_dict()` output | `mee/api/engine.py:L43-56` | `{emotion, confidence, scores, has_face}` |
| `overall` keys | `mee/api/engine.py:L150-152` | `{emotion, confidence, conflict}` |
| `voice` dict shape | `mee/api/engine.py:L180-190` | `{emotion, confidence, scores}` or None |
| Emotion labels | `mee/fusion/emotion_fusion.py:L30-32` | angry/disgust/fear/happy/sad/surprised/neutral |

### 2. Engine Lifecycle (IMPORTANT)

```python
from mee import EmotionEngine, MEEConfig

engine = EmotionEngine(config=MEEConfig())

# is_ready is ALWAYS False in V1 — it's a stub that returns self._model_ready
# The demo should display "Models not loaded" when engine.is_ready is False
is_ready = engine.is_ready  # Always False — stub at engine.py:L219-220

# process() returns: {face, voice, overall, trend, latency_ms}
result = engine.process(video_frame=bgr_frame, audio=audio_chunk)
```

### 3. Camera/Audio Capture

**Camera:** `cv2.VideoCapture(0)` → frames as BGR numpy array (H×W×3 uint8).  
Fallback: show "No camera" message + file upload option for still-frame evaluation.

**Audio:** `sounddevice.InputStream` at 16kHz, capture chunks of ~320 samples (20ms).  
Fallback: show "No microphone" message + audio file upload for playback evaluation.

### 4. Headless/JSON Mode

Support CLI flags:
```bash
streamlit run demo/emotion_demo.py -- --headless --output results.jsonl
```

When headless mode is active, skip Streamlit UI entirely and write each result as a JSON line to the output file. Log periodic summary stats (avg latency, emotion distribution).

---

## Implementation Steps

### Step 1: Demo Script Skeleton (`demo/emotion_demo.py`, lines 1-30)
- Imports: streamlit components, EmotionEngine/MEEConfig from mee, argparse
- CLI parser with `--headless` and `--output <path>` flags  
- Initialize engine with default MEEConfig()

### Step 2: Capture Functions (~lines 35-80)
- `get_frame() -> np.ndarray | None`: cv2.VideoCapture(0), fallback to None
- `get_audio() -> np.ndarray | None`: sounddevice stream, chunk at audio_sample_rate (16000 Hz), fallback to None

### Step 3: Engine Processing Loop (~lines 85-110)
- Background thread calling `engine.process(frame, audio)` every ~100ms
- Thread-safe queue.Queue for results → UI rendering
- Track running latency stats (min/max/avg over last N frames)

### Step 4: Streamlit UI Layout (~lines 115-200)

**Sidebar:**
- Fusion weights sliders (vision_weight, voice_weight) — default 0.5 each
- Model availability indicators (🔴/🟡/🟢 for face detection, voice model)
- "Headless mode" checkbox
- "Reset engine" button

**Main area:**
- Camera frame with bounding box overlay (if vision working, use face detection coords)
- Emotion bars: face emotion, voice emotion, overall emotion (horizontal bars)
- Trend display: `stable`/`improving`/`declining`/`unstable` with emoji
- Conflict banner: red alert when `overall.conflict == True`
- Debug panel: collapsible JSON of last result + latency_ms

**Important:** Use streamlit's default styling only — no custom CSS. Functional demo, not production polish.

### Step 5: Headless Mode (~lines 205-240)
- When `--headless` flag is set, skip all Streamlit UI code
- Write each result as JSON line to output file (one dict per line = jsonl format)
- Log summary every 60 seconds (emotion distribution, avg latency)
- Handle KeyboardInterrupt for clean shutdown

---

## pyproject.toml Update

Current demo section:
```toml
demo = ["streamlit>=1.28"]
```

Change to:
```toml
demo = ["streamlit>=1.28", "sounddevice>=0.4", "opencv-python>=4.8"]
```

These are needed for live camera + mic access. They should be non-blocking for import — if unavailable, the demo shows "install X" messages rather than crashing.

---

## Constraints (MANDATORY)

1. **Single file** — all demo logic in `demo/emotion_demo.py`
2. **Public API only** — only calls `EmotionEngine().process(video_frame=, audio=)`
3. **Graceful degradation** — no crashes on missing hardware/model; show clear messages + file upload fallback
4. **Headless mode must work** — tested with `python demo/emotion_demo.py --headless` (not via streamlit)
5. **"Affective-state estimation" wording** — never "reads true emotion" in any UI text or docstring
6. **No production polish** — functional demo only, default streamlit styling

---

## Gate Entry Verification (AGENTS.md Rule 7)

Before starting work, verify all prior gate artifacts exist:
- [ ] TASK_REQUEST.md exists ✅
- [ ] CTO_PLAN.md exists ✅

If either is missing, halt and return to the CTO.

---

## Known Implementation Notes

1. **Streamlit runs on a single thread** — use `threading.Thread` for both camera capture and engine processing loops to avoid blocking the UI.
2. **Engine `is_ready` always returns False** — display "Models not loaded" notice rather than blocking. In practice, if insightface/speechbrain aren't installed, the engine gracefully degrades to neutral predictions (which exercises all pipeline paths correctly).
3. **Audio chunk size**: 16kHz × 0.02s = 320 samples per frame — matches what VoiceProcessor expects for feature extraction.
4. **No models on this system** — on systems without insightface/speechbrain, the engine returns neutral/fallback values. This still validates all pipeline paths (history accumulation, trend computation, fusion logic).

---

## Test / Verification Steps

After implementation:
1. `streamlit run demo/emotion_demo.py` — runs on system with camera+mic (or shows "no hardware" message)
2. `python demo/emotion_demo.py --headless --output /tmp/test_results.jsonl` — writes JSONL output
3. Verify UI displays: face/voice emotion bars, trend indicator, conflict banner, debug panel
4. Verify graceful degradation when camera/mic unavailable

---

## DELIVERY REQUIREMENT

Produce an implementation status report in `IMPLEMENTATION_REPORT.md` in this task directory (≤200 lines):
```
TASK_MEE_008 Implementation Status
=====================================
Subtask 1: demo/emotion_demo.py — [APPLIED | FAILED]
- File: demo/emotion_demo.py, ~N lines
- Change: streamlit app with camera/mic input and real-time display
...
Test Results: (describe how you verified the deliverables)

Key decisions made during implementation:
- (document any deviations from the plan)

Known issues / notes for Reviewer:
- (any observations relevant for review)
```

---

## IMPORTANT — Read the Full CTO Plan Before Starting

The `CTO_PLAN.md` in this directory contains additional rationale, design decisions, and constraints. Read it fully before beginning implementation.
