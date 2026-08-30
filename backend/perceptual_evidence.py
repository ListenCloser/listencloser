"""Production-owned measured perceptual audio evidence.

This module contains the small descriptor set validated by Analysis V3 #455/#468.
It emits literal measured series only. It does not convert descriptor values into
semantic adjectives, affect, section labels, or causal musical explanations.
"""

from __future__ import annotations

import io
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

import librosa
import numpy as np
import soundfile as sf

from audio_processing import decode_audio_to_wav
from domain.perceptual_report import (
    CANONICAL_SAMPLE_RATE as CANONICAL_SAMPLE_RATE,
    DEFAULT_HOP_LENGTH as DEFAULT_HOP_LENGTH,
    DEFAULT_N_FFT as DEFAULT_N_FFT,
    FeatureName as FeatureName,
    MeasuredFeatureSeries as MeasuredFeatureSeries,
    PREPROCESSING_VERSION as PREPROCESSING_VERSION,
    PerceptualEvidenceReport as PerceptualEvidenceReport,
    PerceptualProvenance as PerceptualProvenance,
    PerceptualSeriesEvidence as PerceptualSeriesEvidence,
    REPORT_SCHEMA_VERSION as REPORT_SCHEMA_VERSION,
)

MIN_AUDIO_SAMPLES = DEFAULT_N_FFT


def _librosa_version() -> str:
    try:
        return version("librosa")
    except PackageNotFoundError:
        return str(getattr(librosa, "__version__", "unknown"))


def _validate_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float32)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if samples.ndim != 1:
        raise ValueError("perceptual evidence requires mono audio")
    if samples.size < MIN_AUDIO_SAMPLES:
        raise ValueError(
            f"audio must contain at least {MIN_AUDIO_SAMPLES} samples for perceptual evidence"
        )
    if not np.isfinite(samples).all():
        raise ValueError("audio must contain only finite samples")
    return samples


def canonicalize_audio_bytes(audio_bytes: bytes, *, fmt: str = "wav") -> np.ndarray:
    """Decode arbitrary supported audio into the one validated analysis contract."""
    if not audio_bytes:
        raise ValueError("audio bytes must not be empty")
    wav_bytes = decode_audio_to_wav(audio_bytes, fmt=fmt)
    samples, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
    if int(sample_rate) != CANONICAL_SAMPLE_RATE:
        raise ValueError(
            f"canonical decoder returned {sample_rate} Hz; expected {CANONICAL_SAMPLE_RATE} Hz"
        )
    return _validate_audio(np.asarray(samples), CANONICAL_SAMPLE_RATE)


def _frame_times(n_frames: int, sample_rate: int, hop_length: int) -> list[float]:
    frames = np.arange(n_frames, dtype=int)
    return librosa.frames_to_time(frames, sr=sample_rate, hop_length=hop_length).tolist()


