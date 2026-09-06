"""Product-contract tests for experimental symbolic-detail MIDI measurements."""

from io import BytesIO
from uuid import uuid4

import mido
import pytest

from domain.api.workflows_jobs import _require_public_create_action
from symbolic_detail import build_symbolic_detail


def _symbolic_fixture() -> bytes:
    midi = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))

    for lead_pitch, bass_pitch in ((60, 48), (62, 47), (64, 45)):
        track.append(mido.Message("note_on", note=lead_pitch, velocity=80, time=0))
        track.append(mido.Message("note_on", note=bass_pitch, velocity=72, time=0))
        track.append(mido.Message("note_off", note=lead_pitch, velocity=0, time=480))
        track.append(mido.Message("note_off", note=bass_pitch, velocity=0, time=0))

    midi.tracks.append(track)
    handle = BytesIO()
    midi.save(file=handle)
    return handle.getvalue()


def test_symbolic_detail_keeps_exact_source_and_method_qualification() -> None:
    source_version_id = uuid4()
    report = build_symbolic_detail(
        _symbolic_fixture(),
        source_version_id=source_version_id,
        source_artifact_kind="midi_performance",
    )

    assert report.source_version_id == source_version_id
    assert report.source_artifact_kind == "midi_performance"
    assert report.experimental is True
    assert report.method.id == "partitura_performance_midi_v1"
    assert report.method.parameters["stream_source"] == (
        "partitura_load_performance_midi_track_channel"
    )
    assert report.register.low_midi == 45
    assert report.register.high_midi == 64
    assert report.register.low_name == "A2"
    assert report.register.high_name == "E4"
    assert report.register.span_semitones == 19
    assert report.contour.basis == "onset_pitch_centroid"
    assert report.contour.onset_count == 3
    assert report.interval_motion.interval_count > 0
    assert report.density.note_count == 6
    assert report.density.duration_quarters == 3.0
    assert report.texture.midi_stream_count == 1
    assert report.texture.peak_simultaneous_notes == 2
    assert report.voice_motion.status == "unavailable"
    assert "not canonical melody" in report.interpretation


def test_symbolic_detail_rejects_wrong_or_empty_source() -> None:
    with pytest.raises(ValueError, match="performance or corrected MIDI"):
        build_symbolic_detail(
            _symbolic_fixture(),
            source_version_id=uuid4(),
            source_artifact_kind="musicxml_score",
        )

    with pytest.raises(ValueError, match="non-empty MIDI"):
        build_symbolic_detail(
            b"",
            source_version_id=uuid4(),
            source_artifact_kind="midi_corrected",
        )


def test_symbolic_detail_is_a_public_opt_in_workflow_action() -> None:
    assert _require_public_create_action("symbolic_detail") == "symbolic_detail"
