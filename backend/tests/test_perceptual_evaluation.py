from __future__ import annotations

import numpy as np
import pytest

from backend.evaluation.analysis_v3.perceptual.features import (
    extract_baseline_perceptual_evidence,
    onset_strength_series,
    relative_band_energy_series,
    rms_series,
    spectral_centroid_series,
)


SAMPLE_RATE = 22_050


def _sine(frequency_hz: float, duration_seconds: float, amplitude: float = 1.0) -> np.ndarray:
    times = np.arange(int(SAMPLE_RATE * duration_seconds), dtype=float) / SAMPLE_RATE
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * times)


def _values_in_window(series, start_seconds: float, end_seconds: float) -> np.ndarray:
    times = np.asarray(series.frame_times_seconds)
    values = np.asarray(series.values)
    mask = np.logical_and(times >= start_seconds, times <= end_seconds)
    assert np.any(mask)
    return values[mask]


def test_rms_tracks_controlled_amplitude_step() -> None:
    audio = np.concatenate([_sine(440.0, 1.0, 0.1), _sine(440.0, 1.0, 0.8)])

    series = rms_series(audio, SAMPLE_RATE)

    quiet = float(np.median(_values_in_window(series, 0.2, 0.8)))
    loud = float(np.median(_values_in_window(series, 1.2, 1.8)))
    assert loud / quiet == pytest.approx(8.0, rel=0.03)
    assert series.unit == "linear_amplitude"
    assert series.normalization == "none"


def test_spectral_centroid_tracks_frequency_shift() -> None:
    audio = np.concatenate([_sine(220.0, 1.0), _sine(4_000.0, 1.0)])

    series = spectral_centroid_series(audio, SAMPLE_RATE)

    low = float(np.median(_values_in_window(series, 0.2, 0.8)))
    high = float(np.median(_values_in_window(series, 1.2, 1.8)))
    assert low == pytest.approx(220.0, abs=8.0)
    assert high == pytest.approx(4_000.0, abs=20.0)
    assert high > low * 10


def test_relative_band_energy_distinguishes_low_and_high_frequency_content() -> None:
    low_series = relative_band_energy_series(_sine(100.0, 2.0), SAMPLE_RATE)
    high_series = relative_band_energy_series(_sine(6_000.0, 2.0), SAMPLE_RATE)

    low_values = np.median(_values_in_window(low_series, 0.2, 1.8), axis=0)
    high_values = np.median(_values_in_window(high_series, 0.2, 1.8), axis=0)

    band_order = low_series.parameters["band_order"]
    assert band_order == ["low", "low_mid", "mid", "high"]
    assert low_values[0] > 0.98
    assert high_values[3] > 0.98
    assert low_values[3] < 0.01
    assert high_values[0] < 0.01


def test_relative_band_energy_is_stable_under_global_gain_change() -> None:
    audio = _sine(100.0, 2.0)
    original = relative_band_energy_series(audio, SAMPLE_RATE)
    quieter = relative_band_energy_series(audio * 0.2, SAMPLE_RATE)

    original_values = _values_in_window(original, 0.2, 1.8)
    quieter_values = _values_in_window(quieter, 0.2, 1.8)

    np.testing.assert_allclose(original_values, quieter_values, atol=1e-5, rtol=1e-5)
    assert original.normalization == "per_frame_total_stft_power"


def test_onset_strength_rises_for_denser_impulse_activity() -> None:
    audio = np.zeros(SAMPLE_RATE * 4, dtype=np.float32)
    for seconds in np.arange(0.25, 2.0, 0.5):
        audio[int(seconds * SAMPLE_RATE)] = 1.0
    for seconds in np.arange(2.05, 4.0, 0.125):
        audio[int(seconds * SAMPLE_RATE)] = 1.0

    series = onset_strength_series(audio, SAMPLE_RATE)

    sparse = float(np.mean(_values_in_window(series, 0.2, 1.9)))
    dense = float(np.mean(_values_in_window(series, 2.1, 3.9)))
    assert dense > sparse * 2


def test_baseline_bundle_preserves_measured_feature_metadata() -> None:
    evidence = extract_baseline_perceptual_evidence(_sine(440.0, 1.0), SAMPLE_RATE)

    assert set(evidence) == {
        "rms",
        "spectral_centroid",
        "relative_band_energy",
        "onset_strength",
    }
    for series in evidence.values():
        assert series.channel_mode == "mono"
        assert len(series.frame_times_seconds) == len(series.values)
        assert series.to_dict()["feature"] == series.feature


def test_perceptual_evaluation_fails_closed_for_stereo_until_spatial_contract_exists() -> None:
    stereo = np.stack([_sine(440.0, 1.0), _sine(440.0, 1.0)], axis=0)

    with pytest.raises(ValueError, match="requires mono audio"):
        extract_baseline_perceptual_evidence(stereo, SAMPLE_RATE)


def test_perceptual_evaluation_rejects_invalid_audio() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        rms_series(np.asarray([], dtype=np.float32), SAMPLE_RATE)
    with pytest.raises(ValueError, match="positive"):
        rms_series(_sine(440.0, 1.0), 0)
    with pytest.raises(ValueError, match="finite"):
        rms_series(np.asarray([0.0, np.nan], dtype=np.float32), SAMPLE_RATE)
