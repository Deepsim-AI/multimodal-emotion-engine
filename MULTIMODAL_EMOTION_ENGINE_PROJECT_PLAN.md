# Multimodal Emotion Engine (MEE)
## DS-EO Engineering Project Plan

**Project:** Multimodal Emotion Engine  
**Abbreviation:** MEE  
**Status:** Proposed  
**Priority:** High  
**Type:** Independent AI Capability / Research Prototype  
**Target Platform:** Linux PC → Jetson AGX Orin  
**Relationship to AI Companion Book:** Independent; the book remains complete at Chapter 15

---

## 1. Project Objective

Develop an independent **Multimodal Emotion Engine (MEE)** that estimates a user's affective state from multiple input modalities:

1. **Visual input** — facial expression
2. **Audio input** — voice/acoustic characteristics
3. **Multimodal fusion** — combining visual and voice signals
4. **Temporal analysis** — tracking changes in estimated affective state over time

The initial objective is **not** to build a complete companion robot.

The objective is to create a clean, modular, locally deployable AI capability that can later be integrated into:

- Desktop companion robots
- Educational devices
- Smart lamps
- AI assistants
- DS-AIOS
- Other embodied AI systems

---

## 2. Project Positioning

The existing **AI Companion** book will remain complete at Chapter 15.

Chapter 16 and the commercial/research work described in this document are **not part of the book**.

The book remains an educational project. MEE is an independent engineering and productization project.

The intended evolution is:

```text
AI Companion Book
    Chapter 15
        │
        │ Educational foundation
        ▼
Multimodal Emotion Engine (MEE)
        │
        │ Reusable AI capability
        ▼
Future Companion AI / Embodied AI Systems
        │
        ├── Desktop Robot
        ├── Educational Device
        ├── Smart Lamp
        ├── DS-AIOS
        └── Other Applications
```

MEE should therefore be developed as an independent component rather than as an extension of the book's Chapter 15 implementation.

---

## 3. Scope

### 3.1 In Scope for V1

```text
                    MEE
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
     Vision        Voice        Context
        │            │            │
        ▼            ▼            │
 Facial Emotion  Voice Emotion    │
        │            │            │
        └────────────┼────────────┘
                     ▼
              Emotion Fusion
                     │
                     ▼
                User State
                     │
                     ▼
              Temporal Trend
```

V1 should provide:

- Webcam input
- Face detection
- Facial expression estimation
- Microphone input
- Voice/acoustic emotion estimation
- Multimodal emotion fusion
- Confidence scores
- Temporal state tracking
- A lightweight local demonstration UI
- Structured JSON output
- Unit and integration tests
- Documentation
- Initial Jetson AGX Orin feasibility assessment

### 3.2 Out of Scope for V1

Do not implement the following in the initial project:

- Robot hardware control
- Motors or servo control
- Full conversational agent
- LLM integration
- TTS
- Long-term memory
- Cloud-based emotion processing
- Mobile application
- Production web service
- Commercial SDK licensing infrastructure
- Training large emotion models from scratch

These can become separate future projects.

---

## 4. Architectural Principles

### 4.1 Independent Capability

MEE must not depend on Chapter 15 at runtime.

It should be possible to install and execute MEE independently.

### 4.2 Local-First

The initial implementation should prioritize local inference.

User camera and audio data should not need to leave the local machine for the core functionality.

### 4.3 Modular Models

Vision and voice models must be replaceable without changing the public MEE interface.

### 4.4 Stable API Boundary

Applications should interact with MEE through a stable interface rather than directly accessing underlying model implementations.

### 4.5 Evidence and Uncertainty

MEE should expose confidence scores and, where appropriate, disagreement between modalities.

The system should avoid presenting affective-state estimates as objective measurements of a person's internal psychological state.

---

# 5. Proposed Architecture

```text
                    Multimodal Emotion Engine
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
           Vision           Voice           Context
              │               │               │
              ▼               ▼               │
      Facial Expression   Voice Emotion       │
          Estimator          Estimator         │
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                     Multimodal Fusion
                              │
                              ▼
                       User State Model
                              │
                              ▼
                       Temporal Analysis
                              │
                              ▼
                         MEE API Output
```

The architecture should allow each component to evolve independently.

---

# 6. Proposed Repository Structure

