"""Publish corrected MIDI as a complete, provenance-exact performance Version.

The legacy correction handler writes a complete MIDI file but only persists the
replacement notes as Entities. Register this adapter for the correction
capability so Piano Roll/comparison consumers see the complete persisted note
world and the resulting immutable Version is explicitly qualified as an edited
performance rather than an ambiguous ``midi_corrected`` artifact.
"""

from __future__ import annotations

import io
import logging
from uuid import UUID

import music_features
import domain.capabilities as capabilities
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


def _publish_corrected_playback(
    job: Job,
    client,
    *,
    corrected_version_id: UUID,
    corrected_midi: bytes,
    owner_id: str,
) -> UUID | None:
    """Best-effort synthesize playback bound to the exact corrected MIDI Version.

    MIDI correction remains the durable primary result. If the configured
    FluidSynth/SoundFont runtime is unavailable, preserve the corrected Version
    and fail closed by publishing no playback artifact rather than substituting
    audio from a different performance interpretation.
    """
    try:
        wav_bytes = music_features.midi_to_wav(corrected_midi)
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
    except Exception:
        logger.exception(
            "corrected_playback_render_failed",
            extra={"corrected_version_id": str(corrected_version_id)},
        )
        return None


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

    # Playback is an auxiliary derivative, not a second correction result. The
    # correction coordinator can therefore keep its exact one-output contract
    # while the Work bundle discovers this render by exact parent/provenance.
    _publish_corrected_playback(
        job,
        client,
        corrected_version_id=output_version_id,
        corrected_midi=corrected_midi,
        owner_id=owner_id,
    )

    return output_ids


def register_corrected_midi_entity_sync(worker) -> None:
    """Override correction registration with the consistency/provenance adapter."""
    worker.register("correct", "1.0", handle_correct_with_entity_sync)
