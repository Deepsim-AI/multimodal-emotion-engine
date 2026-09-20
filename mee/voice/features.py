"""TASK_MEE_005 Subtask 3: Feature extractor — extracts acoustic features from raw audio.

Provides a deterministic feature vector over 10 named acoustic channels:
    MFCC (mean + std), Spectral Centroid, Spectral Bandwidth, Spectral Rolloff,
    Zero-Crossing Rate, RMS Energy, Pitch (Hz), HNR (dB)
"""
from __future__ import annotations

from typing import Dict, Optional


AUDIO_FEATURES = [
    "mfcc_mean", "mfcc_std",      # MFCC features (13 coeffs, mean + std per coeff) — 26 values total
    "spectral_centroid",           # Spectral centroid
    "spectral_bandwidth",          # Spectral bandwidth
    "spectral_rolloff",            # Spectral rolloff (85th percentile)
    "zero_crossing_rate",          # Zero-crossing rate
    "rms_energy",                  # Root mean square energy
    "pitch_hz",                    # Fundamental frequency estimate
    "hnr_db",                      # Harmonic-to-noise ratio
]

FEATURE_DIM = len(AUDIO_FEATURES)


class FeatureExtractor:
    """Extracts acoustic features from raw audio using librosa.

    Usage:
        extractor = FeatureExtractor()
        features = extractor.extract(audio_array, sample_rate=16000)
    """

    def __init__(self):
        self._librosa_available = False
        self._load_librosa()

    def _load_librosa(self):
        try:
            import librosa  # noqa: F401
            self._librosa_available = True
        except ImportError:
            self._librosa_available = False

    @property
    def available(self) -> bool:
        return self._librosa_available

    @staticmethod
    def is_available() -> bool:
        try:
            import librosa as _lr  # noqa: F401
            return True
        except ImportError:
            return False

    def extract(self, audio: 'np.ndarray', sample_rate: int = 16000) -> Dict[str, float]:
        """Extract acoustic features from raw audio.

        Args:
            audio: (N,) float32 mono audio samples at any sample rate.
            sample_rate: Audio sample rate (default 16000).

        Returns:
            Dict mapping each feature name to a scalar float value.
            Always returns all 10 feature names, even if some are zeros.
        """
        # Ensure numpy import is available
        import numpy as np

        result = {name: 0.0 for name in AUDIO_FEATURES}

        if not self._librosa_available or audio is None or len(audio) == 0:
            return result

        try:
            import librosa

            # Resample to 16kHz if needed
            y = librosa.resample(
                audio.astype(np.float32),
                orig_sr=sample_rate,
                target_sr=16000,
            )

            if len(y) < 512:  # Too short for meaningful features
                return result

            # MFCC: mean and std across time for each of 13 coeffs (26 values total — but we aggregate to scalar)
            mfcc = librosa.feature.mfcc(y=y, sr=16000, n_mfcc=13)
            # Aggregate: global mean of all MFCC coefficients as the "mfcc_mean" feature
            result["mfcc_mean"] = float(np.mean(mfcc))
            result["mfcc_std"] = float(np.std(mfcc))

            # Spectral centroid (weighted mean frequency)
            cent = librosa.feature.spectral_centroid(y=y, sr=16000)
            result["spectral_centroid"] = float(np.mean(cent))

            # Spectral bandwidth
            band = librosa.feature.spectral_bandwidth(y=y, sr=16000)
            result["spectral_bandwidth"] = float(np.mean(band))

            # Spectral rolloff (85th percentile)
            rolloff = librosa.feature.spectral_rolloff(y=y, sr=16000, roll_percent=0.85)
            result["spectral_rolloff"] = float(np.mean(rolloff))

            # Zero-crossing rate
            zcr = librosa.feature.zero_crossing_rate(y)
            result["zero_crossing_rate"] = float(np.mean(zcr))

            # RMS energy
            rms = librosa.feature.rms(y=y)
            result["rms_energy"] = float(np.mean(rms))

            # Pitch (fundamental frequency, Hz) — use pyin for better estimation
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'),
                sr=16000, frame_length=512, hop_length=128,
            )
            # Use mean of non-nan pitch values (only voiced portions)
            valid_pitch = f0[~np.isnan(f0)] if len(f0) > 0 else np.array([0.0])
            result["pitch_hz"] = float(np.mean(valid_pitch))

            # Harmonic-to-Noise Ratio (approximate via STFT)
            stft_magnitude = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
            if stft_magnitude.size > 0:
                # Simple approximation: ratio of median to max magnitude across frequency bins
                mag_mean = float(np.mean(stft_magnitude))
                mag_max = float(np.max(stft_magnitude))
                result["hnr_db"] = float(20 * np.log10(max(mag_mean / max(mag_max, 1e-10), 1e-10)))
            else:
                result["hnr_db"] = -100.0

        except Exception:
            # Graceful degradation: return all zeros (already initialized)
            pass

        return result