MEE should initially be developed as an independent project.

A possible development location is:

```text
~/projects/multimodal-emotion-engine/
```

A future public repository could be:

```text
Deepsim-AI/multimodal-emotion-engine
```

Recommended structure:

```text
multimodal-emotion-engine/
│
├── README.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
│
├── mee/
│   ├── __init__.py
│   │
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── detector.py
│   │   ├── emotion_model.py
│   │   └── processor.py
│   │
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── recorder.py
│   │   ├── features.py
│   │   ├── emotion_model.py
│   │   └── processor.py
│   │
│   ├── fusion/
│   │   ├── __init__.py
│   │   └── emotion_fusion.py
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── history.py
│   │   └── estimator.py
│   │
│   └── api/
│       ├── __init__.py
│       └── engine.py
│
├── demo/
│   └── emotion_demo.py
│
├── tests/
│   ├── test_vision.py
│   ├── test_voice.py
│   ├── test_fusion.py
│   └── test_state.py
│
└── docs/
    ├── ARCHITECTURE.md
    ├── MODEL_EVALUATION.md
    └── JETSON_DEPLOYMENT.md
```

The implementation may be adjusted by the DS-EO CTO after technical evaluation.

---

# 7. Core Public API

The most important design principle is that consumers interact with MEE through a stable API.

For example:

```python
engine = EmotionEngine()

result = engine.process(
    video_frame=frame,
    audio=audio
)
```

A possible result:

```json
{
  "face": {
    "emotion": "sad",
    "confidence": 0.78
  },
  "voice": {
    "emotion": "frustrated",
    "confidence": 0.84
  },
  "overall": {
    "emotion": "frustrated",
    "confidence": 0.81
  },
  "trend": "increasing"
}
```

The exact API can be refined during TASK_MEE_001.

The underlying models must remain implementation details.

---

# 8. Phase 1 — Technical Research and Model Evaluation

## Objective

Identify suitable pretrained/open-source models for visual and voice emotion estimation.

### Vision Model Requirements

Evaluate models for:

- Facial expression recognition
- Local inference
- Linux compatibility
- Reasonable CPU/GPU performance
- Potential Jetson compatibility
- Model size
- Inference latency
- Accuracy/benchmark information
- Commercial-use licensing

### Voice Model Requirements

Evaluate models for:

- Speech/voice emotion recognition
- Acoustic emotion classification
- Local inference
- Linux compatibility
- Reasonable inference latency
- Potential Jetson compatibility
- Model size
- Accuracy/benchmark information
- Commercial-use licensing

### Deliverable

Create:

```text
docs/MODEL_EVALUATION.md
```

Recommended evaluation table:

| Model | Modality | Benchmark | Latency | Model Size | License | Jetson Potential |
|---|---|---|---:|---:|---|---|
| Model A | Vision | ... | ... | ... | ... | ... |
| Model B | Voice | ... | ... | ... | ... | ... |

Model selection must consider licensing and future commercialization, not popularity alone.

---

# 9. Phase 2 — Vision Emotion Engine

## Objective

Replace the simple face-detection capability used in the book with a dedicated facial-expression estimation pipeline.

Recommended structure:

```text
vision/
├── detector.py
├── emotion_model.py
└── processor.py
```

Pipeline:

```text
Webcam Frame
     │
     ▼
Face Detection
     │
     ▼
Face Crop / Preprocessing
     │
     ▼
Facial Expression Model
     │
     ▼
Emotion Probabilities
```

Example output:

```json
{
  "emotion": "happy",
  "confidence": 0.81,
  "scores": {
    "happy": 0.81,
    "neutral": 0.12,
    "sad": 0.03,
    "angry": 0.02,
    "surprise": 0.02
  }
}
```

The implementation should support:

- Webcam input
- Face detection
- Facial expression estimation
- Confidence scores
- Multiple detected faces where technically practical
- No-face handling
- Configurable model
- Local inference
- Graceful failure

### Terminology

The project documentation should generally use terms such as:

- Facial Expression Estimation
- Affective State Estimation
- Facial Emotion Estimation

It should avoid claiming that the model directly determines a person's true internal emotional or psychological state.

---

# 10. Phase 3 — Voice Emotion Engine

## Objective

