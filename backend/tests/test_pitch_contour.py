import numpy as np
import pytest

from engines.pitch.pyin import frames_from_estimates, hz_to_midi_cents


def test_hz_to_midi_cents_uses_a440_absolute_reference():
    assert hz_to_midi_cents(440.0) == pytest.approx(6900.0)
    assert hz_to_midi_cents(220.0) == pytest.approx(5700.0)


def test_frames_preserve_coordinates_voicing_probability_and_unvoiced_nulls():
    frames = frames_from_estimates(
        np.array([440.0, np.nan, 445.0]),
        np.array([True, False, True]),
        np.array([0.98, 0.04, 0.91]),
        sample_rate_hz=22050,
        hop_length_samples=220,
    )

    assert frames[0] == {
        "frame": 0,
        "time_seconds": 0.0,
        "pitch_hz": 440.0,
        "pitch_cents": pytest.approx(6900.0),
        "voiced": True,
        "voiced_probability": 0.98,
    }
    assert frames[1]["time_seconds"] == pytest.approx(220 / 22050)
    assert frames[1]["pitch_hz"] is None
    assert frames[1]["pitch_cents"] is None
    assert frames[1]["voiced"] is False
    assert frames[1]["voiced_probability"] == pytest.approx(0.04)
    assert frames[2]["frame"] == 2
    assert frames[2]["pitch_hz"] == pytest.approx(445.0)
