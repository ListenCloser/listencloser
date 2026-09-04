"""Worker capability for experimental symbolic-detail analysis."""

from __future__ import annotations

import hashlib
from uuid import UUID

from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo
from domain.symbolic_detail_report import METHOD_ID, REPORT_SCHEMA_VERSION
from symbolic_detail import build_symbolic_detail

_STORAGE_BUCKET = "artifacts"
_ALLOWED_INPUT_KINDS = {ArtifactKind.midi_performance, ArtifactKind.midi_corrected}


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("symbolic_detail requires a job owner")
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


def handle_symbolic_detail(job: Job, client) -> list[str]:
    if len(job.input_version_ids) != 1:
        raise ValueError("symbolic_detail requires exactly one MIDI input version")

    owner = _owner_id(job)
    input_version_id = job.input_version_ids[0]
    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)

    _update_progress(client, job.id, 0.1, "loading source MIDI version")
    input_version = version_repo.get(input_version_id, owner)
    if not input_version:
        raise ValueError(f"version {input_version_id} not found")
    input_artifact = artifact_repo.get(input_version.artifact_id, owner)
    if not input_artifact:
        raise ValueError(f"artifact {input_version.artifact_id} not found")
    if input_artifact.kind not in _ALLOWED_INPUT_KINDS:
        raise ValueError("symbolic_detail requires a performance or corrected MIDI Version")

    _update_progress(client, job.id, 0.3, "downloading source MIDI")
    midi_bytes = client.storage.from_(input_version.storage_bucket).download(input_version.storage_key)

    _update_progress(client, job.id, 0.5, "measuring symbolic detail")
    report = build_symbolic_detail(
        midi_bytes,
        source_version_id=input_version.id,
        source_artifact_kind=input_artifact.kind.value,
    )
    report_bytes = report.model_dump_json(indent=2).encode("utf-8")

    _update_progress(client, job.id, 0.8, "storing symbolic detail")
    storage_key = f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/symbolic-detail.json"
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
        owner,
    )
    output_version = version_repo.create(
        Version(
            artifact_id=output_artifact.id,
            parent_version_id=input_version.id,
            lineage=[input_version.id],
            storage_key=storage_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=len(report_bytes),
            sha256=hashlib.sha256(report_bytes).hexdigest(),
            produced_by_job_id=job.id,
            created_by=owner,
            label="Experimental Symbolic Detail",
            metadata={
                "report_type": "symbolic_detail",
                "schema_version": REPORT_SCHEMA_VERSION,
                "experimental": True,
                "source_version_id": str(input_version.id),
                "source_artifact_id": str(input_artifact.id),
                "source_artifact_kind": input_artifact.kind.value,
                "source_sha256": input_version.sha256,
                "method": METHOD_ID,
                "canonical_theory": False,
                "issue": 1178,
            },
        ),
        owner,
    )
    _update_progress(client, job.id, 1.0, "symbolic detail ready")
    return [str(output_version.id)]


def register_symbolic_detail_capability(worker) -> None:
    worker.register("symbolic_detail", "1.0", handle_symbolic_detail)
