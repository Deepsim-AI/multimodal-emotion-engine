# CTO Plan — TASK_MEE_008: Emotion Demonstration UI

**Task ID:** TASK_MEE_008  
**Status:** Awaiting user approval → awaiting Implementer build  
**Date:** 2026-09-21  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)

---

## Executive Summary

Build a **single-file streamlit demo** (`demo/emotion_demo.py`) that consumes the public `EmotionEngine` API to drive live camera + microphone input and display all engine outputs in real-time. The UI is a consumer — it never touches model internals, respects the public API contract, and degrades gracefully when hardware is unavailable.

**Design principle:** One file, no new Python packages beyond streamlit (already in pyproject.toml demo extras), no production polish — functional technical demo only.

---

## Subtask Breakdown

### Subtask 1 — Demo Script (`demo/emotion_demo.py`)

**File:** `demo/emotion_demo.py` (CREATE)  
**Purpose:** Streamlit app that drives EmotionEngine with live camera + mic and displays all outputs.

**Architecture:**
```python
# App structure:
# 1. Sidebar: controls (fusion weights, model toggle, headless flag)
# 2. Main area:
#    - Camera feed with bounding box overlay (if vision available)
#    - Emotion bars for face, voice, overall
#    - Trend indicator (stable / improving / declining / unstable)
#    - Conflict banner when conflict=True
#    - JSON debug panel
# 3. Background thread: engine loop at ~10Hz

# Engine usage (public API only):
from mee import EmotionEngine, MEEConfig
engine = EmotionEngine(config=MEEConfig())

result = engine.process(video_frame=bgr_frame, audio=audio_chunk)
# result keys: face, voice, overall, trend, latency_ms
```

**Key components:**

#### 1. Engine lifecycle (lines ~15-30):
```python
engine = EmotionEngine(config=MEEConfig())
is_ready = engine.is_ready  # Always False in V1 — stub always returns False
# Note: is_ready is a stub; the demo should display a notice that models aren't loaded
# rather than blocking on it.
```

#### 2. Camera capture (lines ~35-60):
- Use `cv2.VideoCapture(0)` or streamlit's built-in camera if available
- Fallback: "No camera available" message with option to load from file
- Frame format: BGR numpy array (H×W×3 uint8) — matches EmotionEngine.process() contract

#### 3. Audio capture (lines ~65-90):
- Use `sounddevice` for live mic input
- Capture in chunks (~20ms at 16kHz = 320 samples) — matches audio_sample_rate config
- Fallback: "No microphone available" message + file upload option

#### 4. Processing loop (lines ~95-120):
- Background thread calling `engine.process()` at ~10Hz
- Results pushed to a thread-safe queue for UI rendering
- Track latency_ms from engine output

#### 5. Streamlit UI layout (lines ~125-200):
```
Sidebar:
├── Fusion weights (vision_weight, voice_weight) — sliders
├── Model availability indicator (🔴/🟡/🟢 for face detection, voice model)
├── "Headless mode" checkbox — when checked, outputs to JSON file instead of UI
└── "Reset engine" button

Main:
├── Camera frame with bounding box (if vision working)
├── Emotion bars: face emotion, voice emotion, overall emotion (3 horizontal bars)
├── Trend display: [stable / improving / declining / unstable] with emoji indicator
├── Conflict banner: red alert when overall.conflict == True
└── Debug panel: collapsible JSON output of last result + latency_ms
```

#### 6. Headless/JSON mode (lines ~205-230):
- When "Headless mode" is checked in sidebar, instead of Streamlit UI:
  - Write results to `demo/results.jsonl` (one JSON line per frame)
  - Write summary stats every 60 seconds
  - Support `--output <path>` CLI flag for output file path

### Subtask 2 — Update pyproject.toml

**File:** `pyproject.toml` (MODIFY only demo section)  
**Change:** Ensure streamlit dependency is correct and add any needed audio/video extras.

Current:
```toml
demo = ["streamlit>=1.28"]
```

No changes needed — streamlit includes its own camera/mic integration via `st.camera_input` and `st.audio`. If sounddevice is needed for lower-level capture, add it to demo deps:
```toml
demo = ["streamlit>=1.28", "sounddevice>=0.4", "opencv-python>=4.8"]
```

