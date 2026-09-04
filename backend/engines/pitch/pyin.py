"""Continuous F0 extraction for the experimental Pitch contour surface."""

from __future__ import annotations

import io
import math
from typing import Any

import librosa
import numpy as np
import soundfile as sf

FMIN_HZ = 50.0
FMAX_HZ = 1600.0
FRAME_LENGTH = 2048
HOP_SECONDS = 0.01


def hz_to_midi_cents(hz: float) -> float:
    """Return absolute MIDI cents (A4=6900 at 440 Hz)."""
    if hz <= 0 or not math.isfinite(hz):
        raise ValueError("pitch frequency must be finite and positive")
    return 6900.0 + 1200.0 * math.log2(hz / 440.0)


def _finite_or_none(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def frames_from_estimates(
    f0_hz: np.ndarray,
    voiced_flag: np.ndarray,
    voiced_probability: np.ndarray,
    *,
    sample_rate_hz: int,
    hop_length_samples: int,
) -> list[dict[str, Any]]:
    """Serialize pYIN arrays without leaking NaN into persisted JSON."""
    frames: list[dict[str, Any]] = []
    for index, (pitch, is_voiced, probability) in enumerate(
        zip(f0_hz, voiced_flag, voiced_probability, strict=True)
    ):
        hz = _finite_or_none(float(pitch))
        frames.append(
            {
                "frame": index,
                "time_seconds": index * hop_length_samples / sample_rate_hz,
                "pitch_hz": hz,
                "pitch_cents": hz_to_midi_cents(hz) if hz is not None else None,
                "voiced": bool(is_voiced) and hz is not None,
                "voiced_probability": _finite_or_none(float(probability)),
            }
        )
    return frames


def estimate_pitch_contour(wav_bytes: bytes) -> dict[str, Any]:
    """Estimate a continuous monophonic F0 track from canonical decoded WAV bytes."""
    audio, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    if audio.size == 0 or sample_rate <= 0:
        raise ValueError("decoded audio is empty or has an invalid sample rate")

    input_channels = int(audio.shape[1])
    mono = np.mean(audio, axis=1, dtype=np.float32)
    hop_length = max(1, int(round(sample_rate * HOP_SECONDS)))

    f0_hz, voiced_flag, voiced_probability = librosa.pyin(
        mono,
        sr=sample_rate,
        fmin=FMIN_HZ,
        fmax=FMAX_HZ,
        frame_length=FRAME_LENGTH,
        hop_length=hop_length,
        center=True,
        fill_na=np.nan,
    )

    return {
        "engine": {
            "name": "librosa",
            "version": librosa.__version__,
            "method": "pyin",
            "model": "algorithmic pYIN; no learned checkpoint",
            "license": "ISC",
        },
        "preprocessing": {
            "input_channels": input_channels,
            "downmix": "mean" if input_channels > 1 else "already_mono",
            "sample_rate_hz": int(sample_rate),
            "frame_length_samples": FRAME_LENGTH,
            "hop_length_samples": hop_length,
            "hop_seconds": hop_length / sample_rate,
            "fmin_hz": FMIN_HZ,
            "fmax_hz": FMAX_HZ,
            "centered_frames": True,
            "pitch_cents_reference": "absolute MIDI cents; A4=440 Hz=6900 cents",
        },
        "frames": frames_from_estimates(
            f0_hz,
            voiced_flag,
            voiced_probability,
            sample_rate_hz=sample_rate,
            hop_length_samples=hop_length,
        ),
    }
