"""Keep corrected-MIDI evidence complete and publish its performance authority.

The legacy correction handler writes a complete MIDI file but only persists the
replacement notes as Entities and classifies the result as generic
``midi_corrected``. Until representation roles are first-class schema columns
(see #613), this adapter completes the note world, renders playback from the
corrected MIDI, and only then publishes the result as the edited performance
interpretation. Exact-Version consumers therefore never mistake notation MIDI
or a partially completed correction for current performance evidence.
"""

from __future__ import annotations

import io
from uuid import UUID

import domain.capabilities as capabilities
from domain.models import ArtifactKind, Capability, Entity, EntityKind, Job, NoteEntity, Span
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


def _publish_edited_performance(job: Job, output_version, client) -> None:
    """Classify the correction only after all required outputs are durable."""
    source_version_id = job.input_version_ids[0]
    metadata = dict(output_version.metadata or {})
    metadata.update(
        {
            "representation_role": "edited_performance",
            "source_performance_version_id": str(source_version_id),
            "correction_workflow_id": str(job.workflow_id),
            "correction_job_id": str(job.id),
            "correction": {
                "selection_start": job.parameters.get("selection_start"),
                "selection_end": job.parameters.get("selection_end"),
                # This is the exact replacement payload used to create the MIDI.
                # A semantic add/remove/pitch delta can be reconstructed against
                # source_performance_version_id without guessing.
                "replacement_notes": job.parameters.get("corrected_notes", []),
            },
        }
    )

    # These rows were created inside this same worker attempt. Reclassification
    # happens before the worker marks the job succeeded, so clients never need
    # to mutate an already-published performance interpretation.
    (
        client.table("artifacts")
        .update({"kind": ArtifactKind.midi_performance.value})
        .eq("id", str(output_version.artifact_id))
        .execute()
    )
    (
        client.table("artifact_versions")
        .update({"label": "Corrected transcription", "metadata": metadata})
        .eq("id", str(output_version.id))
        .execute()
    )


def handle_correct_with_entity_sync(job: Job, client) -> list[str]:
    """Run correction, complete Entities/playback, then publish edited truth."""
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

    # Playback is an exact child of the corrected MIDI. Do this before
    # reclassifying the MIDI as current edited-performance truth; a synthesis
    # failure therefore fails closed and cannot surface a half-complete source.
    synthesis_job = job.model_copy(
        update={
            "capability": Capability(name="synthesize", version="1.0"),
            "input_version_ids": [output_version_id],
            "parameters": {
                "label": "Corrected transcription playback",
                "sample_rate": int(job.parameters.get("sample_rate", 22050)),
            },
        }
    )
    audio_ids = capabilities.handle_synthesize(synthesis_job, client)

    _publish_edited_performance(job, output_version, client)
    return [*output_ids, *audio_ids]


def register_corrected_midi_entity_sync(worker) -> None:
    """Override the legacy correction registration with the consistency adapter."""
    worker.register("correct", "1.0", handle_correct_with_entity_sync)