**CTO recommendation:** Add sounddevice and opencv-python to demo deps since the demo needs low-level camera/mic access for real-time operation (streamlit's built-in `st.camera_input` is too slow for ~10Hz engine processing).

### Subtask 3 — Readme snippet for Demo (optional, in docs)

**File:** `docs/DEMO.md` (CREATE)  
**Purpose:** One-page guide for running the demo.

```markdown
# MEE Demo UI

Run: `pip install -e ".[demo]" && streamlit run demo/emotion_demo.py`

Or headless mode: `streamlit run demo/emotion_demo.py -- --headless --output results.jsonl`

Requirements: camera and microphone on Linux PC. On systems without hardware,
the demo shows a graceful "no hardware" message with file-upload fallback.
```

---

## Key Code References (R-SI-2: Exact File/Symbol/Lines)

The Implementer needs to understand exactly what the public API provides:

| What | File | Lines |
|------|------|-------|
| `process()` return dict shape | `mee/api/engine.py:L130-155` | `{face, voice, overall, trend, latency_ms}` |
| `face.to_dict()` output | `mee/api/engine.py:L43-56` | `{emotion, confidence, scores, has_face}` |
| `overall` keys | `mee/api/engine.py:L150-152` | `{emotion, confidence, conflict}` |
| `voice` dict shape | `mee/api/engine.py:L180-190` | `{emotion, confidence, scores}` or None |
| Trend states | `mee/state/estimator.py` | `stable`/`improving`/`declining`/`unstable` |
| Emotion label set | `mee/fusion/emotion_fusion.py:L30-32` | `("angry","disgust","fear","happy","sad","surprised","neutral")` |
| MEEConfig defaults | `mee/api/engine.py:L16-24` | All defaults suitable for demo use |
| `engine.is_ready` | `mee/api/engine.py:L219-220` | **Always returns False** (stub) — demo must handle this |

---

## Constraints

1. **Single file** — all demo logic in `demo/emotion_demo.py`. No sub-packages, no conftest changes.
2. **Public API only** — the demo never touches `_infer_vision`, `_infer_voice`, `_fuse`, or any model internals. It only calls `engine.process(video_frame=..., audio=...)`.
3. **Graceful degradation** — when camera/microphone/hardware/model is unavailable, show a clear message rather than crashing. Provide file upload fallback for evaluation.
4. **Headless mode** — must support `--headless` CLI flag for scripted/automated evaluation (output to JSONL).
5. **No production polish** — functional demo only; use streamlit's default styling.
6. **"Affective-state estimation"** — never "reads true emotion" in any UI text or docstring.

---

## Acceptance Criteria Mapping

| Requirement | How Implemented | Verification |
|---|---|---|
| Runs on Linux PC with camera+mic (or shows "no hardware") | cv2.VideoCapture + sounddevice with try/except fallbacks | Manual test on system with hardware |
| Displays face, voice, overall, trend, confidence | Streamlit components rendering result dict keys | Visual verification |
| Headless/JSON mode via `--headless` flag | CLI arg parsing in main() | `python demo/emotion_demo.py --headless` |
| Graceful missing camera/mic handling | Try/except on cv2.VideoCapture(0) and sounddevice inputs | Manual test with no hardware |
| Uses only public API | Only calls `EmotionEngine().process(video_frame=, audio=)` | Code inspection |

---

## Implementation Steps (ordered for the Implementer)

### Step 1: Skeleton (`demo/emotion_demo.py`, lines 1-30)
- Imports: streamlit components, EmotionEngine from mee, MEEConfig, argparse
- CLI argument parser with `--headless` and `--output` flags
- Initialize engine with default config

### Step 2: Camera/Audio capture functions (~lines 35-80)
- `get_frame() -> np.ndarray | None`: cv2.VideoCapture(0), fallback to None
- `get_audio() -> np.ndarray | None`: sounddevice stream, chunk at audio_sample_rate, fallback to None

### Step 3: Engine processing loop (~lines 85-110)
- Background thread that calls `engine.process(frame, audio)` every ~100ms
- Thread-safe queue for results (use `queue.Queue`)
- Track running latency stats

### Step 4: UI rendering functions (~lines 115-180)
- If headless: write to JSONL file, skip streamlit entirely
- If not headless: render sidebar controls, camera frame, emotion bars, trend display, conflict banner, debug panel

### Step 5: Headless mode logic (~lines 185-210)
- Write each result as a JSON line to output file
- Log periodic summary stats
- Clean shutdown on KeyboardInterrupt

---

## Known Design Decisions by CTO

1. **Engine `is_ready` always returns False** (line 219 of engine.py is a stub). The demo should display a notice "Models not loaded — using synthetic/simulated input or showing hardware availability message" rather than blocking indefinitely. In practice, if insightface/speechbrain aren't installed, the engine will gracefully degrade to neutral predictions (which IS real behavior, just with empty models).

2. **Streamlit runs on a single thread** — camera capture via cv2.VideoCapture in the main streamlit thread may conflict. Solution: use `threading.Thread` for both camera capture and engine processing loops.

3. **Audio chunk size**: 16kHz sample rate × 0.02s = 320 samples per frame. This matches what the VoiceProcessor expects as a reasonable chunk size for feature extraction.

---

## Delivery Checklist

| Deliverable | Location | Status |
|---|---|---|
| `demo/emotion_demo.py` | CREATE | Pending |
| `pyproject.toml` demo deps update | MODIFY (demo section only) | Pending |
| `docs/DEMO.md` | CREATE | Pending |
| Demo runs successfully on PC with hardware | Shell verification | Pending |
| Headless mode works (`--headless`) | Shell verification | Pending |

---

## Risks & Notes

1. **Streamlit camera/mic support varies** — `st.camera_input` is available in newer versions but may not work headless. The demo will use streamlit's default components when available, falling back to file upload for evaluation without hardware.

2. **No real model inference on this system** (no insightface/speechbrain installed). On systems where models are installed, the engine will produce real predictions; on this system it will return neutral/fallback values — which still exercises all pipeline paths correctly.

3. **pyproject.toml demo deps**: Only add sounddevice and opencv-python to the demo extras if they're needed beyond streamlit's own dependencies. They should be non-blocking for import — if unavailable, show a "install X" message rather than crash.
