"""Worker capability for auditioning the experimental melody proposal.

The capability does not infer a second melody and does not isolate the source
recording. It resolves the persisted melody Insight back to exact note entities
on the same immutable MIDI Version, renders only those notes with the canonical
FluidSynth path, and persists the result as derived audio.
"""

from __future__ import annotations

import hashlib
import io
import math
from uuid import UUID

import pretty_midi

import music_features
from domain.models import Artifact, ArtifactKind, Entity, EntityKind, Insight, Job, Version
from domain.repositories import ArtifactRepo, EntityRepo, InsightRepo, VersionRepo

_STORAGE_BUCKET = "artifacts"
_MATCH_EPSILON_SECONDS = 0.005
_ALLOWED_INPUT_KINDS = {ArtifactKind.midi_performance, ArtifactKind.midi_corrected}


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("melody_audition requires a job owner")
    return job.created_by


def _update_progress(client, job_id: UUID, progress: float, message: str) -> None:
    result = (
        client.table("jobs")
        .update({"progress": max(0.0, min(1.0, float(progress))), "status_message": message})
        .eq("id", str(job_id))
        .eq("stage", "running")
        .execute()
    )
    if result.data == []:
        raise RuntimeError("job is no longer running")


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _candidate_notes(insight: Insight) -> list[tuple[int, float, float]]:
    raw_notes = insight.evidence.get("notes")
    if not isinstance(raw_notes, list) or not raw_notes:
        raise ValueError("melody insight has no proposed note objects")

    candidates: list[tuple[int, float, float]] = []
    for raw in raw_notes:
        if not isinstance(raw, dict):
            raise ValueError("melody note evidence is malformed")
        pitch_value = raw.get("pitch")
        start = _finite_number(raw.get("start_seconds"))
        end = _finite_number(raw.get("end_seconds"))
        if (
            isinstance(pitch_value, bool)
            or not isinstance(pitch_value, int)
            or pitch_value < 0
            or pitch_value > 127
            or start is None
            or end is None
            or start < 0
            or end <= start
        ):
            raise ValueError("melody note evidence is malformed")
        candidates.append((pitch_value, start, end))
    return candidates


def match_melody_note_entities(insight: Insight, entities: list[Entity]) -> list[Entity]:
    """Resolve every proposed tuple to exactly one unused persisted note entity."""
    if insight.kind != "melody":
        raise ValueError("melody_audition requires melody evidence")

    source_notes = [
        entity for entity in entities if entity.kind == EntityKind.note and entity.note is not None
    ]
    used_ids: set[UUID] = set()
    matched: list[Entity] = []

    for pitch, start, end in _candidate_notes(insight):
        matches = [
            entity
            for entity in source_notes
            if entity.id not in used_ids
            and entity.note is not None
            and entity.note.pitch == pitch
            and abs(entity.note.start_seconds - start) <= _MATCH_EPSILON_SECONDS
            and abs(entity.note.end_seconds - end) <= _MATCH_EPSILON_SECONDS
        ]
        if len(matches) != 1:
            if not matches:
                raise ValueError(
                    "a proposed melody note cannot be mapped to an exact source note entity"
                )
            raise ValueError(
                "a proposed melody note maps ambiguously to multiple source note entities"
            )
        source = matches[0]
        used_ids.add(source.id)
        matched.append(source)

    return matched


