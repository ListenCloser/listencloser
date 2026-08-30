"""Regression tests for stage-attributed audio -> score evaluation."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pretty_midi
import pytest
from backend.evaluation import models, notation_eval


MUSICXML = b"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice>
      </note>
    </measure>
  </part>
</score-partwise>
"""


def _midi_bytes(*, pitch: int = 60) -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes.append(
        pretty_midi.Note(velocity=90, pitch=pitch, start=0.0, end=1.0)
    )
    midi.instruments.append(instrument)
    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def _clip(
    tmp_path: Path,
    reference_midi: bytes,
    *,
    with_musicxml: bool = True,
) -> models.EvalClip:
    audio_path = tmp_path / "source.wav"
    midi_path = tmp_path / "reference.mid"
    xml_path = tmp_path / "reference.musicxml"
    audio_path.write_bytes(b"fake-audio")
    midi_path.write_bytes(reference_midi)
    if with_musicxml:
        xml_path.write_bytes(MUSICXML)
    return models.EvalClip(
        id="fixture",
        source_id="fixture-source",
        audio=str(audio_path),
        category="solo_piano",
        reference_midi=str(midi_path),
        reference_musicxml=str(xml_path) if with_musicxml else None,
    )


def _metric_grid(*, bpm: float = 120.0) -> dict:
    return {
        "bpm": bpm,
        "beats": [0.0, 0.5, 1.0],
        "downbeats": [0.0, 1.0],
        "provenance": {"engine": "librosa"},
    }


def test_score_transcription_reuses_canonical_analysis_v3_matcher():
    reference = _midi_bytes(pitch=60)
    identical = notation_eval._score_transcription(reference, reference)
    wrong_pitch = notation_eval._score_transcription(reference, _midi_bytes(pitch=72))

    assert identical["onset_flat"]["f1"] == 1.0
    assert identical["note_flat"]["f1"] == 1.0
    assert wrong_pitch["onset_flat"]["f1"] == 0.0


def test_reference_mode_never_invokes_transcription(tmp_path, monkeypatch):
    reference_midi = _midi_bytes()
    clip = _clip(tmp_path, reference_midi)
    notation_inputs: list[bytes] = []
    notation_downbeats: list[list[float] | None] = []

    monkeypatch.setattr(notation_eval, "_production_metric_grid", lambda _path: _metric_grid())

    def fail_if_transcribed(_audio_path, _output_path):
        raise AssertionError("reference MIDI ceiling must not invoke transcription")

    monkeypatch.setattr(notation_eval, "_run_product_transcription", fail_if_transcribed)

    def fake_notation(midi_bytes, _beat_times, *, downbeats):
        notation_inputs.append(midi_bytes)
        notation_downbeats.append(downbeats)
        return MUSICXML, {"profile": "test"}

    monkeypatch.setattr(notation_eval, "_notation_from_midi", fake_notation)

    result = notation_eval.evaluate_clip(clip, "reference_midi_to_score")

    assert notation_inputs == [reference_midi]
    assert notation_downbeats == [[0.0, 1.0]]
    assert result["accuracy"] is None
    assert result["stages"]["transcription"]["status"] == "not_run"
    assert result["stages"]["metric_grid"]["source"] == "production_score_beat_engine"
    assert result["stages"]["metric_grid"]["downbeat_count"] == 2
    assert result["stages"]["notation"]["adaptive"] is True
    assert result["stages"]["notation"]["piano_grand_staff"] is True


def test_reference_mode_does_not_require_reference_musicxml(tmp_path, monkeypatch):
    reference_midi = _midi_bytes()
    clip = _clip(tmp_path, reference_midi, with_musicxml=False)

    monkeypatch.setattr(notation_eval, "_production_metric_grid", lambda _path: _metric_grid())
    monkeypatch.setattr(
        notation_eval,
        "_notation_from_midi",
        lambda _midi, _beats, *, downbeats: (MUSICXML, {"profile": "test"}),
    )

    result = notation_eval.evaluate_clip(clip, "reference_midi_to_score")

    assert result["structural"]["total_note_count"] == 1
    assert "reference_structural" not in result
    assert "note_count_ratio" not in result
    assert result["stages"]["notation"]["reference_structural"] is None


