"""Durable worker capability for exact Score ↔ performance alignment.

This capability deliberately accepts exact immutable Versions only. It never resolves
"latest" Score/MIDI, never substitutes timestamps for a failed matcher, and does not
change either representation's authority. The first product slice accepts canonical
performance MIDI; explicit corrected-performance authority can be added separately.
"""

from __future__ import annotations

from uuid import UUID

from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo
from domain.score_performance_alignment import AlignmentSufficiencyPolicy
from domain.score_performance_note_identity import canonical_alignment_report_json
from engines.alignment.parangonar import ParangonarAlignmentEngine

_STORAGE_BUCKET = "artifacts"
_REPORT_TYPE = "score_performance_alignment"
_REPORT_SCHEMA_VERSION = 2
_DEFAULT_POLICY = AlignmentSufficiencyPolicy(
    minimum_score_fraction=0.8,
    minimum_performance_fraction=0.8,
)


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("score_performance_alignment requires a job owner")
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


def handle_score_performance_alignment(job: Job, client) -> list[str]:
    """Align one exact MusicXML Version to one exact canonical performance MIDI Version."""

    if len(job.input_version_ids) != 2:
        raise ValueError(
            "score_performance_alignment requires exact score and performance Versions"
        )

    owner_id = _owner_id(job)
    score_version_id, performance_version_id = job.input_version_ids
    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)

    _update_progress(client, job.id, 0.1, "loading exact Score and performance Versions")
    score_version = version_repo.get(score_version_id, owner_id)
    performance_version = version_repo.get(performance_version_id, owner_id)
    if not score_version or not performance_version:
        raise ValueError("score or performance Version not found")

    score_artifact = artifact_repo.get(score_version.artifact_id, owner_id)
    performance_artifact = artifact_repo.get(performance_version.artifact_id, owner_id)
    if not score_artifact or not performance_artifact:
        raise ValueError("score or performance Artifact not found")
    if score_artifact.work_id != performance_artifact.work_id:
        raise ValueError("score and performance Versions must belong to the same Work")
    if score_artifact.kind != ArtifactKind.musicxml_score:
        raise ValueError("score_performance_alignment requires a MusicXML score Version")
    if performance_artifact.kind != ArtifactKind.midi_performance:
        raise ValueError(
            "score_performance_alignment first slice requires canonical performance MIDI"
        )

    _update_progress(client, job.id, 0.25, "downloading exact Score and performance evidence")
    score_bytes = client.storage.from_(score_version.storage_bucket).download(
        score_version.storage_key
    )
    performance_bytes = client.storage.from_(performance_version.storage_bucket).download(
        performance_version.storage_key
    )

    _update_progress(client, job.id, 0.45, "aligning Score to performed notes")
    execution = ParangonarAlignmentEngine().align_with_identity(
        score_musicxml=score_bytes,
        performance_midi=performance_bytes,
        score_version_id=score_version.id,
        performance_version_id=performance_version.id,
        sufficiency_policy=_DEFAULT_POLICY,
    )
    relation = execution.relation
    report_bytes = canonical_alignment_report_json(
        relation,
        execution.event_identity,
    ).encode("utf-8")

    _update_progress(client, job.id, 0.78, "storing exact Score-performance relation")
    storage_key = (
        f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/score-performance-alignment.json"
    )
    client.storage.from_(_STORAGE_BUCKET).upload(
        storage_key,
        report_bytes,
        {"content-type": "application/json"},
    )
    output_artifact = artifact_repo.create(
        Artifact(
            work_id=score_artifact.work_id,
            kind=ArtifactKind.analysis_report,
            mime_type="application/json",
        ),
        owner_id,
    )
    output_version = version_repo.create(
        Version(
            artifact_id=output_artifact.id,
            parent_version_id=score_version.id,
            lineage=[score_version.id, performance_version.id],
            storage_key=storage_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=len(report_bytes),
            produced_by_job_id=job.id,
            created_by=owner_id,
            label="Score ↔ performance alignment",
            metadata={
                "report_type": _REPORT_TYPE,
                "schema_version": _REPORT_SCHEMA_VERSION,
                "identity_schema_version": execution.event_identity.schema_version,
                "score_version_id": str(score_version.id),
                "performance_version_id": str(performance_version.id),
                "package": relation.method.package,
                "package_version": relation.method.package_version,
                "matcher": relation.method.matcher,
                "sufficiency": relation.sufficiency.value,
                "projection_precision": relation.projection_precision.value,
                "score_events_total": relation.coverage.score_events_total,
                "score_events_mapped": relation.coverage.score_events_mapped,
                "performance_events_total": relation.coverage.performance_events_total,
                "performance_events_mapped": relation.coverage.performance_events_mapped,
                "issue": 1083,
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "Score-performance alignment ready")
    return [str(output_version.id)]


def register_score_performance_alignment_capability(worker) -> None:
    worker.register(
        "score_performance_alignment",
        "1.0",
        handle_score_performance_alignment,
    )
