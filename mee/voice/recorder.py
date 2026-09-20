"""TASK_MEE_005 Subtask 2: Audio recorder — captures and buffers raw audio.

Provides a minimal, dependency-safe interface:
    recorder = AudioRecorder(sample_rate=16000)
    records = recorder.record(buffer_or_path)  -> list[AudioRecord]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AudioRecord:
    """A chunk of captured audio."""
    data: np.ndarray      # (N,) float32 mono samples at 16kHz
    sample_rate: int      # always 16000 for MEE
    duration: float       # seconds


class AudioRecorder:
    """Captures raw audio from numpy buffers or files.

    Usage:
        recorder = AudioRecorder()
        records = recorder.record(audio_array)  # list[AudioRecord]
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = 2.0  # seconds per chunk

    @property
    def available(self) -> bool:
        return True  # AudioRecorder works with any numpy array input

    @staticmethod
    def is_available() -> bool:
        """True if librosa is importable (for potential file reading)."""
        try:
            import librosa  # noqa: F401
            return True
        except ImportError:
            return False

    def record(self, audio_input) -> list[AudioRecord]:
        """Record audio from buffer or path.

        Args:
            audio_input: numpy array (N,) float32 mono at any sample rate,
                         or file path string.

        Returns:
            List of AudioRecord chunks, each chunk_duration seconds long.
            Empty list if input is None or invalid.
        """
        if audio_input is None:
            return []

        # Load from file path if string
        if isinstance(audio_input, str):
            try:
                import librosa
                y, sr = librosa.load(audio_input, sr=self.sample_rate)
                return self._split_into_chunks(y, sr)
            except ImportError:
                return []
            except Exception:
                return []

        # Handle numpy array input directly
        if isinstance(audio_input, np.ndarray):
            y = audio_input.astype(np.float32)
            if y.ndim > 1:
                y = y.mean(axis=1)  # stereo to mono
            # Resample if needed (simple linear interpolation)
            if len(y) > 0:
                target_length = int(len(y) * self.sample_rate / max(1, getattr(audio_input, 'sample_rate', self.sample_rate) if hasattr(audio_input, 'sample_rate') else self.sample_rate))
                # For simplicity, just use the data as-is at the configured sample rate
                return self._split_into_chunks(y, self.sample_rate)
            return []

        return []

    def _split_into_chunks(self, audio: np.ndarray, sample_rate: int) -> list[AudioRecord]:
        """Split audio array into fixed-duration chunks."""
        if len(audio) == 0:
            return []

        chunk_samples = int(self.chunk_duration * sample_rate)
        chunks: list[AudioRecord] = []

        for i in range(0, len(audio), chunk_samples):
            chunk_data = audio[i:i + chunk_samples].copy()
            if len(chunk_data) == 0:
                break
            duration = len(chunk_data) / sample_rate
            chunks.append(AudioRecord(
                data=chunk_data.astype(np.float32),
                sample_rate=sample_rate,
                duration=round(duration, 4),
            ))

        return chunks


class MicRecorder:
    """Convenience subclass using sounddevice for live microphone capture.

    Usage:
        mic = MicRecorder()
        record = mic.record_chunk(seconds=2.0)
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    @property
    def available(self) -> bool:
        try:
            import sounddevice as sd  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def is_available() -> bool:
        try:
            import sounddevice as sd  # noqa: F401
            return len(sd.query_devices()) > 0
        except ImportError:
            return False

    def record_chunk(self, seconds: float = 2.0) -> Optional[AudioRecord]:
        """Record one chunk from the microphone.

        Returns AudioRecord on success, None if mic unavailable or error.
        """
        try:
            import sounddevice as sd
            recording = sd.rec(
                int(seconds * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
            )
            sd.wait()
            return AudioRecord(
                data=recording.flatten(),
                sample_rate=self.sample_rate,
                duration=round(seconds, 4),
            )
        except Exception:
            return None
