from __future__ import annotations

import sys
from types import SimpleNamespace

from backend.evaluation.analysis_v3.separation.datasets import babyslakh_reference
from backend.evaluation.analysis_v3.separation.metrics import si_sdr
from backend.evaluation.analysis_v3.separation.run_sisdr_reference import _summarize
import numpy as np
import soundfile as sf


def test_si_sdr_comparison_uses_fast_bss_eval_and_reports_gain(monkeypatch):
    calls: list[tuple[tuple[int, ...], tuple[int, ...], bool, float]] = []
    scores = iter([3.0, 10.0])

    def fake_si_sdr(reference, estimated, zero_mean, clamp_db):
        calls.append((reference.shape, estimated.shape, zero_mean, clamp_db))
        return np.asarray([next(scores)], dtype=float)

    monkeypatch.setitem(sys.modules, "fast_bss_eval", SimpleNamespace(si_sdr=fake_si_sdr))

    reference = np.linspace(-1.0, 1.0, 100)
    mixture = reference + 0.5
    estimated_stem = reference + 0.1
    result = si_sdr.compare_si_sdr_mixture_vs_stem(mixture, estimated_stem, reference)

    assert result is not None
    assert result.mixture_si_sdr_db == 3.0
    assert result.stem_si_sdr_db == 10.0
    assert result.improvement_db == 7.0
    assert calls == [
        ((1, 100), (1, 100), True, 100.0),
        ((1, 100), (1, 100), True, 100.0),
    ]


def test_si_sdr_withholds_completely_silent_reference():
    assert (
        si_sdr.compute_si_sdr(
            np.ones(100, dtype=np.float32),
            np.zeros(100, dtype=np.float32),
        )
        is None
    )


def test_si_sdr_folds_mismatched_channels_to_mono(monkeypatch):
    calls: list[tuple[tuple[int, ...], tuple[int, ...]]] = []

    def fake_si_sdr(reference, estimated, zero_mean, clamp_db):
        calls.append((reference.shape, estimated.shape))
        return np.asarray([5.0], dtype=float)

    monkeypatch.setitem(sys.modules, "fast_bss_eval", SimpleNamespace(si_sdr=fake_si_sdr))

    base = np.linspace(-1.0, 1.0, 100)
    reference = np.stack([base, 0.5 * base], axis=1)
    estimated = reference.mean(axis=1)

    assert si_sdr.compute_si_sdr(estimated, reference) == 5.0
    assert calls == [((1, 100), (1, 100))]


def test_reference_path_filter_only_allows_required_track_files():
    assert (
        babyslakh_reference._safe_selected_relative_path(
            "babyslakh_16k/Track00001/mix.wav", "Track00001"
        ).as_posix()
        == "mix.wav"
    )
    assert (
        babyslakh_reference._safe_selected_relative_path(
            "babyslakh_16k/Track00001/stems/S01.wav", "Track00001"
        ).as_posix()
        == "stems/S01.wav"
    )
    assert (
        babyslakh_reference._safe_selected_relative_path(
            "babyslakh_16k/Track00002/stems/S01.wav", "Track00001"
        )
        is None
    )
    assert (
        babyslakh_reference._safe_selected_relative_path(
            "babyslakh_16k/Track00001/MIDI/S01.mid", "Track00001"
        )
        is None
    )


def test_build_reference_stems_groups_exact_isolated_sources(monkeypatch, tmp_path):
    track = tmp_path / "Track00001"
    (track / "stems").mkdir(parents=True)
    (track / "metadata.yaml").write_text("stub: true\n")

    sample_rate = 8000
    bass = np.full(80, 0.1, dtype=np.float32)
    drums = np.full(80, 0.2, dtype=np.float32)
    other = np.full(80, 0.3, dtype=np.float32)
    sf.write(track / "mix.wav", bass + drums + other, sample_rate)
    sf.write(track / "stems" / "S00.wav", bass, sample_rate)
    sf.write(track / "stems" / "S01.wav", drums, sample_rate)
    sf.write(track / "stems" / "S02.wav", other, sample_rate)

    monkeypatch.setattr(
        babyslakh_reference,
        "_load_metadata",
        lambda path: {
            "stems": {
                "S00": {"audio_rendered": True, "inst_class": "Bass", "is_drum": False},
                "S01": {"audio_rendered": True, "inst_class": "Drums", "is_drum": True},
                "S02": {"audio_rendered": True, "inst_class": "Piano", "is_drum": False},
            }
        },
    )

    mixture_path, references, counts = babyslakh_reference.build_reference_stems(
        track,
        excerpt_seconds=0.01,
    )

    assert mixture_path == track / "mix.wav"
    assert counts == {"drums": 1, "bass": 1, "other": 1}
    assert set(references) == {"drums", "bass", "other"}
    mixed_bass, sr = sf.read(references["bass"], dtype="float32")
    assert sr == sample_rate
    assert len(mixed_bass) == 80
    assert np.allclose(mixed_bass, bass)


def test_summary_keeps_missing_reference_separate_from_scored():
    rows = [
        {
            "stems": {
                "vocals": {"state": "missing_reference"},
                "drums": {"state": "scored", "improvement_db": 2.0},
                "bass": {"state": "scored", "improvement_db": -1.0},
                "other": {"state": "withheld_silent_reference"},
            }
        },
        {
            "stems": {
                "vocals": {"state": "missing_reference"},
                "drums": {"state": "scored", "improvement_db": 4.0},
                "bass": {"state": "missing_reference"},
                "other": {"state": "scored", "improvement_db": 1.0},
            }
        },
    ]

    summary = _summarize(rows)

    assert summary["drums"]["scored_tracks"] == 2
    assert summary["drums"]["mean_improvement_db"] == 3.0
    assert summary["vocals"]["missing_reference_tracks"] == 2
    assert summary["other"]["withheld_silent_reference_tracks"] == 1
