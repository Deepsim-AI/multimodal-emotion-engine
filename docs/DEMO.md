# MEE Demo UI — TASK_MEE_008

A single-file Streamlit demo (`demo/emotion_demo.py`) that drives the public
`EmotionEngine.process(video_frame=, audio=)` API with live camera + microphone
input and displays face / voice / overall / trend / confidence in real-time.

This is an **affective-state estimation** tool — it *estimates* affective
state from face + voice signals. It does not read true emotion.

## Install

```bash
pip install -e ".[demo]"
# installs: streamlit, sounddevice, opencv-python (plus the core `mee` package)
```

## Run (GUI)

Requires a camera and microphone. On hardware-less systems the demo shows a
clear "no hardware" message and offers file-upload fallback for single-frame /
single-clip evaluation.

```bash
streamlit run demo/emotion_demo.py
```

## Run (headless / scripted)

No browser required. Streams every engine result as one JSON line per step
(`.jsonl`), logs a summary every 60 s, and shuts down cleanly on Ctrl-C.

```bash
python demo/emotion_demo.py --headless --output /tmp/mee_results.jsonl
# optional: limit duration (seconds)
python demo/emotion_demo.py --headless --output /tmp/mee_results.jsonl --duration 60
```

## What you'll see

- Camera frame (BGR, live)
- Emotion bars for face (vision), voice, and overall (fused)
- Trend indicator: `➖ stable / 📈 improving / 📉 declining / 🌪 unstable`
- Red conflict banner when `overall.conflict == True`
- Debug panel with the full last result as JSON
- Latency stats (avg/min/max over the last 64 engine steps)

## Notes

- `engine.is_ready` is **always False in V1** (stub — no backend model
  loaded). The demo shows a "Models not loaded" notice and channels
  gracefully degrade to neutral fallback values. This is *real* behavior —
  all pipeline paths (history, fusion, trend) still execute.
- Audio chunks are 20 ms @ 16 kHz (320 samples), matching the engine's
  expected input granularity.
- The UI is a **consumer** of the public API only — it never touches
  `_infer_vision`, `_infer_voice`, `_fuse`, or any model internals.
