"""Evaluation-only perceptual audio evidence primitives for Analysis V3.

These helpers intentionally expose measured audio descriptors, not semantic
interpretations. A high spectral centroid is not called "bright", a high RMS is
not called "exciting", and raw descriptor values are not treated as calibrated
confidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import librosa
import numpy as np


@dataclass(frozen=True)
class FeatureSeries:
    """A time-localized measured descriptor with explicit normalization metadata."""

    feature: str
    frame_times_seconds: list[float]
    values: list[float] | list[list[float]]
    unit: str | None
    normalization: str
    channel_mode: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float32)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if samples.ndim != 1:
        raise ValueError("perceptual evaluation currently requires mono audio")
    if samples.size == 0:
        raise ValueError("audio must contain at least one sample")
    if not np.isfinite(samples).all():
        raise ValueError("audio must contain only finite samples")
    return samples


def _frame_times(n_frames: int, sample_rate: int, hop_length: int) -> list[float]:
    frames = np.arange(n_frames, dtype=int)
    return librosa.frames_to_time(frames, sr=sample_rate, hop_length=hop_length).tolist()


def rms_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> FeatureSeries:
    """Frame RMS amplitude without semantic interpretation."""
    samples = _validate_audio(audio, sample_rate)
    values = librosa.feature.rms(
        y=samples,
        frame_length=frame_length,
        hop_length=hop_length,
        center=True,
    )[0]
    return FeatureSeries(
        feature="rms",
        frame_times_seconds=_frame_times(len(values), sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="linear_amplitude",
        normalization="none",
        channel_mode="mono",
        parameters={"frame_length": frame_length, "hop_length": hop_length},
    )


def spectral_centroid_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> FeatureSeries:
    """Frame spectral centroid in Hz."""
    samples = _validate_audio(audio, sample_rate)
    values = librosa.feature.spectral_centroid(
        y=samples,
        sr=sample_rate,
        n_fft=n_fft,
        hop_length=hop_length,
        center=True,
    )[0]
    return FeatureSeries(
        feature="spectral_centroid",
        frame_times_seconds=_frame_times(len(values), sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="hz",
        normalization="none",
        channel_mode="mono",
        parameters={"n_fft": n_fft, "hop_length": hop_length},
    )


def relative_band_energy_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = 2048,
    hop_length: int = 512,
    bands_hz: tuple[tuple[str, float, float | None], ...] = (
        ("low", 20.0, 250.0),
        ("low_mid", 250.0, 1000.0),
        ("mid", 1000.0, 4000.0),
        ("high", 4000.0, None),
    ),
) -> FeatureSeries:
    """Relative spectral power by coarse frequency band.

    Each frame is normalized by its total STFT power, making this evidence
    substantially less sensitive to a global gain change than absolute energy.
    Silent frames are returned as all-zero band ratios.
    """
    samples = _validate_audio(audio, sample_rate)
    stft = librosa.stft(samples, n_fft=n_fft, hop_length=hop_length, center=True)
    power = np.abs(stft) ** 2
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)
    total_power = power.sum(axis=0)

    band_rows: list[np.ndarray] = []
    band_names: list[str] = []
    nyquist = sample_rate / 2.0
    for name, low_hz, high_hz in bands_hz:
        upper = nyquist if high_hz is None else min(float(high_hz), nyquist)
        lower = max(0.0, float(low_hz))
        if upper <= lower:
            raise ValueError(f"invalid or empty frequency band {name!r}")
        mask = np.logical_and(frequencies >= lower, frequencies < upper)
        if not np.any(mask):
            raise ValueError(f"frequency band {name!r} contains no FFT bins")
        band_power = power[mask].sum(axis=0)
        ratio = np.divide(
            band_power,
            total_power,
            out=np.zeros_like(band_power, dtype=float),
            where=total_power > 0,
        )
        band_rows.append(ratio)
        band_names.append(name)

    values = np.stack(band_rows, axis=1)
    return FeatureSeries(
        feature="relative_band_energy",
        frame_times_seconds=_frame_times(values.shape[0], sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="fraction_of_frame_power",
        normalization="per_frame_total_stft_power",
        channel_mode="mono",
        parameters={
            "n_fft": n_fft,
            "hop_length": hop_length,
            "bands": [
                {"name": name, "low_hz": low, "high_hz": high} for name, low, high in bands_hz
            ],
            "band_order": band_names,
        },
    )


def onset_strength_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    hop_length: int = 512,
) -> FeatureSeries:
    """Librosa onset-strength envelope as localized transient/activity evidence."""
    samples = _validate_audio(audio, sample_rate)
    values = librosa.onset.onset_strength(y=samples, sr=sample_rate, hop_length=hop_length)
    return FeatureSeries(
        feature="onset_strength",
        frame_times_seconds=_frame_times(len(values), sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="librosa_onset_strength",
        normalization="librosa_default_log_power_mel_flux",
        channel_mode="mono",
        parameters={"hop_length": hop_length},
    )


def extract_baseline_perceptual_evidence(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> dict[str, FeatureSeries]:
    """Extract the deliberately small first-round #455 evidence set."""
    _validate_audio(audio, sample_rate)
    return {
        "rms": rms_series(
            audio,
            sample_rate,
            frame_length=n_fft,
            hop_length=hop_length,
        ),
        "spectral_centroid": spectral_centroid_series(
            audio,
            sample_rate,
            n_fft=n_fft,
            hop_length=hop_length,
        ),
        "relative_band_energy": relative_band_energy_series(
            audio,
            sample_rate,
            n_fft=n_fft,
            hop_length=hop_length,
        ),
        "onset_strength": onset_strength_series(
            audio,
            sample_rate,
            hop_length=hop_length,
        ),
    }
