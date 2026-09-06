"""Dormant worker capability for bounded AnalysisGNN score-analysis reports.

The capability is worker-registered but intentionally has no public workflow
dispatch while the exact pretrained artifact terms and real runtime proof remain
unresolved. That keeps the persistence path testable without making an unavailable
or legally ambiguous model user-reachable.
"""

from __future__ import annotations

from uuid import UUID

from domain.analysisgnn_score_report import REPORT_SCHEMA_VERSION, REPORT_TYPE, build_analysisgnn_score_report
from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo
from engines.symbolic.analysisgnn import AnalysisGNNEngine, PRODUCT_SCORE_TASKS, normalize_score_evidence

_STORAGE_BUCKET = "artifacts"


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("analysisgnn_score requires a job owner")
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


def handle_analysisgnn_score(job: Job, client) -> list[str]:
    """Analyze one exact trusted MusicXML Version and persist bounded proposals."""

    if len(job.input_version_ids) != 1:
        raise ValueError("analysisgnn_score requires exactly one MusicXML input version")

    owner_id = _owner_id(job)
    input_version_id = job.input_version_ids[0]
    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)

    _update_progress(client, job.id, 0.1, "loading exact source score version")
    input_version = version_repo.get(input_version_id, owner_id)
    if not input_version:
        raise ValueError(f"version {input_version_id} not found")
    input_artifact = artifact_repo.get(input_version.artifact_id, owner_id)
    if not input_artifact:
        raise ValueError(f"artifact {input_version.artifact_id} not found")
    if input_artifact.kind != ArtifactKind.musicxml_score:
        raise ValueError("analysisgnn_score requires a MusicXML score version")

    _update_progress(client, job.id, 0.25, "downloading exact source score")
    musicxml_bytes = client.storage.from_(input_version.storage_bucket).download(
        input_version.storage_key
    )

    _update_progress(client, job.id, 0.45, "running experimental score analysis")
    engine_result = AnalysisGNNEngine().analyze_musicxml(
        musicxml_bytes,
        tasks=PRODUCT_SCORE_TASKS,
    )
    evidence = normalize_score_evidence(engine_result)
    report = build_analysisgnn_score_report(
        evidence,
        work_id=input_artifact.work_id,
        source_score_artifact_id=input_artifact.id,
        source_score_version_id=input_version.id,
    )
    report_bytes = report.model_dump_json(indent=2).encode("utf-8")

    _update_progress(client, job.id, 0.78, "storing experimental score analysis")
    storage_key = f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/analysisgnn-score.json"
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
    method_parameters = report.method.parameters
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
            label="Experimental Score Analysis",
            metadata={
                "report_type": REPORT_TYPE,
                "schema_version": REPORT_SCHEMA_VERSION,
                "experimental": True,
                "source_score_version_id": str(input_version.id),
                "source_score_artifact_id": str(input_artifact.id),
                "engine": report.method.engine,
                "engine_version": report.method.library_version,
                "model": report.method.model,
                "model_license": method_parameters.get("model_license", "UNVERIFIED"),
                "runtime_classification": method_parameters.get(
                    "runtime_classification", "INTERNAL_ONLY"
                ),
                "checkpoint_sha256": method_parameters.get("checkpoint_sha256"),
                "tasks": list(report.tasks),
                "observation_count": len(report.observations),
                "issue": 1248,
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "experimental score analysis ready")
    return [str(output_version.id)]


def register_analysisgnn_score_capability(worker) -> None:
    worker.register("analysisgnn_score", "1.0", handle_analysisgnn_score)