Extend the audio pipeline beyond speech transcription by estimating affective information from acoustic characteristics.

Recommended structure:

```text
voice/
├── recorder.py
├── features.py
├── emotion_model.py
└── processor.py
```

Pipeline:

```text
Microphone
    │
    ▼
Audio Recording
    │
    ├──────────────► ASR / Transcript
    │
    └──────────────► Acoustic Analysis
                           │
                           ▼
                     Voice Emotion
```

Example output:

```json
{
  "emotion": "frustrated",
  "confidence": 0.76
}
```

Potential acoustic features include:

- Fundamental frequency / pitch
- Energy
- Speaking rate
- Pause duration
- MFCC
- Spectral characteristics

The system should distinguish between speech content and acoustic emotion. The transcript alone must not be treated as the voice-emotion signal.

A small initial emotion vocabulary may include:

```text
neutral
happy
sad
angry
frustrated
excited
```

The final labels should be determined by the selected model and documented clearly.

---

# 11. Phase 4 — Multimodal Emotion Fusion

## Objective

Combine visual and voice estimates into a unified affective-state estimate.

Recommended module:

```text
fusion/
└── emotion_fusion.py
```

Input:

```text
Vision Result
+
Voice Result
```

Output:

```json
{
  "emotion": "frustrated",
  "confidence": 0.81,
  "sources": {
    "vision": "sad",
    "voice": "frustrated"
  }
}
```

### V1 Fusion Strategy

Start with a transparent deterministic strategy rather than a learned fusion model.

For example:

```text
Vision     40%
Voice      40%
Context    20%
```

The exact weighting should be treated as an engineering parameter, not as a scientifically established truth.

If context is not available in V1, the system can operate using vision and voice only.

The architecture should allow a learned fusion model to be introduced later.

---

# 12. Phase 5 — Temporal State Estimation

## Objective

Move beyond single-frame emotion classification.

Example:

```text
Time →

10:01   neutral
10:02   neutral
10:03   confused
10:04   frustrated
10:05   frustrated
10:06   frustrated
```

The system can then estimate:

```text
Current State: Frustrated
Trend: Increasing
```

Possible trend states:

```text
increasing
stable
decreasing
unknown
```

Recommended structure:

```text
state/
├── history.py
└── estimator.py
```

This capability is important for future companion applications because an application's response may depend more on a sustained or changing state than on one instantaneous classification.

---

# 13. Phase 6 — Demonstration UI

Develop a lightweight local demonstration interface.

The purpose is technical demonstration and evaluation, not production UI design.

Example:

```text
┌────────────────────────────────────────────┐
│        Multimodal Emotion Engine           │
├──────────────────────┬─────────────────────┤
│                      │ Facial Expression   │
│                      │                     │
│       CAMERA         │ Happy       81%     │
│                      │                     │
│                      │ Voice Emotion       │
│                      │ Frustrated  76%     │
│                      │                     │
│                      │ Overall             │
│                      │ Frustrated  81%     │
│                      │                     │
│                      │ Trend               │
│                      │ ↑ Increasing        │
├──────────────────────┴─────────────────────┤
│ Speech: "This problem is really difficult."│
└────────────────────────────────────────────┘
```

The UI should expose enough information for technical evaluation, including:

- Camera image
- Detected face
- Facial emotion
- Voice emotion
- Confidence
- Fused state
- Trend
- Transcript, if ASR is enabled

---

# 14. Phase 7 — Standardized Test Scenarios

DS-EO should establish a repeatable evaluation protocol.

## Test A — Neutral

Normal facial expression and normal speech.

Record:

- Vision result
- Voice result
- Fusion result
- Confidence
- Latency

## Test B — Happy

Smile and positive/excited speech.

Record the same measurements.

## Test C — Sad

Sad facial expression and low-energy speech.

Record the same measurements.

## Test D — Frustrated

Frown and frustrated speech.

This scenario is particularly relevant to the proposed educational companion use case.

## Test E — Conflicting Modalities

Example:

- Positive facial expression
- Angry/frustrated voice

The system should preserve the disagreement rather than silently hiding it.

Example:

```json
{
  "face": {
    "emotion": "happy",
    "confidence": 0.72
  },
  "voice": {
    "emotion": "angry",
    "confidence": 0.79
  },
  "overall": {
    "emotion": "uncertain",
    "confidence": 0.51
  },
  "conflict": true
}
```

