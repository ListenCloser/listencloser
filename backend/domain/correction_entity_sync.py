"""Publish corrected MIDI as a complete, provenance-exact performance Version.

The legacy correction handler writes a complete MIDI file but only persists the
replacement notes as Entities. Register this adapter for the correction
capability so Piano Roll/comparison consumers see the complete persisted note
world and the resulting immutable Version is explicitly qualified as an edited
performance rather than an ambiguous ``midi_corrected`` artifact.
"""

from __future__ import annotations

import io
from uuid import UUID

import domain.capabilities as capabilities
from domain.models import Entity, EntityKind, Job, NoteEntity, Span
from domain.repositories import EntityRepo


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


def _edited_performance_metadata(job: Job, existing: dict) -> dict:
    """Describe only correction facts that are directly proven by the durable Job."""
    corrected_notes = job.parameters.get("corrected_notes") or []
    return {
        **existing,
        "representation": "edited_performance",
        "correction": {
            "schema_version": 1,
            "operation": "replace_notes_in_span",
            "source_version_id": str(job.input_version_ids[0]),
            "selection_start_seconds": job.parameters.get("selection_start"),
            "selection_end_seconds": job.parameters.get("selection_end"),
            "replacement_note_count": len(corrected_notes),
        },
    }


def handle_correct_with_entity_sync(job: Job, client) -> list[str]:
    """Run correction, qualify its Version, then publish its complete note world."""
    output_ids = capabilities.handle_correct(job, client)
    if len(output_ids) != 1:
        raise ValueError("correct must produce exactly one MIDI version")

    output_version_id = UUID(output_ids[0])
    output_version = capabilities._lookup_version(client, output_version_id)
    owner_id = capabilities._resolve_owner_id(client, job.workflow_id)
    corrected_midi = capabilities.download_version_bytes(output_version, client)

    # Parse before publishing follow-on state so corrupt/unreadable output leaves
    # the handler failed rather than advertising a complete corrected note world.
    full_note_world = note_entities_from_midi_bytes(corrected_midi, output_version_id)

    metadata = _edited_performance_metadata(job, dict(output_version.metadata))
    (
        client.table("artifact_versions")
        .update({"metadata": metadata})
        .eq("id", str(output_version_id))
        .execute()
    )

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
    """Override correction registration with the consistency/provenance adapter."""
    worker.register("correct", "1.0", handle_correct_with_entity_sync)