def test_product_mode_transcribes_audio_then_scores_and_notates_prediction(
    tmp_path,
    monkeypatch,
):
    reference_midi = _midi_bytes(pitch=60)
    predicted_midi = _midi_bytes(pitch=60)
    clip = _clip(tmp_path, reference_midi)
    notation_inputs: list[bytes] = []
    transcribed_audio_paths: list[Path] = []

    monkeypatch.setattr(
        notation_eval,
        "_production_metric_grid",
        lambda _path: _metric_grid(bpm=118.0),
    )

    def fake_transcription(audio_path: Path, output_path: Path):
        transcribed_audio_paths.append(audio_path)
        output_path.write_bytes(predicted_midi)
        return {
            "runtime_seconds": 1.25,
            "process_max_rss_mb": 256.0,
            "predicted_notes": 1,
            "provenance": {"engine": "basic_pitch"},
        }

    monkeypatch.setattr(notation_eval, "_run_product_transcription", fake_transcription)

    def fake_notation(midi_bytes, _beat_times, *, downbeats):
        assert downbeats == [0.0, 1.0]
        notation_inputs.append(midi_bytes)
        return MUSICXML, {"profile": "test"}

    monkeypatch.setattr(notation_eval, "_notation_from_midi", fake_notation)

    result = notation_eval.evaluate_clip(clip, "audio_to_predicted_midi_to_score")

    assert transcribed_audio_paths == [Path(clip.audio)]
    assert notation_inputs == [predicted_midi]
    assert result["accuracy"]["onset_flat"]["f1"] == 1.0
    assert result["accuracy"]["note_flat"]["f1"] == 1.0
    assert result["stages"]["transcription"]["provenance"]["engine"] == "basic_pitch"
    assert result["stages"]["metric_grid"]["tempo_bpm"] == 118.0
    assert result["stages"]["metric_grid"]["provenance"] == {"engine": "librosa"}
    assert result["stages"]["notation"]["quantization"] == {"profile": "test"}


def test_both_mode_keeps_ceiling_and_product_paths_separate():
    assert notation_eval._modes_for_run("both") == (
        "reference_midi_to_score",
        "audio_to_predicted_midi_to_score",
    )


def test_materialized_manifest_emits_rows_without_reference_musicxml(
    tmp_path,
    monkeypatch,
):
    audio_path = tmp_path / "prepared.wav"
    midi_path = tmp_path / "prepared.mid"
    audio_path.write_bytes(b"audio")
    midi_path.write_bytes(_midi_bytes())
    materialized_manifest = tmp_path / "manifest-real_world_v1.json"
    materialized_manifest.write_text(
        json.dumps(
            {
                "name": "real_world_v1_materialized",
                "clips": [
                    {
                        "id": "asap_fixture",
                        "dataset": "asap",
                        "source_id": "Bach/Prelude/test.mid",
                        "category": "solo_piano",
                        "audio": str(audio_path),
                        "reference_midi": str(midi_path),
                    }
                ],
            }
        )
    )

    observed: list[models.EvalClip] = []

    def fake_evaluate_clip(clip, mode):
        observed.append(clip)
        return {
            "clip_id": clip.id,
            "source_id": clip.source_id,
            "mode": mode,
            "accuracy": None,
            "structural": {
                "total_note_count": 1,
                "measure_count": 1,
                "tie_count": 0,
            },
        }

    monkeypatch.setattr(notation_eval, "evaluate_clip", fake_evaluate_clip)

    result = notation_eval.run_notation_evaluation(
        str(materialized_manifest),
        str(tmp_path / "results"),
        mode="reference_midi_to_score",
    )

    assert len(result["clips"]) == 1
    assert len(observed) == 1
    assert observed[0].audio == str(audio_path)
    assert observed[0].reference_midi == str(midi_path)
    assert observed[0].reference_musicxml is None
    assert observed[0].source_id == "Bach/Prelude/test.mid"


def test_source_manifest_fails_with_materialized_manifest_instruction(
    tmp_path,
    monkeypatch,
):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("MUSIC_EVAL_CACHE_DIR", str(cache_dir))
    source_manifest = tmp_path / "real_world_v1.json"
    source_manifest.write_text(
        json.dumps(
            {
                "name": "real_world_v1",
                "clips": [
                    {
                        "id": "asap_fixture",
                        "dataset": "asap",
                        "source_id": "Bach/Prelude/test.mid",
                        "category": "solo_piano",
                    }
                ],
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="evaluator-ready materialized manifest",
    ) as exc_info:
        notation_eval.run_notation_evaluation(
            str(source_manifest),
            str(tmp_path / "results"),
        )

    assert "evaluation.datasets.prepare" in str(exc_info.value)
    assert "manifest-real_world_v1.json" in str(exc_info.value)


def test_materialized_manifest_without_reference_midi_fails_closed(tmp_path):
    audio_path = tmp_path / "prepared.wav"
    audio_path.write_bytes(b"audio")
    materialized_manifest = tmp_path / "manifest-custom.json"
    materialized_manifest.write_text(
        json.dumps(
            {
                "name": "custom_materialized",
                "clips": [
                    {
                        "id": "fixture",
                        "source_id": "fixture-source",
                        "category": "solo_piano",
                        "audio": str(audio_path),
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError, match="no clips with reference MIDI"):
        notation_eval.run_notation_evaluation(
            str(materialized_manifest),
            str(tmp_path / "results"),
        )
