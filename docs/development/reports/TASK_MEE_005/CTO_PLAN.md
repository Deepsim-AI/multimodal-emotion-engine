# CTO Plan — TASK_MEE_005: Voice Emotion Engine

**Task ID:** TASK_MEE_005  
**Gate:** G1 — Plan Approval  
**Phase:** Phase 2 / Voice Subsystem Implementation  
**Date:** 2026-09-20  
**Planned By:** CTO / Architect 🏗️  

---

## 1. Objective

Implement the full Voice submodule (`mee/voice/`) that performs **acoustic emotion estimation** (not speech transcription) from raw audio, using the approved model from TASK_MEE_003: **SpeechBrain RavNet**. Replace the empty stub and return structured emotion results matching the public API `_MEEFaceResult` schema.

### Model Selection (from MEE_003 CTO_APPROVAL)
- **Primary:** SpeechBrain RavNet (Apache-2.0, ~73–90% accuracy, ONNX export support)
- **Fallback:** Wav2Vec 2.0-base + emotion head (MIT license, SOTA ~70–82%)
- **Model source:** SpeechBrain HuggingFace hub (`speechbrain/mtl-mimic-rep-vanilla`)
- **Label set:** `["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]`

### Prerequisite Gate Check (Pre-G1)

| Requirement | Status | Evidence |
|---|---|---|
| TASK_MEE_003 G4 approved | ✅ | `docs/development/reports/TASK_MEE_003/CTO_APPROVAL.md` |
| Voice model recommendation | ✅ | SpeechBrain RavNet (VO4) |
| Public API boundary stable | ✅ | `mee/api/engine.py:138-141` — `_infer_voice()` stub confirmed |
| MeeEngine.process() signature unchanged | ✅ | Lines 72–97 — no modification needed |

---

## 2. Dependency Setup

### File: `pyproject.toml` (~line 15)

**Line to modify:** The existing `[project.optional-dependencies].vision` line needs a new `[voice]` section added.

```toml
# Line 16 (after vision line): add new section
voice = ["speechbrain>=0.5.14", "librosa>=0.10", "torchaudio>=2.1"]
```

**Change marker:** `// TASK_MEE_005 Subtask 1: Add speechbrain, librosa to [project.optional-dependencies].voice`

### Dependency Verification

| Package | Purpose | License | Commercial-safe? |
|---|---|---|---|
| speechbrain>=0.5.14 | Emotion recognition toolkit | Apache-2.0 ✅ | Yes |
| librosa>=0.10 | Audio feature extraction (MFCC, spectral) | MIT ✅ | Yes |
| torchaudio>=2.1 | Audio I/O and preprocessing | BSD ✅ | Yes |

---

## 3. Implementation Plan (7 Subtasks)

### Subtask 1: Voice Package Structure

**Create `mee/voice/__init__.py` with exports:**

```python
# File: mee/voice/__init__.py (replace stub content at ~line 1)
from .recorder import AudioRecorder, MicRecorder
from .features import FeatureExtractor, AUDIO_FEATURES
from .emotion_model import EmotionModel, VOICE_LABELS, VoiceResult
from .processor import VoiceProcessor

__all__ = [
    "AudioRecorder", "MicRecorder",
    "FeatureExtractor", "AUDIO_FEATURES",
    "EmotionModel", "VOICE_LABELS", "VoiceResult",
    "VoiceProcessor",
]
```

**Change marker:** `// TASK_MEE_005 Subtask 1a: New voice package exports`

---

### Subtask 2: AudioRecorder — `mee/voice/recorder.py` (~180 lines)

**File:** `mee/voice/recorder.py` (NEW)

```
Classes:
- AudioRecord: dataclass(attrs=["data", "sample_rate", "duration"])
    data: np.ndarray (N,) float32 mono audio samples at 16kHz
    sample_rate: int (always 16000 for MEE)
    duration: float seconds

- AudioRecorder: captures raw audio from file or buffer
    __init__(sample_rate=16000, channels=1)
    record(buffer_or_path) -> list[AudioRecord]
        - Supports numpy array input (no file I/O required for engine use)
        - Splits into configurable chunk_duration segments (default 2.0s)
    is_available() -> bool — checks mic + librosa availability

- MicRecorder: convenience subclass using sounddevice for live capture
    record_chunk(seconds=2.0) -> AudioRecord
```

