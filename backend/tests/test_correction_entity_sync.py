from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4

import pretty_midi

import domain.capabilities as capabilities
import domain.correction_entity_sync as correction_sync
from domain.models import Capability, Entity, Job, Version


def _midi_bytes() -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)

    piano = pretty_midi.Instrument(program=0, name="Piano")
    piano.notes.extend(
        [
            pretty_midi.Note(velocity=80, pitch=60, start=0.2, end=0.6),
            pretty_midi.Note(velocity=90, pitch=72, start=1.1, end=1.45),
        ]
    )
    midi.instruments.append(piano)

    bass = pretty_midi.Instrument(program=32, name="Bass")
    bass.notes.append(pretty_midi.Note(velocity=70, pitch=48, start=2.1, end=2.5))
    midi.instruments.append(bass)

    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def _note_world(entities: list[Entity]) -> list[tuple[int, float, float, int]]:
    world: list[tuple[int, float, float, int]] = []
    for entity in entities:
        assert entity.note is not None
        world.append(
            (
                entity.note.pitch,
                round(entity.note.start_seconds, 3),
                round(entity.note.end_seconds, 3),
                entity.note.velocity,
            )
        )
    return sorted(world)


def test_note_entities_from_midi_bytes_materializes_every_instrument() -> None:
    version_id = uuid4()

    entities = correction_sync.note_entities_from_midi_bytes(_midi_bytes(), version_id)

    assert [note[0] for note in _note_world(entities)] == [48, 60, 72]
    assert all(entity.version_id == version_id for entity in entities)


def test_correction_sync_replaces_partial_entities_from_persisted_midi(monkeypatch) -> None:
    output_version_id = uuid4()
    workflow_id = uuid4()
    artifact_id = uuid4()
    captured_entities: list[Entity] = []

    output_version = Version(
        id=output_version_id,
        artifact_id=artifact_id,
        storage_key="corrected.mid",
        storage_bucket="artifacts",
    )
    job = Job(
        workflow_id=workflow_id,
        capability=Capability(name="correct", version="1.0"),
    )

    monkeypatch.setattr(
        capabilities,
        "handle_correct",
        lambda *_: [str(output_version_id)],
    )
    monkeypatch.setattr(capabilities, "_lookup_version", lambda *_: output_version)
    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_: "owner")
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *_: _midi_bytes())

    class CapturingEntityRepo:
        def __init__(self, _client):
            pass

        def create_many(self, entities: list[Entity], _owner_id: str) -> list[Entity]:
            captured_entities.extend(entities)
            return entities

    monkeypatch.setattr(correction_sync, "EntityRepo", CapturingEntityRepo)

    class DeleteQuery:
        def __init__(self):
            self.filters: list[tuple[str, str]] = []
            self.deleted = False
            self.executed = False

        def delete(self):
            self.deleted = True
            return self

        def eq(self, column: str, value: str):
            self.filters.append((column, value))
            return self

        def execute(self):
            self.executed = True
            return SimpleNamespace(data=[])

    query = DeleteQuery()

    class Client:
        def table(self, name: str):
            assert name == "entities"
            return query

    result = correction_sync.handle_correct_with_entity_sync(job, Client())

    assert result == [str(output_version_id)]
    assert query.deleted is True
    assert query.executed is True
    assert query.filters == [
        ("version_id", str(output_version_id)),
        ("kind", "note"),
    ]
    assert [note[0] for note in _note_world(captured_entities)] == [48, 60, 72]
    assert all(entity.version_id == output_version_id for entity in captured_entities)
