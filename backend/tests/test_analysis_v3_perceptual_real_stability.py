from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf
from backend.evaluation.analysis_v3.perceptual.run_real_stability import (
    CANONICAL_SAMPLE_RATE,
    probe_track,
)

SAMPLE_RATE = 22_050


def _sine(duration_seconds: float, frequency_hz: float = 440.0) -> np.ndarray:
    times = np.arange(int(SAMPLE_RATE * duration_seconds), dtype=float) / SAMPLE_RATE
    return np.sin(2.0 * np.pi * frequency_hz * times).astype(np.float32)


def test_real_stability_probe_reports_expected_gain_and_canonical_behavior(tmp_path) -> None:
    path = tmp_path / "tone.wav"
    sf.write(path, _sine(2.0), SAMPLE_RATE)

    result = probe_track(path)

    rms_gain = result["gain_x0_5"]["rms"]
    assert rms_gain["perturbed_median"] / rms_gain["reference_median"] == pytest.approx(
        0.5,
        rel=0.01,
    )
    assert result["gain_x0_5"]["relative_band_energy"]["delta"] == pytest.approx(
        [0.0, 0.0, 0.0, 0.0],
        abs=1e-5,
    )
    assert result["native_sample_rate_diagnostic"]["target_sample_rate"] == 16_000
    assert result["canonical_preprocessing"]["sample_rate"] == CANONICAL_SAMPLE_RATE
    assert result["canonical_preprocessing"]["channel_mode"] == "mono"
    assert result["boundary_shift"] is None


def test_canonical_codec_comparison_uses_same_sample_rate(tmp_path) -> None:
    original = tmp_path / "tone-44100.wav"
    variant = tmp_path / "tone-16000.wav"

    times_44k = np.arange(44_100 * 2, dtype=float) / 44_100
    audio_44k = np.sin(2.0 * np.pi * 440.0 * times_44k).astype(np.float32)
    times_16k = np.arange(16_000 * 2, dtype=float) / 16_000
    audio_16k = np.sin(2.0 * np.pi * 440.0 * times_16k).astype(np.float32)
    sf.write(original, audio_44k, 44_100)
    sf.write(variant, audio_16k, 16_000)

    result = probe_track(original, codec_variant=variant)

    assert result["sample_rate"] == 44_100
    assert result["codec_variant"]["sample_rate"] == 16_000
    canonical = result["codec_variant"]["canonical_aggregate_delta"]
    assert abs(canonical["spectral_centroid"]["relative_delta"]) < 0.01
    assert abs(canonical["rms"]["relative_delta"]) < 0.01


def test_real_stability_probe_reports_boundary_sensitivity_for_long_audio(tmp_path) -> None:
    audio = np.concatenate(
        [
            _sine(8.0, 220.0) * 0.2,
            _sine(8.0, 2_000.0) * 0.8,
        ]
    )
    path = tmp_path / "two-state.wav"
    sf.write(path, audio, SAMPLE_RATE)

    result = probe_track(path)

    boundary = result["boundary_shift"]
    assert boundary is not None
    assert boundary["shift_seconds"] == 0.5
    assert set(boundary["features"]) == {
        "onset_strength",
        "relative_band_energy",
        "rms",
        "spectral_centroid",
    }
    assert result["baseline"]["relative_band_energy"]["frames"] > 0