**Key requirements:**
- Always resample to 16kHz (per MEEConfig.audio_sample_rate)
- Returns empty list if audio unavailable — never raises
- Graceful degradation: if `sounddevice` not installed, `MicRecorder.record_chunk()` returns `None`; `AudioRecorder` continues to work with file/buffer input

**Change marker:** `// TASK_MEE_005 Subtask 2: New AudioRecorder + MicRecorder classes for audio capture`

---

### Subtask 3: FeatureExtractor — `mee/voice/features.py` (~200 lines)

**File:** `mee/voice/features.py` (NEW)

```
Constants:
AUDIO_FEATURES = [
    "mfcc_mean", "mfcc_std",      # MFCC features (13 coeffs, mean + std per coeff)
    "spectral_centroid",           # Spectral centroid
    "spectral_bandwidth",          # Spectral bandwidth
    "spectral_rolloff",            # Spectral rolloff (85th percentile)
    "zero_crossing_rate",          # Zero-crossing rate
    "rms_energy",                  # Root mean square energy
    "pitch_hz",                    # Fundamental frequency estimate
    "hnr_db",                      # Harmonic-to-noise ratio
]
# Total: ~42-dimensional feature vector (13*2 + 7 scalars)

Class: FeatureExtractor
    extract(audio: np.ndarray, sample_rate: int = 16000) -> dict[str, float]
        - Input: raw audio samples at any sample rate (auto-resample to 16k)
        - Returns: dict mapping feature name → scalar value
        - Uses librosa for all computations
```

**Specific implementation notes:**
- **MFCC:** `librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13)` → take mean and std across time axis (26 values)
- **Spectral centroid/rolloff:** `librosa.feature.spectral_centroid()` and `spectral_rolloff(roll_percent=0.85)` — return single scalar
- **Zero-crossing rate:** `librosa.feature.zero_crossing_rate()` — mean across frames
- **RMS energy:** `librosa.feature.rms()` — mean across frames  
- **Pitch (Hz):** `librosa.pyin()` for fundamental frequency estimate; use mean if available, else 0.0
- **HNR:** Approximate via `librosa.amplitude_to_db(np.abs(librosa.stft(audio)))` → ratio of harmonic to noise energy

**Graceful degradation:** If librosa unavailable, return all zeros dict with feature names preserved (matching keys always returned).

**Change marker:** `// TASK_MEE_005 Subtask 3: New FeatureExtractor class for acoustic feature extraction`

---

### Subtask 4: EmotionModel — `mee/voice/emotion_model.py` (~250 lines)

**File:** `mee/voice/emotion_model.py` (NEW)

```
Constants:
VOICE_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]

@dataclass
class VoiceResult:
    emotion: str = "neutral"
    confidence: float = 0.0
    scores: dict[str, float] = field(default_factory=dict)

Class: EmotionModel
    __init__(model_path=None, device="cpu")
        - model_path: path to SpeechBrain checkpoint or HuggingFace repo string
          default: "speechbrain/mtl-mimic-rep-vanilla"
        - device: "cpu" or "cuda" (auto-detect GPU available)
        - Downloads/expands checkpoint on first use

    predict(audio: np.ndarray, features=None) -> VoiceResult
        - audio: raw samples at 16kHz
        - features: optional precomputed dict from FeatureExtractor (for fallback mode)
        - Returns VoiceResult with emotion, confidence, scores dict over VOICE_LABELS
        
    is_available() -> bool — checks speechbrain importability
```

**Implementation detail — primary path (SpeechBrain):**
1. Load `speechbrain/inference/classifiers` or `speechbrain.lobes.features` for audio frontend
2. Use SpeechBrain's pretrained emotion recognition model (`speechbrain/mtl-mimic-rep-vanilla`)
3. Run forward pass → get class probabilities over speechemotion labels
4. Map SpeechBrain native labels to MEE canonical set:
   ```python
   # Label mapping (SpeechBrain → MEE canonical)
   LABEL_MAP = {
       "angry": "angry",
       "disgust": "disgust", 
       "fear": "fear",
       "happy": "happy",
       "sad": "sad",
       "surprised": "surprised",
       "neutral": "neutral",
   }
   ```

