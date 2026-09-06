"""Publish corrected MIDI with a complete, provenance-exact note world.

The legacy correction handler writes a complete MIDI file but only persists the
replacement notes as Entities. Register this adapter for the correction
capability so Piano Roll/comparison consumers see the complete persisted note
world. The immutable Version's semantic role remains proven by its producing
``correct`` Job and exact input Version; this adapter never mutates a published
Version row after creation.
"""

from __future__ import annotations

import io
import logging
from uuid import UUID

import domain.capabilities as capabilities
import music_features
from domain.models import ArtifactKind, Entity, EntityKind, Job, NoteEntity, Span
from domain.repositories import EntityRepo

logger = logging.getLogger("correction_entity_sync")


def note_entities_from_midi_bytes(data: bytes, version_id: UUID) -> list[Entity]:
    """Materialize the complete note world encoded by one MIDI Version."""
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(io.BytesIO(data))
    entities: list[Entity] = []
    for instrument in midi.instruments:
        for note in instrument.notes:
            entities.append(
                Entity(
                    version_id=version_id,
                    kind=EntityKind.note,
                    span=Span(start_seconds=note.start, end_seconds=note.end),
                    note=NoteEntity(
                        pitch=note.pitch,
                        start_seconds=note.start,
                        end_seconds=note.end,
                        velocity=note.velocity,
                    ),
                )
            )
    return entities


def _publish_corrected_playback(
    job: Job,
    client,
    *,
    corrected_version_id: UUID,
    corrected_midi: bytes,
    owner_id: str,
) -> UUID | None:
    """Synthesize playback bound to the exact corrected MIDI Version.

    A missing synth runtime is an honest optional-capability abstention: preserve
    the corrected MIDI and publish no playback. Once synthesis succeeds,
    persistence errors propagate through the normal fenced Job failure path
    rather than being hidden as a successful partial publication.
    """
    try:
        wav_bytes = music_features.midi_to_wav(corrected_midi)
    except Exception:
        logger.exception(
            "corrected_playback_render_unavailable",
            extra={"corrected_version_id": str(corrected_version_id)},
        )
        return None

    work_id = capabilities._resolve_work_id(client, corrected_version_id)
    storage_key = capabilities._job_storage_key(job, "corrected.wav")
    capabilities._upload_bytes(
        client,
        capabilities._STORAGE_BUCKET,
        storage_key,
        wav_bytes,
        "audio/wav",
    )
    return capabilities._create_output_version(
        client,
        work_id,
        ArtifactKind.audio_rendered,
        storage_key,
        wav_bytes,
        corrected_version_id,
        job,
        owner_id,
        mime_type="audio/wav",
        label="Corrected transcription playback",
        metadata={
            "representation": "transcription_playback",
            "source_midi_version_id": str(corrected_version_id),
            "source_representation": "edited_performance",
        },
    )


def handle_correct_with_entity_sync(job: Job, client) -> list[str]:
    """Run correction, republish complete notes, and optionally render playback."""
    output_ids = capabilities.handle_correct(job, client)
    if len(output_ids) != 1:
        raise ValueError("correct must produce exactly one corrected MIDI before playback")

    output_version_id = UUID(output_ids[0])
    output_version = capabilities._lookup_version(client, output_version_id)
    owner_id = capabilities._resolve_owner_id(client, job.workflow_id)
    corrected_midi = capabilities.download_version_bytes(output_version, client)

    # Parse before replacing Entities so corrupt/unreadable output leaves the
    # handler failed rather than advertising a partial corrected note world.
    full_note_world = note_entities_from_midi_bytes(corrected_midi, output_version_id)

    (
        client.table("entities")
        .delete()
        .eq("version_id", str(output_version_id))
        .eq("kind", EntityKind.note.value)
        .execute()
    )
    if full_note_world:
        EntityRepo(client).create_many(full_note_world, owner_id)

    playback_version_id = _publish_corrected_playback(
        job,
        client,
        corrected_version_id=output_version_id,
        corrected_midi=corrected_midi,
        owner_id=owner_id,
    )
    if playback_version_id is not None:
        output_ids.append(str(playback_version_id))

    return output_ids


def register_corrected_midi_entity_sync(worker) -> None:
    """Override correction registration with complete-entity/playback publication."""
    worker.register("correct", "1.0", handle_correct_with_entity_sync)