The exact conflict policy should be determined during implementation and testing.

---

# 15. Phase 8 — End-to-End Prototype

Combine:

```text
Camera
   │
   ▼
Vision Emotion
   │
   ├──────────────┐
   │              │
   │              ▼
   │          Multimodal
   │            Fusion
   │              ▲
   │              │
   ▼              │
User State        │
                  │
Microphone ───────┘
       │
       ▼
Voice Emotion
```

The end-to-end prototype should provide a single MEE result object.

Acceptance criteria:

- Camera input works reliably
- Microphone input works reliably
- Vision inference works
- Voice inference works
- Fusion works
- Temporal state works
- UI works
- Structured output works
- Errors are handled gracefully
- Tests are reproducible
- Installation is documented

---

# 16. Phase 9 — Jetson AGX Orin Deployment

Jetson deployment should begin only after the PC prototype is validated.

Target:

```text
PC Prototype
      │
      ▼
Model Optimization
      │
      ▼
Jetson AGX Orin
      │
      ▼
Local Multimodal Inference
```

Measure:

- GPU utilization
- CPU utilization
- Memory consumption
- FPS
- Face detection latency
- Facial emotion inference latency
- Voice inference latency
- Fusion latency
- End-to-end latency
- Concurrent camera/audio performance
- Stability during extended execution

Deliverable:

```text
docs/JETSON_DEPLOYMENT.md
```

The deployment document should include:

- Hardware configuration
- Software versions
- Installation steps
- Model versions
- Runtime configuration
- Performance measurements
- Known limitations

---

# 17. Phase 10 — Packaging

Once the prototype is stable, package MEE as a reusable capability.

Recommended final structure:

```text
multimodal-emotion-engine/
│
├── README.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
│
├── mee/
│   ├── vision/
│   ├── voice/
│   ├── fusion/
│   ├── state/
│   └── api/
│
├── demo/
│   └── emotion_demo.py
│
├── tests/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── MODEL_EVALUATION.md
    └── JETSON_DEPLOYMENT.md
```

At this stage MEE becomes a reusable AI capability rather than a one-off demonstration.

---

# 18. DS-EO Task Breakdown

Recommended task sequence:

```text
TASK_MEE_001
Project Setup & Architecture

TASK_MEE_002
Vision Emotion Model Evaluation

TASK_MEE_003
Voice Emotion Model Evaluation

TASK_MEE_004
Vision Emotion Engine

TASK_MEE_005
Voice Emotion Engine

TASK_MEE_006
Multimodal Emotion Fusion

TASK_MEE_007
Temporal User State

TASK_MEE_008
Emotion Demonstration UI

TASK_MEE_009
End-to-End Validation

TASK_MEE_010
Jetson AGX Orin Deployment

TASK_MEE_011
Packaging & Documentation
```

Recommended dependency chain:

```text
TASK_MEE_001
      │
      ├──────────────┐
      ▼              ▼
TASK_MEE_002    TASK_MEE_003
      │              │
      ▼              ▼
TASK_MEE_004    TASK_MEE_005
      │              │
      └──────┬───────┘
             ▼
       TASK_MEE_006
             │
             ▼
       TASK_MEE_007
             │
             ▼
       TASK_MEE_008
             │
             ▼
       TASK_MEE_009
             │
             ▼
       TASK_MEE_010
             │
             ▼
       TASK_MEE_011
```

---

# 19. DS-EO Role Assignment

## PM

Responsible for:

- Task intake
- Requirements
- Acceptance criteria
- Dependencies
- Progress tracking
- Milestone management

## CTO

Responsible for:

- System architecture
- Model selection
- Technology decisions
- Fusion strategy
- Jetson deployment strategy
- Long-term extensibility

## Implementer

Responsible for:

- Implementation
- Integration
- Testing
- Performance optimization
- Documentation

## Reviewer

Responsible for:

- Code review
- Architecture review
- Model/license review
- Test validation
- Reproducibility review
- Security/privacy review

---

# 20. Key Acceptance Criteria

V1 should not be judged solely by a single emotion-classification accuracy number.

## Functional

