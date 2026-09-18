# Multimodal Emotion Engine (MEE)

An independent, locally-deployable AI capability that estimates a user's affective state from multiple input modalities: visual (facial expression) and voice (acoustic characteristics).

## Overview

MEE processes webcam video and microphone audio to produce:

- Per-modality emotion estimates with confidence scores
- Multimodal fused emotion estimate
- Temporal state trend (increasing / stable / decreasing)
- Structured JSON output

## Key Principles

- **Local-first** — core inference runs on-device; no cloud dependency
- **Modular** — vision and voice models are interchangeable behind a stable API
- **Independent** — does not depend on the AI Companion Book Chapter 15

## Project Structure

```
multimodal-emotion-engine/
├── mee/              # Core Python package
│   ├── vision/       # Facial expression pipeline
│   ├── voice/        # Voice emotion pipeline
│   ├── fusion/       # Multimodal fusion
│   ├── state/        # Temporal state tracking
│   └── api/          # Public API
├── demo/             # Demonstration UI
├── tests/            # Unit and integration tests
└── docs/             # Architecture and deployment docs
```

## Status

**Phase:** G1→G2 (CTO Plan Approved — Awaiting User Approval)

See `docs/development/reports/TASK_MEE_001/` for task artifacts.

## License

Proprietary — Deepsim-AI
