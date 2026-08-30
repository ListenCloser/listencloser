from __future__ import annotations

import io
import subprocess

import pretty_midi
import pytest

from evaluation import pm2s_notation_bakeoff as bakeoff


def _midi_bytes() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes.extend(
        [
            pretty_midi.Note(velocity=80, pitch=60, start=1.0, end=1.5),
            pretty_midi.Note(velocity=84, pitch=64, start=1.0, end=2.0),
            pretty_midi.Note(velocity=88, pitch=67, start=2.0, end=2.5),
        ]
    )
    midi.instruments.append(instrument)
    output = io.BytesIO()
    midi.write(output)
    return output.getvalue()


def test_build_pm2s_command_keeps_candidate_out_of_product_process():
    command = bakeoff.build_pm2s_command(
        "/candidate/bin/python",
        "/candidate/PM2S",
        "/tmp/in.mid",
        "/tmp/out.mid",
    )

    assert command[0] == "/candidate/bin/python"
    assert command[1] == "-c"
    assert command[-3:] == ["/candidate/PM2S", "/tmp/in.mid", "/tmp/out.mid"]
    assert "CRNNJointPM2S" in command[2]


def test_validate_pm2s_checkout_fails_closed_on_wrong_sha(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="deadbeef\n",
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError, match="PM2S checkout must be"):
        bakeoff.validate_pm2s_checkout("/candidate/PM2S")


def test_slice_performance_midi_rebases_and_clips_notes():
    sliced = bakeoff.slice_performance_midi(_midi_bytes(), 1.25, 2.25)
    midi = pretty_midi.PrettyMIDI(io.BytesIO(sliced))
    notes = sorted(
        [note for instrument in midi.instruments for note in instrument.notes],
        key=lambda note: (note.start, note.pitch),
    )

    assert len(notes) == 3
    assert notes[0].start == pytest.approx(0.0, abs=1e-3)
    assert notes[0].end == pytest.approx(0.25, abs=1e-3)
    assert max(note.end for note in notes) <= 1.0 + 1e-3


def test_midi_diagnostics_reports_overlaps_and_duration_vocabulary():
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes.extend(
        [
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=1.0),
            pretty_midi.Note(velocity=80, pitch=60, start=0.5, end=1.5),
            pretty_midi.Note(velocity=80, pitch=64, start=0.5, end=0.75),
        ]
    )
    midi.instruments.append(instrument)
    output = io.BytesIO()
    midi.write(output)

    diagnostics = bakeoff.diagnose_midi(output.getvalue())

    assert diagnostics["note_count"] == 3
    assert diagnostics["same_pitch_overlap_count"] == 1
    assert diagnostics["max_polyphony"] == 3
    assert diagnostics["distinct_duration_count_1ms"] == 2


def test_evaluate_pair_records_candidate_unavailable_without_fabricating_result(monkeypatch):
    monkeypatch.setattr(
        bakeoff,
        "_current_score",
        lambda midi: {
            "status": "measured",
            "notation_midi_sha256": "current",
        },
    )

    def fail_candidate(*args, **kwargs):
        raise RuntimeError("checkpoint unavailable")

    monkeypatch.setattr(bakeoff, "_pm2s_score", fail_candidate)
    monkeypatch.setattr(bakeoff, "_checkpoint_provenance", lambda repo: [])

    result = bakeoff.evaluate_pair(
        _midi_bytes(),
        clip_id="fixture",
        pm2s_python="/candidate/bin/python",
        pm2s_repo="/candidate/PM2S",
        product_baseline_sha="abc123",
    )

    assert result["input"]["transcription_in_scope"] is False
    assert result["current"]["status"] == "measured"
    assert result["pm2s"]["status"] == "unavailable"
    assert "checkpoint unavailable" in result["pm2s"]["error"]
    assert result["provenance"]["pm2s_checkpoint_rights"].startswith("unverified")