**Implementation detail — fallback path (Wav2Vec):**
1. If speechbrain unavailable, use `transformers.Wav2Vec2ForAudioClassification`
2. Load `facebook/wav2vec2-base-960h` or similar with emotion head
3. Extract features → classify → map labels

**Degraded output (no model available):**
```python
VoiceResult(
    emotion="neutral",
    confidence=0.0, 
    scores={label: 0.0 for label in VOICE_LABELS}
)
```

**Change marker:** `// TASK_MEE_005 Subtask 4: New EmotionModel class with SpeechBrain primary + Wav2Vec fallback`

---

### Subtask 5: VoiceProcessor — `mee/voice/processor.py` (~120 lines)

**File:** `mee/voice/processor.py` (NEW)

```
Class: VoiceProcessor
    __init__(detector=None, emotion_model=None)
        - detector: AudioRecorder instance for input buffering (optional)
        - emotion_model: EmotionModel instance (creates default if None)

    process(audio: np.ndarray, sample_rate: int = 16000) -> VoiceResult
        Pipeline:
        1. FeatureExtractor.extract(audio, sample_rate) → feature dict
        2. EmotionModel.predict(audio, features) → VoiceResult
        3. Return result (always returns, never raises)

    process_audio_chunk(duration_seconds: float) -> VoiceResult
        Convenience: record + process one chunk from live source
```

**Return format matches `_MEEFaceResult.to_dict()` schema:**
```python
{
    "emotion": str,       # best guess (e.g., "happy")
    "confidence": float,  # max score [0,1]
    "scores": {label: float},  # all 7 label scores summing to ~1.0
}
```

**Change marker:** `// TASK_MEE_005 Subtask 5: New VoiceProcessor pipeline class`

---

### Subtask 6: Engine Integration — `mee/api/engine.py`

**File:** `/home/deepsim/multimodal-emotion-engine/mee/api/engine.py`  
**Lines to modify:** ~138–141 (the `_infer_voice()` stub)

**Change at line 138-141:**
```python
# OLD (stub):
def _infer_voice(self, audio=None) -> dict | None:
    if not self._model_ready or audio is None:
        return None
    # Placeholder — will be replaced in TASK_MEE_003
    return {"emotion": "neutral", "confidence": 0.0, "scores": {}}

# NEW (replaced by Implementer):
def _infer_voice(self, audio=None) -> dict | None:
    """TASK_MEE_005: Real voice inference via VoiceProcessor."""
    if not self._model_ready or audio is None:
        return None
    
    vp = self._ensure_voice()
    if vp is None:
        # Graceful degradation — no voice model available
        return {"emotion": "neutral", "confidence": 0.0, "scores": {label: 0.0 for label in VOICE_LABELS}}
    
    result = vp.process(audio, self.config.audio_sample_rate)
    return {
        "emotion": result.emotion,
        "confidence": result.confidence,
        "scores": result.scores,
    }

# Also add _ensure_voice() method after _ensure_vision():
def _ensure_voice(self):
    """TASK_MEE_005: Lazy-load the voice processor (one-time cost)."""
    if not hasattr(self, '_voice_processor') or self._voice_processor is None:
        try:
            from ..voice.processor import VoiceProcessor
            self._voice_processor = VoiceProcessor()
        except Exception:
            self._voice_processor = None  # graceful degradation
    return self._voice_processor

# Also add class-level init for voice processor at ~line 65-66 (after _vision_processor):
self._voice_processor = None  # TASK_MEE_005: lazy-loaded VoiceProcessor
```

**Also update docstring at line 6:**
```python
# OLD: "TASK_MEE_004: Vision path wired..." 
# NEW: "TASK_MEE_004+005: Vision + Voice paths wired to their respective submodules"
```

**Change marker:** `// TASK_MEE_005 Subtask 6: Wire VoiceProcessor into EmotionEngine._infer_voice()` and add _ensure_voice()`

---

### Subtask 7: Unit Tests — `tests/test_voice.py` (~12 tests, ~200 lines)

**File:** `tests/test_voice.py` (NEW)

```python
# === Test A: FeatureExtractor Interface ===
def test_feature_extractor_interface():
    """FeatureExtractor.extract returns dict with all 10 feature names."""
    
# === Test B: MFCC Features Present ===  
def test_mfcc_features_present():
    """mfcc_mean and mfcc_std keys present; values are numpy scalars."""

