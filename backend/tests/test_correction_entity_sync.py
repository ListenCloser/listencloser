from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import uuid4

import pretty_midi
import pytest

import domain.capabilities as capabilities
import domain.correction_entity_sync as correction_sync
from domain.models import ArtifactKind, Capability, Entity, Job, Version


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


def test_correction_sync_replaces_entities_and_publishes_exact_playback_output(
    monkeypatch,
) -> None:
    output_version_id = uuid4()
    playback_version_id = uuid4()
    source_version_id = uuid4()
    workflow_id = uuid4()
    artifact_id = uuid4()
    work_id = uuid4()
    captured_entities: list[Entity] = []
    captured_upload: dict = {}
    captured_playback: dict = {}

    output_version = Version(
        id=output_version_id,
        artifact_id=artifact_id,
        storage_key="corrected.mid",
        storage_bucket="artifacts",
        metadata={"existing": "preserved"},
    )
    job = Job(
        workflow_id=workflow_id,
        capability=Capability(name="correct", version="1.0"),
        input_version_ids=[source_version_id],
        parameters={
            "selection_start": 1.0,
            "selection_end": 1.5,
            "corrected_notes": [
                {"pitch": 73, "start": 1.1, "end": 1.45, "velocity": 90},
            ],
        },
    )

    monkeypatch.setattr(
        capabilities,
        "handle_correct",
        lambda *_: [str(output_version_id)],
    )
    monkeypatch.setattr(capabilities, "_lookup_version", lambda *_: output_version)
    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda *_: "owner")
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda *_: work_id)
    monkeypatch.setattr(capabilities, "download_version_bytes", lambda *_: _midi_bytes())
    monkeypatch.setattr(
        correction_sync.music_features,
        "midi_to_wav",
        lambda *_args, **_kwargs: b"RIFF-corrected",
    )
    monkeypatch.setattr(
        capabilities,
        "_job_storage_key",
        lambda _job, filename: f"jobs/correction/{filename}",
    )

    def capture_upload(_client, bucket, key, data, content_type="application/octet-stream"):
        captured_upload.update(
            bucket=bucket,
            key=key,
            data=data,
            content_type=content_type,
        )

    def capture_output_version(
        _client,
        actual_work_id,
        kind,
        storage_key,
        content,
        parent_version_id,
        actual_job,
        owner_id,
        **kwargs,
    ):
        captured_playback.update(
            work_id=actual_work_id,
            kind=kind,
            storage_key=storage_key,
            content=content,
            parent_version_id=parent_version_id,
            job=actual_job,
            owner_id=owner_id,
            kwargs=kwargs,
        )
        return playback_version_id

    monkeypatch.setattr(capabilities, "_upload_bytes", capture_upload)
    monkeypatch.setattr(capabilities, "_create_output_version", capture_output_version)

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

    entity_query = DeleteQuery()

    class Client:
        def table(self, name: str):
            # Published Versions are immutable at the fenced worker boundary.
            assert name == "entities"
            return entity_query

    result = correction_sync.handle_correct_with_entity_sync(job, Client())

    assert result == [str(output_version_id), str(playback_version_id)]
    assert output_version.metadata == {"existing": "preserved"}
    assert entity_query.deleted is True
    assert entity_query.executed is True
    assert entity_query.filters == [
        ("version_id", str(output_version_id)),
        ("kind", "note"),
    ]
    assert [note[0] for note in _note_world(captured_entities)] == [48, 60, 72]
    assert all(entity.version_id == output_version_id for entity in captured_entities)

    assert captured_upload == {
        "bucket": "artifacts",
        "key": "jobs/correction/corrected.wav",
        "data": b"RIFF-corrected",
        "content_type": "audio/wav",
    }
    assert captured_playback["work_id"] == work_id
    assert captured_playback["kind"] == ArtifactKind.audio_rendered
    assert captured_playback["storage_key"] == "jobs/correction/corrected.wav"
    assert captured_playback["content"] == b"RIFF-corrected"
    assert captured_playback["parent_version_id"] == output_version_id
    assert captured_playback["job"] == job
    assert captured_playback["owner_id"] == "owner"
    assert captured_playback["kwargs"] == {
        "mime_type": "audio/wav",
        "label": "Corrected transcription playback",
        "metadata": {
            "representation": "transcription_playback",
            "source_midi_version_id": str(output_version_id),
            "source_representation": "edited_performance",
        },
    }


def test_missing_synth_runtime_keeps_correction_without_playback(monkeypatch) -> None:
    corrected_version_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="correct", version="1.0"),
        input_version_ids=[uuid4()],
    )

    def fail_render(*_args, **_kwargs):
        raise RuntimeError("no synth runtime")

    monkeypatch.setattr(correction_sync.music_features, "midi_to_wav", fail_render)

    assert (
        correction_sync._publish_corrected_playback(
            job,
            object(),
            corrected_version_id=corrected_version_id,
            corrected_midi=_midi_bytes(),
            owner_id="owner",
        )
        is None
    )


def test_playback_persistence_failure_is_not_hidden_as_success(monkeypatch) -> None:
    corrected_version_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="correct", version="1.0"),
        input_version_ids=[uuid4()],
    )
    monkeypatch.setattr(
        correction_sync.music_features,
        "midi_to_wav",
        lambda *_args, **_kwargs: b"RIFF-corrected",
    )
    monkeypatch.setattr(capabilities, "_resolve_work_id", lambda *_: uuid4())
    monkeypatch.setattr(capabilities, "_job_storage_key", lambda *_: "jobs/corrected.wav")

    def fail_upload(*_args, **_kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(capabilities, "_upload_bytes", fail_upload)

    with pytest.raises(RuntimeError, match="storage unavailable"):
        correction_sync._publish_corrected_playback(
            job,
            object(),
            corrected_version_id=corrected_version_id,
            corrected_midi=_midi_bytes(),
            owner_id="owner",
        )
