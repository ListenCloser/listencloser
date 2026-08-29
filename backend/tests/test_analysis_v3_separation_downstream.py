from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from backend.evaluation.analysis_v3.separation.metrics import downstream, separation


def test_compare_beat_f1_uses_production_estimator_and_canonical_metric(monkeypatch):
    calls: list[tuple[list[float], list[float], float]] = []
    predicted_sequences = iter(
        [
            (120.0, [0.0, 0.5, 1.0]),
            (120.0, [0.0, 0.5, 1.0, 1.5]),
        ]
    )

    def fake_estimate_beat_grid(_wav_bytes: bytes):
        return next(predicted_sequences)

    fake_music_features = SimpleNamespace(estimate_beat_grid=fake_estimate_beat_grid)
    monkeypatch.setitem(sys.modules, "music_features", fake_music_features)

    def fake_f_measure(reference, estimated, f_measure_threshold):
        calls.append((reference.tolist(), estimated.tolist(), f_measure_threshold))
        return len(estimated) / 10.0

    fake_mir_eval = SimpleNamespace(beat=SimpleNamespace(f_measure=fake_f_measure))
    monkeypatch.setitem(sys.modules, "mir_eval", fake_mir_eval)

    audio = np.zeros(4410, dtype=np.float32)
    result = downstream.compare_beat_f1_mixture_vs_stem(
        audio,
        audio,
        44100,
        [0.0, 0.5, 1.0, 1.5],
    )

    assert result is not None
    assert result.mixture_score == 0.3
    assert result.stem_score == 0.4
    assert result.delta == pytest.approx(0.1)
    assert calls == [
        ([0.0, 0.5, 1.0, 1.5], [0.0, 0.5, 1.0], 0.07),
        ([0.0, 0.5, 1.0, 1.5], [0.0, 0.5, 1.0, 1.5], 0.07),
    ]


def test_compare_beat_f1_withholds_without_reference_annotations():
    audio = np.zeros(100, dtype=np.float32)
    assert downstream.compare_beat_f1_mixture_vs_stem(audio, audio, 44100, None) is None
    assert downstream.compare_beat_f1_mixture_vs_stem(audio, audio, 44100, []) is None


def test_audio_to_wav_bytes_accepts_channel_first_stereo():
    audio = np.zeros((2, 100), dtype=np.float32)
    wav_bytes = downstream._audio_to_wav_bytes(audio, 44100)
    assert wav_bytes.startswith(b"RIFF")


def test_si_sdr_comparison_measures_gain_over_mixture():
    sample_rate = 8000
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    reference = np.sin(2.0 * np.pi * 220.0 * time)
    interference = 0.7 * np.sin(2.0 * np.pi * 440.0 * time)
    mixture = reference + interference
    estimated_stem = reference + 0.1 * interference

    result = separation.compare_si_sdr_mixture_vs_stem(
        mixture,
        estimated_stem,
        reference,
    )

    assert result is not None
    assert result.stem_si_sdr_db > result.mixture_si_sdr_db
    assert result.improvement_db == pytest.approx(20.0, abs=0.01)


def test_si_sdr_withholds_completely_silent_reference():
    audio = np.ones(100, dtype=np.float32)
    silent_reference = np.zeros(100, dtype=np.float32)
    assert separation.compute_si_sdr(audio, silent_reference) is None


def test_si_sdr_accepts_mismatched_channel_layouts_by_folding_to_mono():
    base = np.linspace(-1.0, 1.0, 100)
    reference = np.stack([base, 0.5 * base], axis=1)
    estimated = reference.mean(axis=1)

    score = separation.compute_si_sdr(estimated, reference)

    assert score is not None
    assert np.isfinite(score)