# === Test C: FeatureVector Consistency ===
def test_feature_vector_consistent():
    """Same audio → same features (deterministic)."""

# === Test D: AudioRecorder.record() Valid Output ===
def test_recorder_record_valid():
    """AudioRecorder with known buffer returns list[AudioRecord] with correct sr."""

# === Test E: Voice Emotion Model Interface ===
def test_emotion_model_interface():
    """EmotionModel.predict() returns VoiceResult with valid structure."""

# === Test F: Voice Label Set ===
def test_voice_label_set():
    """VOICE_LABELS has exactly 7 labels matching MEE canonical set."""

# === Test G: Degraded Model Returns Neutral ===
def test_emotion_model_degraded():
    """When no backend available, returns neutral/0.0/all-zeros."""

# === Test H: VoiceProcessor With Valid Audio ===
def test_processor_with_audio(fake_models):
    """Full pipeline with fake feature extractor + emotion model returns valid result."""

# === Test I: Process Audio Alias ===
def test_process_audio_alias():
    """VoiceProcessor.process_audio_chunk() delegates to process()."""

# === Test J: VoiceProcessor No Audio (Empty) ===
def test_processor_no_audio():
    """process(None) or empty array returns degraded result."""

# === Test K: Processor Degraded Emotion ===
def test_processor_degraded_emotion(fake_models):
    """Degraded emotion model → neutral with zero scores."""

# === Test L: Feature Vector Dimensionality ===
def test_feature_vector_dimensionality():
    """extract() returns dict with exactly 10 feature names."""
```

**Test mocking strategy:** Use `unittest.mock.patch` for speechbrain/torchaudio to avoid heavy dependencies in CI. Create fake model stubs that return controlled VoiceResults for test G-J-L.

**Change marker:** `// TASK_MEE_005 Subtask 7: New test_voice.py with 12 tests covering all voice components`

---

## 4. Architecture Integration Diagram

```
EmotionEngine.process(audio=...)
    │
    ▼
_infer_voice(audio)
    │
    ├── _ensure_voice() → VoiceProcessor() [lazy init]
    │       └── [speechbrain or Wav2Vec available?]
    │           ├── Yes: VoiceProcessor._loaded = True
    │           └── No:  return None (graceful degradation)
    │
    ▼
VoiceProcessor.process(audio, sr=16000)
    │
    ├── FeatureExtractor.extract() → dict[str,float] (~42-dim features)
    │   Uses librosa for: MFCC, spectral, ZCR, RMS, pitch, HNR
    │
    └── EmotionModel.predict(audio, features) → VoiceResult
        ├── Primary: SpeechBrain RavNet (audio → emotion probs)
        ├── Fallback: Wav2Vec 2.0-base (if speechbrain unavailable)
        └── Degraded: neutral/0.0/all-zeros (if neither available)
    │
    ▼
{"emotion": str, "confidence": float, "scores": {label: float}}
    │
    └── Consumed by _fuse() for multimodal fusion (MEE_006)
```

---

## 5. Model Download Notes

- **SpeechBrain RavNet checkpoint:** ~100–200 MB on first use (downloaded from HuggingFace hub to `~/.cache/huggingface/hub/`)
- **Wav2Vec fallback:** ~350 MB base model + emotion head weights
- **Model caching:** SpeechBrain caches in HF hub; subsequent runs are instant
- **First-run delay:** ~10–30 seconds for download on typical broadband

---

## 6. Acceptance Criteria Verification Plan

| Criterion | How Verified | Test Reference |
|---|---|---|
| Given audio → returns voice emotion + confidence (+ scores) | Integration test with synthetic audio + fake model | Test A, F, G |
| Given None audio → no voice result (not error) | Unit: empty/None input branch | Test I |
| Acoustic features extracted; transcript not used | Code review: feature.py uses librosa only | Test B, C, L |
| Graceful degradation when backend missing | Unit: mock speechbrain unavailable → neutral | Test E |
| Public API unchanged | Verify process() signature identical to pre-task | Diff against 2d6edcc |
| Existing tests pass | Run `pytest tests/` — all previous tests must pass | CI check |

---

## 7. Gate G1 Decision Requested

**Recommend: PASS G1** — plan covers all requirements, provides exact file/symbol guidance, includes fallback strategy and license verification. Implementation can proceed immediately.
