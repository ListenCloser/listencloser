from __future__ import annotations

import io
from uuid import uuid4

import pretty_midi

import domain.capabilities as capabilities
from domain.models import Capability, Entity, Job, Version


def _midi_bytes() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)

    piano = pretty_midi.Instrument(program=0, name="Piano")
    piano.notes.extend(
        [
            pretty_midi.Note(velocity=80, pitch=60, start=0.2, end=0.6),
            pretty_midi.Note(velocity=75, pitch=62, start=1.1, end=1.4),
        ]
    )
    midi.instruments.append(piano)

    bass = pretty_midi.Instrument(program=32, name="Bass")
    bass.notes.append(pretty_midi.Note(velocity=70, pitch=48, start=2.1, end=2.5))
    midi.instruments.append(bass)

    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def _entity_note_world(entities: list[Entity]) -> list[tuple[int, float, float, int]]:
    notes: list[tuple[int, float, float, int]] = []
    for entity in entities:
        assert entity.note is not None
        notes.append(
            (
                entity.note.pitch,
                round(entity.note.start_seconds, 3),
                round(entity.note.end_seconds, 3),
                entity.note.velocity,
            )
        )
    return sorted(notes)


def _midi_note_world(data: bytes) -> list[tuple[int, float, float, int]]:
    midi = pretty_midi.PrettyMIDI(io.BytesIO(data))
    return sorted(
        (
            note.pitch,
            round(note.start, 3),
            round(note.end, 3),
            note.velocity,
        )
        for instrument in midi.instruments
        for note in instrument.notes
    )


def test_correct_persists_entities_for_the_full_output_midi(monkeypatch) -> None:
    input_version_id = uuid4()
    output_version_id = uuid4()
    artifact_id = uuid4()
    work_id = uuid4()
    workflow_id = uuid4()
    captured_entities: list[Entity] = []
    uploaded: dict[str, bytes] = {}

    input_version = Version(
        id=input_version_id,
        artifact_id=artifact_id,
        storage_key="source.mid",
        storage_bucket="artifacts",
    )
    source_bytes = _midi_bytes()

    job = Job(
        workflow_id=workflow_id,
        capability=Capability(name="correct", version="1.0"),
        input_version_ids=[input_version_id],
        parameters={
            "selection_start": 1.0,
            "selection_end": 1.5,
            "corrected_notes": [
                {"pitch": 72, "start": 1.1, "end": 1.45, "velocity": 90},
            ],
        },
    )

    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_: "owner")
    monkeypatch.setattr(capabilities, "_lookup_version", lambda *_: input_version)
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda *_: work_id)
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *_: source_bytes)
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_: None)
    monkeypatch.setattr(
        capabilities,
        "_create_output_version",
        lambda *_args, **_kwargs: output_version_id,
    )

    def capture_upload(_client, _bucket, key, data, _content_type):
        uploaded[key] = data

    monkeypatch.setattr(capabilities, "_upload_bytes", capture_upload)

    class CapturingEntityRepo:
        def __init__(self, _client):
            pass

        def create(self, entity: Entity, _owner_id: str) -> Entity:
            captured_entities.append(entity)
            return entity

        def create_many(self, entities: list[Entity], _owner_id: str) -> list[Entity]:
            captured_entities.extend(entities)
            return entities

    monkeypatch.setattr(capabilities, "EntityRepo", CapturingEntityRepo)

    assert capabilities.handle_correct(job, object()) == [str(output_version_id)]

    corrected_bytes = next(iter(uploaded.values()))
    entity_world = _entity_note_world(captured_entities)
    midi_world = _midi_note_world(corrected_bytes)

    # The entity-backed Piano Roll / comparison world must describe the exact
    # same corrected Version as the MIDI users can play. Retained notes from
    # outside the edit region (including other instruments) cannot disappear.
    assert entity_world == midi_world
    assert [note[0] for note in entity_world] == [48, 60, 72]
    assert all(entity.version_id == output_version_id for entity in captured_entities)
