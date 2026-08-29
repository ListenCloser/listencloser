"""Regression tests for stage-attributed audio -> score evaluation."""

from __future__ import annotations

import io
from pathlib import Path

import pretty_midi

import evaluation.notation_eval as notation_eval
from evaluation.models import EvalClip


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


def _clip(tmp_path: Path, reference_midi: bytes) -> EvalClip:
    audio_path = tmp_path / "source.wav"
    midi_path = tmp_path / "reference.mid"
    xml_path = tmp_path / "reference.musicxml"
    audio_path.write_bytes(b"fake-audio")
    midi_path.write_bytes(reference_midi)
    xml_path.write_bytes(MUSICXML)
    return EvalClip(
        id="fixture",
        source_id="fixture-source",
        audio=str(audio_path),
        category="solo_piano",
        reference_midi=str(midi_path),
        reference_musicxml=str(xml_path),
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
