"""TASK_MEE_005 Subtask 7: Unit tests for Voice submodule."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import numpy as np


class TestFeatureExtractorInterface(unittest.TestCase):
    """Test A: FeatureExtractor.extract returns dict with all feature names."""
    
    def test_extract_returns_dict(self):
        from mee.voice.features import FeatureExtractor
        fe = FeatureExtractor()
        audio = np.zeros(16000, dtype=np.float32)
        result = fe.extract(audio)
        self.assertIsInstance(result, dict)
    
    def test_all_feature_names_present(self):
        from mee.voice.features import FeatureExtractor, AUDIO_FEATURES
        fe = FeatureExtractor()
        audio = np.zeros(16000, dtype=np.float32)
        result = fe.extract(audio)
        for name in AUDIO_FEATURES:
            self.assertIn(name, result, f"Feature '{name}' missing from extract output")


class TestFeatureVectorConsistency(unittest.TestCase):
    """Test C: Same audio → same features (deterministic)."""
    
    def test_deterministic(self):
        from mee.voice.features import FeatureExtractor
        fe = FeatureExtractor()
        # Use a reproducible signal — sine wave at 440 Hz
        sr = 16000
        t = np.arange(32000) / sr  # 2 seconds
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        result1 = fe.extract(audio)
        result2 = fe.extract(audio)
        
        for key in result1:
            self.assertEqual(result1[key], result2[key], f"Non-deterministic feature: {key}")


class TestAudioRecorder(unittest.TestCase):
    """Test D: AudioRecorder.record() valid output."""
    
    def test_record_buffer(self):
        from mee.voice.recorder import AudioRecorder
        recorder = AudioRecorder(sample_rate=16000)
        audio = np.random.randn(32000).astype(np.float32)
        records = recorder.record(audio)
        
        self.assertIsInstance(records, list)
        if len(records) > 0:
            for rec in records:
                self.assertAlmostEqual(rec.duration, recorder.chunk_duration, places=1)


class TestEmotionModelInterface(unittest.TestCase):
    """Test E: EmotionModel.predict() returns VoiceResult-like dict."""
    
    def test_predict_returns_valid_structure(self):
        from mee.voice.emotion_model import EmotionModel, VOICE_LABELS, VoiceResult
        
        with patch.object(EmotionModel, '_ensure_loaded'):
            model = EmotionModel()
            audio = np.zeros(16000, dtype=np.float32)
            result = model.predict(audio)
            
            self.assertIsInstance(result, VoiceResult)
            self.assertIn("emotion", dir(result))
            self.assertIsInstance(result.confidence, float)
            self.assertIsInstance(result.scores, dict)
    
    def test_label_set(self):
        from mee.voice.emotion_model import VOICE_LABELS
        
        expected = ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]
        self.assertEqual(VOICE_LABELS, expected)
        
        scores_keys = list(["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"])
        self.assertEqual(set(scores_keys), set(VOICE_LABELS))


class TestDegradedEmotionModel(unittest.TestCase):
    """Test G: Degraded model returns neutral."""
    
    def test_degraded_returns_neutral(self):
        from mee.voice.emotion_model import EmotionModel
        
        # When no backend, predict with None → degraded
        model = EmotionModel()
        result = model.predict(None)
        
        self.assertEqual(result.emotion, "neutral")
        self.assertEqual(result.confidence, 0.0)


class TestVoiceProcessor(unittest.TestCase):
    """Test H: VoiceProcessor.process() full pipeline."""
    
    def test_process_with_valid_audio(self):
        from mee.voice.processor import VoiceProcessor
        
        vp = VoiceProcessor()
        audio = np.random.randn(16000).astype(np.float32)
        result = vp.process(audio, sample_rate=16000)
        
        self.assertIn("emotion", result)
        self.assertIn("confidence", result)
        self.assertIn("scores", result)
        self.assertIsInstance(result["emotion"], str)
    
    def test_process_audio_chunk_alias(self):
        from mee.voice.processor import VoiceProcessor
        
        vp = VoiceProcessor()
        # process_audio_chunk requires sounddevice; just verify it doesn't crash on import
        # Actually, call the method which will return None if no mic
        result = vp.process_audio_chunk(duration_seconds=0.1)
        # Returns None when mic unavailable — that's fine
        self.assertIsNone(result)


class TestVoiceProcessorNoAudio(unittest.TestCase):
    """Test I: VoiceProcessor.process(None) returns degraded."""
    
    def test_no_audio_returns_degraded(self):
        from mee.voice.processor import VoiceProcessor
        
        vp = VoiceProcessor()
        result = vp.process(None, 16000)
        
        self.assertEqual(result["emotion"], "neutral")
        self.assertEqual(result["confidence"], 0.0)


class TestProcessorDegradedEmotion(unittest.TestCase):
    """Test K: Degraded emotion model → neutral with zero scores."""
    
    def test_degraded_neutral_zero_scores(self):
        from mee.voice.emotion_model import EmotionModel, VOICE_LABELS
        
        model = EmotionModel()
        result = model._degraded_result()
        
        self.assertEqual(result.emotion, "neutral")
        self.assertEqual(result.confidence, 0.0)
        for label in VOICE_LABELS:
            self.assertEqual(result.scores.get(label, -1), 0.0)


class TestProcessorChannelScoresStructure(unittest.TestCase):
    """Test L: Voice output scores have all 7 labels as keys."""
    
    def test_scores_keys(self):
        from mee.voice.processor import VoiceProcessor
        
        vp = VoiceProcessor()
        result = vp.process(None, 16000)
        
        expected_labels = ["angry", "disgust", "fear", "happy", "sad", "surprised", "neutral"]
        for label in expected_labels:
            self.assertIn(label, result["scores"], f"Score key '{label}' missing")


class TestProcessorMultipleAudio(unittest.TestCase):
    """Test M: process() with various audio shapes."""
    
    def test_empty_array(self):
        from mee.voice.processor import VoiceProcessor
        
        vp = VoiceProcessor()
        result = vp.process(np.array([], dtype=np.float32), 16000)
        
        self.assertEqual(result["emotion"], "neutral")
        self.assertEqual(result["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()


class TestIntegrationNoRealModels(unittest.TestCase):
    """Test N: Integration — verify degraded path when no real models installed."""

    def test_no_real_models_installed(self):
        """Verify that without speechbrain/wav2vec, the system degrades correctly."""
        from mee.voice.emotion_model import EmotionModel, VOICE_LABELS

        model = EmotionModel()
        has_backend = model._speechbrain_available or model._wav2vec_available

        if not has_backend:
            # With no real models, predict should return neutral/0.0
            import numpy as np
            audio = np.random.randn(16000).astype(np.float32)
            result = model.predict(audio)

            self.assertEqual(result.emotion, "neutral")
            self.assertEqual(result.confidence, 0.0)
            for label in VOICE_LABELS:
                self.assertEqual(result.scores[label], 0.0)
            # This is correct behavior — not a bug when speechbrain isn't installed
        else:
            # Backend importable but model may be unavailable (HF blocked, no network).
            # predict must NOT raise — it must return a valid VoiceResult.
            import numpy as np
            audio = np.random.randn(16000).astype(np.float32)
            result = model.predict(audio)
            self.assertIn(result.emotion, VOICE_LABELS)
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 1.0)
            for label in VOICE_LABELS:
                self.assertIn(label, result.scores)
                self.assertGreaterEqual(result.scores[label], 0.0)


if __name__ == "__main__":
    unittest.main()
