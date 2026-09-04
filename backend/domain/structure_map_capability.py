"""Worker capability for the experimental Structure Map."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo
from domain.structure_map_report import METHOD_ID, REPORT_SCHEMA_VERSION
from structure_map import extract_structure_map_from_bytes

_STORAGE_BUCKET = "artifacts"
_ALLOWED_INPUT_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("structure_map requires a job owner")
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


def handle_structure_map(job: Job, client) -> list[str]:
    if len(job.input_version_ids) != 1:
        raise ValueError("structure_map requires exactly one audio input version")

    owner_id = _owner_id(job)
    input_version_id = job.input_version_ids[0]
    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)

    _update_progress(client, job.id, 0.1, "loading source audio version")
    input_version = version_repo.get(input_version_id, owner_id)
    if not input_version:
        raise ValueError(f"version {input_version_id} not found")
    input_artifact = artifact_repo.get(input_version.artifact_id, owner_id)
    if not input_artifact:
        raise ValueError(f"artifact {input_version.artifact_id} not found")
    if input_artifact.kind not in _ALLOWED_INPUT_KINDS:
        raise ValueError("structure_map requires an audio input version")

    _update_progress(client, job.id, 0.25, "downloading source audio")
    audio_bytes = client.storage.from_(input_version.storage_bucket).download(
        input_version.storage_key
    )
    requested_fmt = str(job.parameters.get("fmt") or "").strip().lower()
    label_fmt = Path(input_version.label).suffix.lstrip(".").lower()
    fmt = requested_fmt or label_fmt or "wav"

    _update_progress(client, job.id, 0.45, "finding candidate structure spans")
    report = extract_structure_map_from_bytes(
        audio_bytes,
        source_version_id=input_version.id,
        fmt=fmt,
    )
    report_bytes = report.model_dump_json(indent=2).encode("utf-8")

    _update_progress(client, job.id, 0.78, "storing structure map")
    storage_key = f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/structure-map.json"
    client.storage.from_(_STORAGE_BUCKET).upload(
        storage_key,
        report_bytes,
        {"content-type": "application/json"},
    )
    output_artifact = artifact_repo.create(
        Artifact(
            work_id=input_artifact.work_id,
            kind=ArtifactKind.analysis_report,
            mime_type="application/json",
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
            byte_size=len(report_bytes),
            produced_by_job_id=job.id,
            created_by=owner_id,
            label="Experimental Structure Map",
            metadata={
                "report_type": "structure_map",
                "schema_version": REPORT_SCHEMA_VERSION,
                "experimental": True,
                "source_version_id": str(input_version.id),
                "source_artifact_id": str(input_artifact.id),
                "method": METHOD_ID,
                "candidate_span_count": len(report.candidate_spans),
                "semantic_labels": False,
                "issue": 1175,
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "structure map ready")
    return [str(output_version.id)]


def register_structure_map_capability(worker) -> None:
    worker.register("structure_map", "1.0", handle_structure_map)