def rms_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    frame_length: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> MeasuredFeatureSeries:
    """Frame RMS amplitude proxy; not calibrated loudness."""
    samples = _validate_audio(audio, sample_rate)
    values = librosa.feature.rms(
        y=samples,
        frame_length=frame_length,
        hop_length=hop_length,
        center=True,
    )[0]
    return MeasuredFeatureSeries(
        feature="rms",
        frame_times_seconds=_frame_times(len(values), sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="linear_amplitude",
        normalization="none",
        parameters={"frame_length": frame_length, "hop_length": hop_length},
    )


def spectral_centroid_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> MeasuredFeatureSeries:
    """Frame spectral center of mass in Hz."""
    samples = _validate_audio(audio, sample_rate)
    values = librosa.feature.spectral_centroid(
        y=samples,
        sr=sample_rate,
        n_fft=n_fft,
        hop_length=hop_length,
        center=True,
    )[0]
    return MeasuredFeatureSeries(
        feature="spectral_centroid",
        frame_times_seconds=_frame_times(len(values), sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="hz",
        normalization="none",
        parameters={"n_fft": n_fft, "hop_length": hop_length},
    )


def relative_band_energy_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
    bands_hz: tuple[tuple[str, float, float | None], ...] = (
        ("low", 20.0, 250.0),
        ("low_mid", 250.0, 1_000.0),
        ("mid", 1_000.0, 4_000.0),
        ("high", 4_000.0, None),
    ),
) -> MeasuredFeatureSeries:
    """Relative STFT power in coarse frequency bands for each frame."""
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
    return MeasuredFeatureSeries(
        feature="relative_band_energy",
        frame_times_seconds=_frame_times(values.shape[0], sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="fraction_of_frame_power",
        normalization="per_frame_total_stft_power",
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
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> MeasuredFeatureSeries:
    """Librosa onset-strength envelope as transient/activity evidence."""
    samples = _validate_audio(audio, sample_rate)
    values = librosa.onset.onset_strength(y=samples, sr=sample_rate, hop_length=hop_length)
    return MeasuredFeatureSeries(
        feature="onset_strength",
        frame_times_seconds=_frame_times(len(values), sample_rate, hop_length),
        values=values.astype(float).tolist(),
        unit="librosa_onset_strength",
        normalization="librosa_default_log_power_mel_flux",
        parameters={"hop_length": hop_length},
    )


def extract_measured_perceptual_series(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> dict[str, MeasuredFeatureSeries]:
    """Extract only the four feature families validated in #455/#468."""
    _validate_audio(audio, sample_rate)
    return {
        "rms": rms_series(audio, sample_rate, frame_length=n_fft, hop_length=hop_length),
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
        "onset_strength": onset_strength_series(audio, sample_rate, hop_length=hop_length),
    }


def build_perceptual_evidence_report(
    audio: np.ndarray,
    *,
    source_version_id: UUID,
    sample_rate: int = CANONICAL_SAMPLE_RATE,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> PerceptualEvidenceReport:
    """Attach production lineage, provenance, and applicability to measured series."""
    samples = _validate_audio(audio, sample_rate)
    if sample_rate != CANONICAL_SAMPLE_RATE:
        raise ValueError(
            f"production perceptual evidence requires {CANONICAL_SAMPLE_RATE} Hz audio"
        )

    measured = extract_measured_perceptual_series(
        samples,
        sample_rate,
        n_fft=n_fft,
        hop_length=hop_length,
    )
    engine_version = _librosa_version()
    series: dict[str, PerceptualSeriesEvidence] = {}
    for name, item in measured.items():
        limitations = []
        if name == "rms":
            limitations.append(
                "Amplitude proxy only; do not treat as calibrated loudness "
                "or compare across encodes."
            )
        if name == "relative_band_energy":
            limitations.append(
                "Span aggregates are localization-sensitive when boundaries cross changing content."
            )
        series[name] = PerceptualSeriesEvidence(
            **item.model_dump(),
            sample_rate=CANONICAL_SAMPLE_RATE,
            source_version_id=source_version_id,
            provenance=PerceptualProvenance(
                engine_version=engine_version,
                parameters={
                    "n_fft": n_fft,
                    "hop_length": hop_length,
                    **item.parameters,
                },
            ),
            limitations=limitations,
        )

    return PerceptualEvidenceReport(
        source_version_id=source_version_id,
        duration_seconds=float(len(samples) / CANONICAL_SAMPLE_RATE),
        series=series,
    )


def extract_perceptual_evidence_from_bytes(
    audio_bytes: bytes,
    *,
    source_version_id: UUID,
    fmt: str = "wav",
) -> PerceptualEvidenceReport:
    """Canonicalize uploaded audio bytes and return production evidence."""
    samples = canonicalize_audio_bytes(audio_bytes, fmt=fmt)
    return build_perceptual_evidence_report(
        samples,
        source_version_id=source_version_id,
        sample_rate=CANONICAL_SAMPLE_RATE,
    )
