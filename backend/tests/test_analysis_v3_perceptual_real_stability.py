from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf
from backend.evaluation.analysis_v3.perceptual.run_real_stability import probe_track

SAMPLE_RATE = 22_050


def _sine(duration_seconds: float, frequency_hz: float = 440.0) -> np.ndarray:
    times = np.arange(int(SAMPLE_RATE * duration_seconds), dtype=float) / SAMPLE_RATE
    return np.sin(2.0 * np.pi * frequency_hz * times).astype(np.float32)


def test_real_stability_probe_reports_expected_gain_behavior(tmp_path) -> None:
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
    assert result["resampled"]["target_sample_rate"] == 16_000
    assert result["boundary_shift"] is None


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
