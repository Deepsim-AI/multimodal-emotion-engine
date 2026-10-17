"""TASK_MEE_005 Subtask 4: Emotion model — acoustic emotion classification.

Primary: SpeechBrain EncoderClassifier (emotion-recognition-wav2vec2-IEMOCAP)
Fallback: Wav2Vec 2.0-base + emotion head (transformers, MIT license)
Degraded: neutral/0.0/all-zeros when no backend available

NOTE: The IEMOCAP model's hyperparams.yaml was authored for SpeechBrain 0.x and
is incompatible with SpeechBrain 1.1.x's `EncoderClassifier.classify_batch` (missing
`compute_features` module). We therefore load the model with `from_hparams` and run
inference by calling the submodules directly (wav2vec2 -> avg_pool -> output_mlp),
which is verified working end-to-end.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np


def _cuda() -> bool:
    """Return True if a CUDA device is actually usable right now."""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


VOICE_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]


@dataclass
class VoiceResult:
    """Structured emotion prediction from voice."""
    emotion: str = "neutral"
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "emotion": self.emotion,
            "confidence": self.confidence,
            "scores": self.scores,
        }


class EmotionModel:
    """Acoustic emotion classification using SpeechBrain or Wav2Vec.

    Usage:
        model = EmotionModel()
        result = model.predict(audio_array, sample_rate=16000)
    """

    # Label mapping: SpeechBrain IEMOCAP native → MEE canonical
    # The IEMOCAP wav2vec2 model outputs 4 labels: neu, ang, hap, sad.
    LABEL_MAP: Dict[str, str] = {
        # IEMOCAP model labels
        "neu": "neutral",
        "ang": "angry",
        "hap": "happy",
        "sad": "sad",
        # Passthrough in case a different 7-label model is supplied
        "angry": "angry",
        "disgust": "disgust",
        "fear": "fear",
        "happy": "happy",
        "sad": "sad",
        "surprised": "surprised",
        "neutral": "neutral",
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
    ):
        self.model_path = model_path or os.path.expanduser(
            "~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP"
        )
        self.device = device
        self._model = None
        self._processor = None
        self._backend: Optional[str] = None
        self._initialized = False
        self._speechbrain_available = False
        self._wav2vec_available = False
        self._init_backends()

    def _init_backends(self):
        """Detect available backends."""
        try:
            import speechbrain  # noqa: F401
            self._speechbrain_available = True
        except ImportError:
            self._speechbrain_available = False

        try:
            import transformers  # noqa: F401
            self._wav2vec_available = True
        except ImportError:
            self._wav2vec_available = False

    @property
    def available(self) -> bool:
        return self._speechbrain_available or self._wav2vec_available

    @staticmethod
    def is_available() -> bool:
        try:
            import speechbrain  # noqa: F401
            return True
        except ImportError:
            try:
                import transformers  # noqa: F401
                return True
            except ImportError:
                return False

    def _ensure_loaded(self) -> None:
        """Load the emotion model on first call (lazy init).

        TASK_MEE_010: Added TensorRT engine auto-detection — if a `.trt` or
        `.int8.onnx` file exists alongside the model directory, it is loaded
        via ONNX Runtime with TensorRT/CUDA providers before falling back to
        PyTorch backends.
        """
        if self._initialized:
            return
        self._initialized = True

        # TASK_MEE_010: Try TensorRT / ONNX Runtime engine first (Jetson GPU path)
        if self._model is None:
            trt_path = self._find_tensorrt_engine()
            if trt_path is not None:
                try:
                    import onnxruntime as ort
                    providers = [p for p in [
                        "TensorrtExecutionProvider",
                        "CUDAExecutionProvider",
                        "CPUExecutionProvider",
                    ] if p in ort.get_available_providers()]
                    self._model = ort.InferenceSession(
                        str(trt_path), providers=providers
                    )
                    self._backend = "tensorrt"
                    self._onnx_labels = ["neutral", "angry", "happy", "sad"]
                    return
                except Exception as e:
                    print(f"[MEE-Voice] TensorRT engine load failed, falling back: {e}")

        # Try SpeechBrain first (primary per MEE_003 CTO_APPROVAL)
        if self._speechbrain_available and self._model is None:
            try:
                import os
                from speechbrain.inference.classifiers import EncoderClassifier

                # Local savedir alongside buffalo_l — no re-download needed.
                savedir = os.path.expanduser(
                    "~/.insightface/models/emotion-recognition-wav2vec2-IEMOCAP"
                )
                os.makedirs(savedir, exist_ok=True)

                self._model = EncoderClassifier.from_hparams(
                    source=self.model_path,
                    savedir=savedir,
                    run_opts={"device": self.device if self.device != "cuda" or not _cuda() else "cuda"},
                )
                self._model.eval()
                self._backend = "speechbrain"
                return
            except Exception as e:
                print(f"[MEE-Voice] SpeechBrain load failed: {e}")

        # Try Wav2Vec fallback
        if self._wav2vec_available and self._model is None:
            try:
                from transformers import (  # noqa: PLC0412
                    AutoModelForAudioClassification,
                    AutoProcessor,
                )
                self._processor = AutoProcessor.from_pretrained(
                    "facebook/wav2vec2-base-960h"
                )
                self._model = AutoModelForAudioClassification.from_pretrained(
                    "facebook/wav2vec2-base-960h"
                )
                self._model.eval()
                self._backend = "wav2vec"
                return
            except Exception as e:
                print(f"[MEE-Voice] Wav2Vec fallback failed: {e}")

        # No backend available — model stays None (degraded mode)
        self._model = None
        self._backend = None

    def predict(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        features: Optional[Dict[str, float]] = None,
    ) -> VoiceResult:
        """Predict emotion from raw audio.

        Args:
            audio: (N,) float32 mono audio samples at ~16kHz.
            sample_rate: Audio sample rate (default 16000).
            features: Optional precomputed acoustic features (unused in V1, preserved for future).

        Returns:
            VoiceResult with emotion, confidence, and scores over VOICE_LABELS.
        """
        if audio is None or len(audio) == 0:
            return self._degraded_result()

        self._ensure_loaded()

        if self._model is None:
            return self._degraded_result()

        try:
            if self._backend == "tensorrt":
                return self._predict_tensorrt(audio, sample_rate)
            elif self._backend == "speechbrain":
                return self._predict_speechbrain(audio, sample_rate)
            elif self._backend == "wav2vec":
                return self._predict_wav2vec(audio, sample_rate)
            else:
                return self._degraded_result()

        except Exception as e:
            # On inference error, degrade to neutral
            print(f"[MEE-Voice] Inference error: {e}")
            return self._degraded_result()

    # TASK_MEE_010: locate a TRT / INT8-ONNX engine next to the model dir
    def _find_tensorrt_engine(self):
        """Return path to a TensorRT or INT8-ONNX engine, or None.

        Looks for:  <model_dir>/emotion_iemocap.int8.onnx
                    <model_dir>/emotion_iemocap.onnx  (used with TRT EP via ORT)
                    <model_dir>/*.trt
        """
        import glob
        base = os.path.dirname(os.path.abspath(self.model_path))
        candidates = [
            os.path.join(base, "emotion_iemocap.int8.onnx"),
            os.path.join(base, "emotion_iemocap.onnx"),
        ]
        candidates += sorted(glob.glob(os.path.join(base, "*.trt")))
        for c in candidates:
            if os.path.isfile(c) and c.endswith((".onnx", ".trt")):
                if c.endswith(".onnx"):
                    try:
                        import onnxruntime as ort
                        gpu_providers = [p for p in ort.get_available_providers()
                                        if p in ("TensorrtExecutionProvider", "CUDAExecutionProvider")]
                        if not gpu_providers:
                            continue  # CPU-only ORT — prefer PyTorch backend instead
                    except ImportError:
                        continue
                return c
        return None

    def _predict_tensorrt(self, audio: np.ndarray, sample_rate: int) -> VoiceResult:
        """TASK_MEE_010: TensorRT / ONNX Runtime inference path.

        Input:  [1, T] float32 audio at 16 kHz
        Output: [1, N] logits — softmax → canonical labels via LABEL_MAP
        """
        arr = np.ascontiguousarray(audio, dtype=np.float32).reshape(1, -1)
        inp_name = self._model.get_inputs()[0].name
        logits = self._model.run(None, {inp_name: arr})[0].flatten()

        z = logits - logits.max()
        exp_z = np.exp(z)
        probs = exp_z / exp_z.sum()

        labels = getattr(self, "_onnx_labels", ["neutral", "angry", "happy", "sad"])
        if len(labels) != len(probs):
            labels = [str(i) for i in range(len(probs))]

        best_idx = int(np.argmax(probs))
        best_raw = labels[best_idx].lower()
        canonical = self.LABEL_MAP.get(best_raw, best_raw)
        if canonical not in VOICE_LABELS:
            canonical = "neutral"

        scores = {label: 0.0 for label in VOICE_LABELS}
        for i, (raw, p) in enumerate(zip(labels, probs)):
            c = self.LABEL_MAP.get(raw.lower(), raw.lower())
            if c in scores:
                scores[c] = round(float(p), 6)

        return VoiceResult(
            emotion=canonical,
            confidence=round(float(probs[best_idx]), 4),
            scores=scores,
        )

    def _predict_speechbrain(self, audio: np.ndarray, sample_rate: int) -> VoiceResult:
        """Run emotion prediction via SpeechBrain IEMOCAP wav2vec2 model.

        Because the IEMOCAP hyperparams.yaml targets SpeechBrain 0.x, the 1.1.x
        `classify_batch` path fails on the missing `compute_features` module. We
        therefore run the submodules directly, which is verified working:

            wav2vec2(raw) -> last_hidden_state -> avg_pool -> output_mlp -> logits

        `output_mlp` returns raw logits (not softmax); we softmax for probabilities.
        Labels come from the model's `label_encoder` (ind2lab: neu/ang/hap/sad).
        """
        import torch

        wav = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)  # [1, T]

        with torch.no_grad():
            out = self._model.mods.wav2vec2(wav)
            emb = out.last_hidden_state if hasattr(out, "last_hidden_state") else out
            n_steps = emb.shape[1]  # time dimension
            kernel = getattr(self._model.mods.avg_pool, "kernel", None)
            if kernel is None:
                # Default SpeechBrain avg_pool kernel size
                kernel = 2
            if n_steps < kernel:
                raise ValueError(f"avg_pool kernel ({kernel}) > input timesteps ({n_steps}); "
                                 f"audio segment too short for emotion detection")
            emb = self._model.mods.avg_pool(emb, torch.ones(emb.shape[0], device=emb.device))
            logits = self._model.mods.output_mlp(emb).flatten()  # -> [N]

        logits = logits.detach().cpu().numpy().astype(np.float64)
        n_classes = logits.shape[-1]

        # Numerically stable softmax
        z = logits - np.max(logits)
        exp_z = np.exp(z)
        probs = exp_z / exp_z.sum()

        # Resolve model labels from label_encoder (attribute-style access)
        le = getattr(self._model.hparams, "label_encoder", None)
        model_labels: list = []
        if le is not None and hasattr(le, "ind2lab"):
            try:
                model_labels = [str(le.ind2lab.get(i, le.ind2lab[i])) for i in range(n_classes)]
            except Exception:
                model_labels = []
        if len(model_labels) != n_classes:
            model_labels = [str(i) for i in range(n_classes)]

        best_idx = int(np.argmax(probs))
        best_label = model_labels[best_idx].lower()
        canonical_label = self.LABEL_MAP.get(best_label, best_label)
        if canonical_label not in VOICE_LABELS:
            canonical_label = "neutral"

        # Build scores over VOICE_LABELS (zero-filled, then populated).
        scores = {label: 0.0 for label in VOICE_LABELS}
        for i, (model_label, p) in enumerate(zip(model_labels, probs)):
            canonical = self.LABEL_MAP.get(str(model_label).lower(), str(model_label).lower())
            if canonical in scores:
                scores[canonical] = round(float(p), 6)

        return VoiceResult(
            emotion=canonical_label,
            confidence=round(float(probs[best_idx]), 4),
            scores=scores,
        )

    def _predict_wav2vec(self, audio: np.ndarray, sample_rate: int) -> VoiceResult:
        """Run emotion prediction via Wav2Vec 2.0."""
        import torch

        inputs = self._processor(
            audio.astype(np.float32).tolist(),
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True,
        )

        if self.device == "cuda" and torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items() if isinstance(v, torch.Tensor)}

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits[0].detach().cpu().numpy()

        # Softmax with numerical stability
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()
        label_idx = int(np.argmax(probs))
        confidence = float(probs[label_idx])

        # Wav2Vec default emotion labels: ang, dis, fear, hap, neu, sad, sur
        wb_labels_map = {
            "ang": "angry",
            "dis": "disgust",
            "fear": "fear",
            "hap": "happy",
            "neu": "neutral",
            "sad": "sad",
            "sur": "surprised",
        }

        label_names = self._model.config.id2label if hasattr(self._model.config, "id2label") else {}
        raw_label = label_names.get(label_idx, "")
        canonical_label = wb_labels_map.get(raw_label, raw_label)
        if canonical_label not in VOICE_LABELS:
            canonical_label = "neutral"

        scores = {label: 0.0 for label in VOICE_LABELS}
        label2id = self._model.config.label2id if hasattr(self._model.config, "label2id") else {}
        for label_name, idx in label2id.items():
            if idx < len(probs):
                canonical = wb_labels_map.get(label_name, label_name)
                if canonical in scores:
                    scores[canonical] = round(float(probs[idx]), 6)

        return VoiceResult(
            emotion=canonical_label,
            confidence=round(confidence, 4),
            scores=scores,
        )

    def _degraded_result(self) -> VoiceResult:
        """Safe fallback when no backend or error occurs."""
        scores = {label: 0.0 for label in VOICE_LABELS}
        return VoiceResult(
            emotion="neutral",
            confidence=0.0,
            scores=scores,
        )
