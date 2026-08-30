"""Keep corrected-MIDI note entities identical to the persisted MIDI Version.

The legacy correction handler writes a complete MIDI file but only persists the
replacement notes as Entities. Until representation roles are separated (see
#613), register this adapter for the correction capability so entity-backed
Piano Roll / comparison consumers cannot observe a partial note world.
"""

from __future__ import annotations

import io
from uuid import UUID

import pretty_midi

import domain.capabilities as capabilities
from domain.models import Entity, EntityKind, Job, NoteEntity, Span
from domain.repositories import EntityRepo


def note_entities_from_midi_bytes(data: bytes, version_id: UUID) -> list[Entity]:
    """Materialize the complete note world encoded by one MIDI Version."""
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


def handle_correct_with_entity_sync(job: Job, client) -> list[str]:
    """Run correction, then replace partial note Entities from its stored MIDI."""
    output_ids = capabilities.handle_correct(job, client)
    if len(output_ids) != 1:
        raise ValueError("correct must produce exactly one MIDI version")

    output_version_id = UUID(output_ids[0])
    output_version = capabilities._lookup_version(client, output_version_id)
    owner_id = capabilities._resolve_owner_id(client, job.workflow_id)
    corrected_midi = capabilities.download_version_bytes(output_version, client)

    # Parse before deleting anything so corrupt/unreadable output leaves the
    # handler failed with its original records intact rather than an empty view.
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

    return output_ids


def register_corrected_midi_entity_sync(worker) -> None:
    """Override the legacy correction registration with the consistency adapter."""
    worker.register("correct", "1.0", handle_correct_with_entity_sync)
