"""Bounded experimental production/spatial measurements for one source recording."""

from __future__ import annotations

import io
import math
import os
import subprocess
import tempfile
import wave
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from audio_processing import _max_decoded_audio_seconds, _sanitize_fmt
from domain.production_spatial_report import (
    METHOD_ID,
    ProductionSpatialMethod,
    ProductionSpatialRelation,
    ProductionSpatialRelationKind,
    ProductionSpatialReport,
    ProductionSpatialWindow,
)

SAMPLE_RATE = 48_000
WINDOW_SECONDS = 3.0
MIN_WINDOW_SECONDS = 1.0
N_FFT = 2048
HOP_LENGTH = 512
_FFMPEG_TIMEOUT = 120
_DECODE_OVERFLOW_PROBE_SECONDS = 1.0
_EPSILON = 1e-12


def _package_version(name: str, fallback: str = "unknown") -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return fallback


def _decode_preserving_channels(audio_bytes: bytes, *, fmt: str) -> tuple[np.ndarray, int]:
    if not audio_bytes:
        raise ValueError("audio bytes must not be empty")
    suffix = _sanitize_fmt(fmt)
    max_duration = _max_decoded_audio_seconds()
    with tempfile.TemporaryDirectory() as td:
        input_path = os.path.join(td, f"input{suffix}")
        output_path = os.path.join(td, "decoded.wav")
        with open(input_path, "wb") as handle:
            handle.write(audio_bytes)
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    input_path,
                    "-t",
                    str(max_duration + _DECODE_OVERFLOW_PROBE_SECONDS),
                    "-ar",
                    str(SAMPLE_RATE),
                    "-c:a",
                    "pcm_s16le",
                    output_path,
                ],
                capture_output=True,
                timeout=_FFMPEG_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Audio decoding failed") from error
        if result.returncode != 0 or not os.path.exists(output_path):
            detail = result.stderr.decode(errors="replace")[-300:]
            raise ValueError(f"Audio decoding failed: {detail or 'invalid audio file'}")
        try:
            with wave.open(output_path, "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                duration = wav_file.getnframes() / frame_rate if frame_rate > 0 else 0.0
        except (OSError, wave.Error) as error:
            raise ValueError("Audio decoding produced an invalid WAV") from error
        if duration > max_duration:
            raise ValueError(f"Audio exceeds maximum duration of {max_duration:g} seconds")
        with open(output_path, "rb") as handle:
            payload = handle.read()

    samples, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    if int(sample_rate) != SAMPLE_RATE:
        raise ValueError(f"decoded audio has unexpected sample rate {sample_rate}")
    if samples.size == 0 or samples.shape[0] < SAMPLE_RATE:
        raise ValueError("audio is too short for production/spatial analysis")
    if not np.isfinite(samples).all():
        raise ValueError("audio must contain only finite samples")
    return np.asarray(samples, dtype=np.float32), int(sample_rate)


def _safe_loudness(meter: pyln.Meter, samples: np.ndarray) -> float | None:
    try:
        value = float(meter.integrated_loudness(samples))
    except (FloatingPointError, ValueError, ZeroDivisionError):
        return None
    return round(value, 3) if math.isfinite(value) else None


def _side_energy_fraction(samples: np.ndarray) -> float | None:
    if samples.ndim != 2 or samples.shape[1] != 2:
        return None
    left = samples[:, 0].astype(np.float64)
    right = samples[:, 1].astype(np.float64)
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    mid_rms = math.sqrt(float(np.mean(mid * mid)))
    side_rms = math.sqrt(float(np.mean(side * side)))
    total_power = mid_rms * mid_rms + side_rms * side_rms
    if total_power <= _EPSILON:
        return None
    return round((side_rms * side_rms) / total_power, 6)


def _mono_for_spectral(samples: np.ndarray) -> np.ndarray:
    return np.mean(samples, axis=1, dtype=np.float64).astype(np.float32)


def _window_measurements(
    samples: np.ndarray,
    sample_rate: int,
    *,
    window_seconds: float,
) -> list[ProductionSpatialWindow]:
    meter = pyln.Meter(sample_rate)
    window_samples = max(1, round(window_seconds * sample_rate))
    minimum_samples = max(1, round(MIN_WINDOW_SECONDS * sample_rate))
    rows: list[ProductionSpatialWindow] = []
    duration = samples.shape[0] / sample_rate

    for start_sample in range(0, samples.shape[0], window_samples):
        end_sample = min(samples.shape[0], start_sample + window_samples)
        if end_sample - start_sample < minimum_samples:
            break
        chunk = samples[start_sample:end_sample]
        mono = _mono_for_spectral(chunk)
        centroid = librosa.feature.spectral_centroid(
            y=mono,
            sr=sample_rate,
            n_fft=N_FFT,
            hop_length=HOP_LENGTH,
        )[0]
        onset = librosa.onset.onset_strength(y=mono, sr=sample_rate, hop_length=HOP_LENGTH)
        rows.append(
            ProductionSpatialWindow(
                start_seconds=round(start_sample / sample_rate, 3),
                end_seconds=round(min(duration, end_sample / sample_rate), 3),
                loudness_lufs=_safe_loudness(meter, chunk if chunk.shape[1] > 1 else chunk[:, 0]),
                side_energy_fraction=_side_energy_fraction(chunk),
                spectral_centroid_hz=round(float(np.mean(centroid)), 3),
                onset_strength_mean=round(float(np.mean(onset)) if onset.size else 0.0, 6),
            )
        )
    return rows


def _largest_adjacent_relation(
    windows: list[ProductionSpatialWindow],
    *,
    kind: ProductionSpatialRelationKind,
    field: str,
    label: str,
    method: str,
    unit: str,
    precision: int,
    scale: float = 1.0,
) -> ProductionSpatialRelation | None:
    best: tuple[float, ProductionSpatialWindow, ProductionSpatialWindow, float] | None = None
    for previous, current in zip(windows[:-1], windows[1:], strict=False):
        previous_value = getattr(previous, field)
        current_value = getattr(current, field)
        if previous_value is None or current_value is None:
            continue
        delta = float(current_value) - float(previous_value)
        candidate = (abs(delta), previous, current, delta)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return None
    _, previous, current, delta = best
    return ProductionSpatialRelation(
        kind=kind,
        label=label,
        method=method,
        unit=unit,
        delta=round(delta * scale, precision),
        start_seconds=previous.start_seconds,
        end_seconds=current.end_seconds,
        from_start_seconds=previous.start_seconds,
        from_end_seconds=previous.end_seconds,
        to_start_seconds=current.start_seconds,
        to_end_seconds=current.end_seconds,
    )


def build_production_spatial_report(
    samples: np.ndarray,
    *,
    sample_rate: int,
    source_version_id: UUID,
    window_seconds: float = WINDOW_SECONDS,
) -> ProductionSpatialReport:
    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[0] == 0 or audio.shape[1] == 0:
        raise ValueError("production_spatial requires non-empty samples shaped (frames, channels)")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if window_seconds < MIN_WINDOW_SECONDS:
        raise ValueError(f"window_seconds must be at least {MIN_WINDOW_SECONDS:g}")

    windows = _window_measurements(audio, sample_rate, window_seconds=window_seconds)
    if len(windows) < 2:
        raise ValueError("audio is too short for adjacent-window production/spatial relations")

    relation_specs = [
        (
            "loudness_change",
            "loudness_lufs",
            "Loudness",
            "pyloudnorm BS.1770 integrated loudness per fixed window; largest adjacent delta",
            "LUFS",
            2,
        ),
        (
            "mid_side_change",
            "side_energy_fraction",
            "Side energy share",
            "side RMS² / (mid RMS² + side RMS²) per fixed stereo window; largest adjacent delta",
            "percentage points",
            1,
        ),
        (
            "spectral_change",
            "spectral_centroid_hz",
            "Spectral centroid",
            "librosa spectral centroid mean per fixed window; largest adjacent delta",
            "Hz",
            1,
        ),
        (
            "transient_change",
            "onset_strength_mean",
            "Onset strength",
            "librosa onset-strength mean per fixed window; largest adjacent delta",
            "librosa onset strength",
            3,
        ),
    ]
    relations = [
        relation
        for spec in relation_specs
        if (relation := _largest_adjacent_relation(
            windows,
            kind=spec[0],
            field=spec[1],
            label=spec[2],
            method=spec[3],
            unit=spec[4],
            precision=spec[5],
            scale=100.0 if spec[0] == "mid_side_change" else 1.0,
        ))
        is not None
    ]

    return ProductionSpatialReport(
        source_version_id=source_version_id,
        duration_seconds=round(audio.shape[0] / sample_rate, 3),
        channel_count=int(audio.shape[1]),
        method=ProductionSpatialMethod(
            pyloudnorm_version=_package_version(
                "pyloudnorm", str(getattr(pyln, "__version__", "unknown"))
            ),
            librosa_version=_package_version(
                "librosa", str(getattr(librosa, "__version__", "unknown"))
            ),
            parameters={
                "sample_rate": sample_rate,
                "window_seconds": window_seconds,
                "minimum_window_seconds": MIN_WINDOW_SECONDS,
                "n_fft": N_FFT,
                "hop_length": HOP_LENGTH,
            },
        ),
        windows=windows,
        relations=relations,
    )


def extract_production_spatial_from_bytes(
    audio_bytes: bytes,
    *,
    source_version_id: UUID,
    fmt: str,
) -> ProductionSpatialReport:
    samples, sample_rate = _decode_preserving_channels(audio_bytes, fmt=fmt)
    return build_production_spatial_report(
        samples,
        sample_rate=sample_rate,
        source_version_id=source_version_id,
    )


__all__ = ["METHOD_ID", "build_production_spatial_report", "extract_production_spatial_from_bytes"]
