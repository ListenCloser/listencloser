"""Truth-contract tests for synthesized melody audition."""

import io
from uuid import uuid4

import pretty_midi
import pytest

from domain.melody_audition_capability import _build_melody_midi, match_melody_note_entities
from domain.models import Entity, EntityKind, Insight, NoteEntity, Span


def _note(version_id, pitch: int, start: float, end: float, velocity: int = 80) -> Entity:
    return Entity(
        version_id=version_id,
        kind=EntityKind.note,
        span=Span(start_seconds=start, end_seconds=end),
        note=NoteEntity(
            pitch=pitch,
            start_seconds=start,
            end_seconds=end,
            velocity=velocity,
        ),
    )


def _insight(version_id, notes: list[dict]) -> Insight:
    return Insight(
        version_id=version_id,
        kind="melody",
        claim="Proposed melody",
        evidence={"notes": notes},
    )


def test_melody_audition_maps_every_tuple_to_one_exact_unused_entity() -> None:
    version_id = uuid4()
    c5 = _note(version_id, 72, 1.0, 1.5, 81)
    d5 = _note(version_id, 74, 1.5, 2.0, 83)
    accompaniment = _note(version_id, 48, 1.0, 2.0, 60)
    insight = _insight(
        version_id,
        [
            {"pitch": 72, "start_seconds": 1.0001, "end_seconds": 1.5001},
            {"pitch": 74, "start_seconds": 1.5001, "end_seconds": 2.0001},
        ],
    )

    matched = match_melody_note_entities(insight, [c5, accompaniment, d5])

    assert [entity.id for entity in matched] == [c5.id, d5.id]


def test_melody_audition_fails_closed_on_missing_or_ambiguous_identity() -> None:
    version_id = uuid4()
    source = _note(version_id, 72, 1.0, 1.5)
    insight = _insight(
        version_id,
        [{"pitch": 72, "start_seconds": 1.0, "end_seconds": 1.5}],
    )

    with pytest.raises(ValueError, match="cannot be mapped"):
        match_melody_note_entities(insight, [])

    duplicate = _note(version_id, 72, 1.002, 1.502)
    with pytest.raises(ValueError, match="ambiguously"):
        match_melody_note_entities(insight, [source, duplicate])


def test_melody_audition_midi_contains_only_proposed_notes_and_full_piece_extent() -> None:
    version_id = uuid4()
    c5 = _note(version_id, 72, 1.0, 1.5, 81)
    d5 = _note(version_id, 74, 3.0, 3.4, 83)

    midi_bytes = _build_melody_midi([c5, d5], piece_end_seconds=10.0)
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))

    assert len(midi.instruments) == 1
    assert [note.pitch for note in midi.instruments[0].notes] == [72, 74]
    assert [note.velocity for note in midi.instruments[0].notes] == [81, 83]
    assert midi.instruments[0].notes[0].start == pytest.approx(1.0, abs=0.002)
    assert midi.instruments[0].notes[1].end == pytest.approx(3.4, abs=0.002)
    assert midi.get_end_time() == pytest.approx(10.0, abs=0.01)
