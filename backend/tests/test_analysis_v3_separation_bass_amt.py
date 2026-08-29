from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from backend.evaluation.analysis_v3.multitrack_transcription.metrics import MatchMetrics
from backend.evaluation.analysis_v3.separation import bass_amt
from backend.evaluation.analysis_v3.separation.datasets import babyslakh_bass
from backend.evaluation.analysis_v3.separation.run_bass_amt import _summary


def _metrics(f1: float) -> MatchMetrics:
    return MatchMetrics(
        reference_notes=10,
        predicted_notes=10,
        matched_notes=int(round(f1 * 10)),
        precision=f1,
        recall=f1,
        f1=f1,
    )


def test_compare_mixture_vs_bass_stem_runs_same_basic_pitch_contract(monkeypatch, tmp_path):
    reference = tmp_path / "bass.mid"
    reference.write_bytes(b"reference")
    calls: list[tuple[tuple[int, ...], float]] = []
    scores = iter([(0.2, 0.1), (0.7, 0.4)])

    def fake_score(audio, sample_rate, reference_midi_paths, *, excerpt_seconds):
        calls.append((audio.shape, excerpt_seconds))
        onset, offset = next(scores)
        return bass_amt.BassAmtScore(
            onset=_metrics(onset),
            onset_offset=_metrics(offset),
            runtime_seconds=1.0,
            process_max_rss_mb=100.0,
            predicted_notes_reported=10,
            provenance={"engine": "basic_pitch"},
        )

    monkeypatch.setattr(bass_amt, "score_basic_pitch_audio", fake_score)

    comparison = bass_amt.compare_mixture_vs_bass_stem(
        np.zeros(100, dtype=np.float32),
        np.zeros((2, 100), dtype=np.float32),
        44100,
        [reference],
        excerpt_seconds=30.0,
    )

    assert comparison.onset_f1_delta == 0.5
    assert comparison.onset_offset_f1_delta == 0.3
    assert calls == [((100,), 30.0), ((2, 100), 30.0)]


def test_score_basic_pitch_audio_calls_production_adapter_and_existing_matcher(
    monkeypatch, tmp_path
):
    reference = tmp_path / "bass.mid"
    reference.write_bytes(b"reference")
    run_calls: list[str] = []
    match_calls: list[bool] = []

    def fake_run_basic_pitch(audio_path, prediction_path):
        run_calls.append(audio_path.name)
        prediction_path.write_bytes(b"prediction")
        return {
            "runtime_seconds": 1.25,
            "process_max_rss_mb": 321.0,
            "predicted_notes": 4,
            "provenance": {"engine": "basic_pitch", "library_version": "0.4.0"},
        }

    def fake_load(paths, *, end_seconds):
        return [
            SimpleNamespace(
                pitch=40,
                start=0.0,
                end=0.5,
                program=32,
                is_drum=False,
            )
        ]

    def fake_match(reference_events, predicted_events, *, require_offset=False, **kwargs):
        match_calls.append(require_offset)
        return _metrics(0.5 if not require_offset else 0.25)

    monkeypatch.setattr(bass_amt, "run_basic_pitch", fake_run_basic_pitch)
    monkeypatch.setattr(bass_amt, "_load_note_events", fake_load)
    monkeypatch.setattr(bass_amt, "match_notes", fake_match)

    score = bass_amt.score_basic_pitch_audio(
        np.zeros((2, 100), dtype=np.float32),
        44100,
        [reference],
        excerpt_seconds=30.0,
    )

    assert run_calls == ["input.wav"]
    assert match_calls == [False, True]
    assert score.onset.f1 == 0.5
    assert score.onset_offset.f1 == 0.25
    assert score.provenance["engine"] == "basic_pitch"


def test_mono_policy_handles_channel_first_and_channel_last():
    channel_first = np.stack([np.ones(10), np.zeros(10)], axis=0)
    channel_last = channel_first.T

    assert np.allclose(bass_amt._mono_audio(channel_first), 0.5)
    assert np.allclose(bass_amt._mono_audio(channel_last), 0.5)


def test_bass_reference_selection_uses_metadata_and_source_midi(monkeypatch, tmp_path):
    track = tmp_path / "Track00001"
    (track / "MIDI").mkdir(parents=True)
    (track / "metadata.yaml").write_text("stub: true\n")
    (track / "MIDI" / "S00.mid").write_bytes(b"bass")
    (track / "MIDI" / "S01.mid").write_bytes(b"piano")

    monkeypatch.setattr(
        babyslakh_bass,
        "_load_metadata",
        lambda path: {
            "stems": {
                "S00": {"inst_class": "Bass", "is_drum": False, "midi_saved": True},
                "S01": {"inst_class": "Piano", "is_drum": False, "midi_saved": True},
            }
        },
    )

    assert babyslakh_bass.bass_reference_midis(track) == [track / "MIDI" / "S00.mid"]


def test_safe_path_filter_excludes_audio_stems_and_other_tracks():
    assert (
        babyslakh_bass._safe_selected_relative_path(
            "babyslakh_16k/Track00001/MIDI/S00.mid", "Track00001"
        ).as_posix()
        == "MIDI/S00.mid"
    )
    assert (
        babyslakh_bass._safe_selected_relative_path(
            "babyslakh_16k/Track00001/stems/S00.wav", "Track00001"
        )
        is None
    )
    assert (
        babyslakh_bass._safe_selected_relative_path(
            "babyslakh_16k/Track00002/MIDI/S00.mid", "Track00001"
        )
        is None
    )


def test_summary_separates_missing_reference_from_scored_rows():
    rows = [
        {"id": "a", "state": "missing_bass_reference"},
        {"id": "b", "state": "no_bass_notes_in_excerpt"},
        {
            "id": "c",
            "state": "scored",
            "comparison": {"onset_f1_delta": 0.3, "onset_offset_f1_delta": -0.1},
        },
        {
            "id": "d",
            "state": "scored",
            "comparison": {"onset_f1_delta": 0.1, "onset_offset_f1_delta": 0.2},
        },
    ]

    summary = _summary(rows)

    assert summary["scored_tracks"] == 2
    assert summary["missing_bass_reference_tracks"] == 1
    assert summary["no_bass_notes_in_excerpt_tracks"] == 1
    assert summary["mean_onset_f1_delta"] == 0.2
    assert summary["onset_improved_tracks"] == 2