- [ ] Camera input works
- [ ] Face detection works
- [ ] Facial expression estimation works
- [ ] Microphone input works
- [ ] Voice emotion estimation works
- [ ] Multimodal fusion works
- [ ] Temporal state tracking works
- [ ] Demonstration UI works
- [ ] Structured API output works

## Engineering

- [ ] Modular architecture
- [ ] Local inference
- [ ] Configurable models
- [ ] Replaceable model backends
- [ ] Unit tests
- [ ] Integration tests
- [ ] Reproducible installation
- [ ] Clear documentation

## Hardware

- [ ] PC prototype validated
- [ ] Jetson feasibility evaluated
- [ ] Jetson performance measured
- [ ] Resource consumption documented

## Productization

- [ ] Stable API boundary
- [ ] No dependency on Chapter 15
- [ ] Underlying models can be replaced
- [ ] Model licenses documented
- [ ] Privacy considerations documented
- [ ] Future SDK/API integration is feasible

---

# 21. Important Scientific and Product Constraint

MEE should not claim that it directly reads or determines a person's true emotional or psychological state.

The system estimates affective information from observable signals.

Preferred terminology:

- Facial Expression Estimation
- Voice Emotion Estimation
- Affective State Estimation
- Multimodal Emotion Estimation

Avoid unsupported claims such as:

> "The AI knows exactly how the user feels."

The README, documentation, and demonstration UI should communicate the probabilistic nature and limitations of the estimates.

---

# 22. Future Integration Architecture

MEE should not decide what the robot should do.

Its responsibility is perception and state estimation.

Future systems can consume MEE output:

```text
                    Application
                         │
                         ▼
                    MEE API
                         │
          ┌──────────────┼──────────────┐
          │              │              │
        Vision         Voice          State
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
                  Emotion / State
                         │
                         ▼
                  Application Logic
```

For a future companion robot:

```text
                    Desktop Robot
                          │
              ┌───────────┴───────────┐
              │                       │
             MEE                 Robot AI
              │                       │
      Emotion / State             Reasoning
              │                       │
              └───────────┬───────────┘
                          ▼
                        Action
```

MEE reports observations and estimates.

The higher-level agent determines how to respond.

---

# 23. Future Product Evolution

The intended architecture should allow MEE to become one component of a larger system:

```text
Multimodal Emotion Engine
            │
            ▼
      Companion AI Core
            │
      ┌─────┼─────┐
      │     │     │
    MEE   Memory  Agent
      │     │     │
      └─────┼─────┘
            ▼
       Robot / Device
```

Potential future components may include:

- Vision Engine
- Voice Engine
- Memory Engine
- Agent Engine
- Conversation Engine
- Robot Control Engine

These should remain separate until there is a concrete integration requirement.

---

# 24. Recommended V1 Development Sequence

The recommended engineering sequence is:

### V1.0 — Perception Prototype

```text
Camera
   ↓
Facial Expression

Microphone
   ↓
Voice Emotion
```

Goal: demonstrate that both modalities work independently.

### V1.1 — Multimodal Prototype

```text
Face
  +
Voice
  ↓
Fusion
  ↓
Affective State
```

Goal: demonstrate that combining modalities provides useful additional information.

### V1.2 — Temporal State

```text
Affective State
       ↓
History
       ↓
Trend
```

Goal: identify sustained or changing states.

### V1.3 — Demonstration System

```text
Camera + Microphone
        ↓
       MEE
        ↓
   Live Dashboard
```

Goal: provide a demonstration suitable for technical evaluation.

### V1.4 — Jetson Prototype

```text
MEE
 ↓
Jetson AGX Orin
 ↓
Local Inference
```

Goal: demonstrate edge deployment feasibility.

---

# 25. Final Project Definition

**Multimodal Emotion Engine (MEE)** is an independent, local-first AI perception component designed to estimate affective states from facial expressions and voice, combine multimodal evidence, and track changes over time.

MEE is intentionally separated from the AI Companion book and from any specific robot implementation.

The immediate goal is a technically credible demonstration.

The longer-term goal is a reusable AI capability that can be integrated into future companion robots, educational devices, DS-AIOS, and other embodied AI systems without exposing or coupling the underlying implementation to the consuming application.

**Primary principle:**

> **Build the perception capability first. Integrate it with agents and physical devices later.**