def _build_melody_midi(matched: list[Entity], piece_end_seconds: float) -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    instrument = pretty_midi.Instrument(program=0, is_drum=False, name="Melody proposal")
    for entity in matched:
        note = entity.note
        if note is None:  # Defensive; matching already filters these.
            continue
        instrument.notes.append(
            pretty_midi.Note(
                velocity=max(1, min(127, int(note.velocity))),
                pitch=int(note.pitch),
                start=float(note.start_seconds),
                end=float(note.end_seconds),
            )
        )
    midi.instruments.append(instrument)

    # Keep the derived source on the same performance-time extent as the Piano
    # Roll even when the proposed melody ends early. A non-audible lyric event
    # extends the MIDI timeline without inventing a musical note or meter event.
    last_note_end = max((note.note.end_seconds for note in matched if note.note), default=0.0)
    if piece_end_seconds > last_note_end:
        midi.lyrics.append(pretty_midi.Lyric(text=" ", time=piece_end_seconds))

    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def handle_melody_audition(job: Job, client) -> list[str]:
    if len(job.input_version_ids) != 1:
        raise ValueError("melody_audition requires exactly one MIDI input version")

    owner_id = _owner_id(job)
    input_version_id = job.input_version_ids[0]
    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)
    insight_repo = InsightRepo(client)
    entity_repo = EntityRepo(client)

    _update_progress(client, job.id, 0.08, "loading melody evidence")
    input_version = version_repo.get(input_version_id, owner_id)
    if not input_version:
        raise ValueError(f"version {input_version_id} not found")
    input_artifact = artifact_repo.get(input_version.artifact_id, owner_id)
    if not input_artifact:
        raise ValueError(f"artifact {input_version.artifact_id} not found")
    if input_artifact.kind not in _ALLOWED_INPUT_KINDS:
        raise ValueError("melody_audition requires a MIDI input version")

    raw_insight_id = job.parameters.get("insight_id")
    if not isinstance(raw_insight_id, str):
        raise ValueError("melody_audition requires insight_id")
    try:
        insight_id = UUID(raw_insight_id)
    except ValueError as error:
        raise ValueError("melody_audition insight_id is invalid") from error
    insight = insight_repo.get(insight_id, owner_id)
    if not insight:
        raise ValueError(f"insight {insight_id} not found")
    if insight.version_id != input_version.id:
        raise ValueError("melody insight and MIDI input do not share one exact Version")
    if insight.kind != "melody":
        raise ValueError("melody_audition requires melody evidence")

    _update_progress(client, job.id, 0.28, "resolving exact Piano Roll notes")
    entities = entity_repo.list_by_version(input_version.id, owner_id)
    matched = match_melody_note_entities(insight, entities)
    if not matched:
        raise ValueError("melody insight contains no playable notes")
    piece_end_seconds = max(
        (
            entity.note.end_seconds
            for entity in entities
            if entity.kind == EntityKind.note and entity.note is not None
        ),
        default=max(entity.note.end_seconds for entity in matched if entity.note),
    )

    _update_progress(client, job.id, 0.48, "preparing melody playback")
    melody_midi = _build_melody_midi(matched, piece_end_seconds)
    _update_progress(client, job.id, 0.62, "rendering melody playback")
    wav_bytes = music_features.midi_to_wav(melody_midi, sr=22050)

    _update_progress(client, job.id, 0.82, "storing melody playback")
    storage_key = f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/melody-playback.wav"
    client.storage.from_(_STORAGE_BUCKET).upload(
        storage_key,
        wav_bytes,
        {"content-type": "audio/wav"},
    )
    output_artifact = artifact_repo.create(
        Artifact(
            work_id=input_artifact.work_id,
            kind=ArtifactKind.audio_rendered,
            mime_type="audio/wav",
        ),
        owner_id,
    )
    output_version = version_repo.create(
        Version(
            artifact_id=output_artifact.id,
            parent_version_id=input_version.id,
            lineage=[input_version.id],
            storage_key=storage_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=len(wav_bytes),
            sha256=hashlib.sha256(wav_bytes).hexdigest(),
            produced_by_job_id=job.id,
            created_by=owner_id,
            label="Melody playback",
            metadata={
                "representation": "melody_playback",
                "playback_role": "melody",
                "source_midi_version_id": str(input_version.id),
                "source_insight_id": str(insight.id),
                "source_note_ids": [str(entity.id) for entity in matched],
                "note_count": len(matched),
                "duration_seconds": piece_end_seconds,
                "experimental": True,
                "synthesized": True,
                "quality_notice": (
                    "Synthesized from the experimental melody proposal; "
                    "not source-separated recording audio."
                ),
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "melody playback ready")
    return [str(output_version.id)]


def register_melody_audition_capability(worker) -> None:
    worker.register("melody_audition", "1.0", handle_melody_audition)
