from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from backend.evaluation.analysis_v3.multitrack_transcription.adapters import (
    basic_pitch as basic_pitch_adapter,
)
from backend.evaluation.analysis_v3.separation.datasets import babyslakh
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


def test_bass_amt_comparison_reuses_basic_pitch_and_amt_metric(monkeypatch, tmp_path):
    reference_midi = tmp_path / "bass.mid"
    reference_midi.write_bytes(b"reference")
    run_calls: list[str] = []

    def fake_run_basic_pitch(audio_path, output_midi):
        run_calls.append(audio_path.name)
        output_midi.write_bytes(b"prediction")
        return {}

    monkeypatch.setattr(basic_pitch_adapter, "run_basic_pitch", fake_run_basic_pitch)
    monkeypatch.setattr(downstream, "_load_midi_events", lambda paths: [str(paths[0])])
    scores = iter([0.2, 0.7])
    fake_amt_metrics = SimpleNamespace(
        match_notes=lambda reference, predicted: SimpleNamespace(f1=next(scores))
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.evaluation.analysis_v3.multitrack_transcription.metrics",
        fake_amt_metrics,
    )

    audio = np.zeros(8000, dtype=np.float32)
    result = downstream.compare_bass_note_f1_mixture_vs_stem(
        audio,
        audio,
        8000,
        [reference_midi],
    )

    assert result is not None
    assert result.mixture_score == 0.2
    assert result.stem_score == 0.7
    assert result.delta == pytest.approx(0.5)
    assert run_calls == ["input.wav", "input.wav"]


def test_babyslakh_manifest_builds_four_stem_references(monkeypatch, tmp_path):
    track = tmp_path / "Track00001"
    (track / "stems").mkdir(parents=True)
    (track / "MIDI").mkdir()
    (track / "metadata.yaml").write_text("stub: true\n")

    sample_rate = 8000
    bass = np.full(80, 0.1, dtype=np.float32)
    drums = np.full(80, 0.2, dtype=np.float32)
    other = np.full(80, 0.3, dtype=np.float32)
    sf.write(track / "mix.wav", bass + drums + other, sample_rate)
    sf.write(track / "stems" / "S00.wav", bass, sample_rate)
    sf.write(track / "stems" / "S01.wav", drums, sample_rate)
    sf.write(track / "stems" / "S02.wav", other, sample_rate)
    (track / "MIDI" / "S00.mid").write_bytes(b"bass-midi")

    monkeypatch.setattr(
        babyslakh,
        "_load_metadata",
        lambda path: {
            "stems": {
                "S00": {"audio_rendered": True, "inst_class": "Bass", "is_drum": False},
                "S01": {"audio_rendered": True, "inst_class": "Drums", "is_drum": True},
                "S02": {"audio_rendered": True, "inst_class": "Piano", "is_drum": False},
            }
        },
    )
    monkeypatch.setattr(
        babyslakh,
        "_extract_reference_beats",
        lambda track_dir: [0.0, 0.5, 1.0],
    )

    manifest_path = tmp_path / "manifest.json"
    payload = babyslakh.build_babyslakh_manifest(
        tmp_path,
        output_manifest=manifest_path,
        limit=1,
    )

    assert payload["dataset_license"] == "CC BY 4.0"
    assert len(payload["clips"]) == 1
    clip = payload["clips"][0]
    assert clip["reference_source_counts"] == {"drums": 1, "bass": 1, "other": 1}
    assert clip["reference_beats"] == [0.0, 0.5, 1.0]
    assert clip["reference_beats_kind"] == "symbolic_synthesis_reference"
    assert "bass" in clip["reference_midis"]
    assert set(clip["reference_stems"]) == {"drums", "bass", "other"}
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text())["name"] == "babyslakh_4stem_reference_v1"
