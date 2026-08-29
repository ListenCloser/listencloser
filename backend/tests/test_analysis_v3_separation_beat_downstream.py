from __future__ import annotations

import sys
from types import SimpleNamespace

from backend.evaluation.analysis_v3.separation import beat_downstream, run_beat_downstream
import numpy as np
import pytest


def test_compare_mixture_vs_drums_reuses_production_estimator_and_pulse_metrics(monkeypatch):
    predicted = iter(
        [
            (120.0, [0.0, 1.0]),
            (120.0, [0.0, 0.5, 1.0, 1.5]),
        ]
    )
    calls: list[bytes] = []

    def fake_estimate_beat_grid(wav_bytes: bytes):
        calls.append(wav_bytes)
        return next(predicted)

    monkeypatch.setitem(
        sys.modules,
        "music_features",
        SimpleNamespace(estimate_beat_grid=fake_estimate_beat_grid),
    )

    reference = [0.0, 0.5, 1.0, 1.5]
    audio = np.zeros(4410, dtype=np.float32)
    comparison = beat_downstream.compare_mixture_vs_drums(
        audio,
        audio,
        44100,
        reference,
    )

    assert len(calls) == 2
    assert all(payload.startswith(b"RIFF") for payload in calls)
    assert comparison.drums.f1 > comparison.mixture.f1
    assert comparison.drums.reference_coverage > comparison.mixture.reference_coverage
    assert comparison.f1_delta == pytest.approx(
        comparison.drums.f1 - comparison.mixture.f1
    )


def test_score_requires_reference_beats():
    audio = np.zeros(100, dtype=np.float32)
    with pytest.raises(ValueError, match="reference_beats"):
        beat_downstream.score_production_beat_grid(audio, 44100, [])


def test_audio_to_wav_bytes_accepts_channel_first_stereo():
    audio = np.zeros((2, 100), dtype=np.float32)
    assert beat_downstream._audio_to_wav_bytes(audio, 44100).startswith(b"RIFF")


def test_comparison_serializes_localization_and_coverage():
    mixture = beat_downstream._score_estimated_beats(
        [0.0, 1.0],
        [0.0, 0.5, 1.0, 1.5],
    )
    drums = beat_downstream._score_estimated_beats(
        [0.01, 0.51, 1.01, 1.51],
        [0.0, 0.5, 1.0, 1.5],
    )
    payload = beat_downstream.BeatDownstreamComparison(mixture=mixture, drums=drums).to_dict()

    assert payload["drums"]["reference_coverage"] == 1.0
    assert payload["drums"]["absolute_median_error_seconds"] == pytest.approx(0.01)
    assert payload["f1_delta"] > 0


def test_reference_beats_excludes_end_exclusive_boundary(monkeypatch):
    monkeypatch.setattr(
        run_beat_downstream.pretty_midi,
        "PrettyMIDI",
        lambda _: SimpleNamespace(get_beats=lambda: np.array([0.0, 59.5, 60.0])),
    )

    assert run_beat_downstream._reference_beats("fixture.mid", end_seconds=60.0) == [0.0, 59.5]


def test_reference_beats_rejects_non_positive_excerpt():
    with pytest.raises(ValueError, match="end_seconds must be positive"):
        run_beat_downstream._reference_beats("fixture.mid", end_seconds=0.0)
