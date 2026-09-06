"""Durable worker capability for experimental natural-language passage Find.

The capability consumes two exact immutable Versions: source audio plus a
performance-MIDI Version directly parented to that source. CLaMP3 C2 operates on
the performance representation, while candidate locators remain source-audio
seconds because that MIDI preserves the direct parent's performance timeline.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo
from domain.text_passage_find import TextPassageFindQuery, find_text_passages
from domain.work_bundle_repository import WorkBundleRepository
from engines.retrieval.clamp3_c2 import default_clamp3_c2_retriever

_STORAGE_BUCKET = "artifacts"
_METHOD_ID = "clamp3_c2_text_performance_cosine"
_ALLOWED_SOURCE_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("text_passage_find requires a job owner")
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


def _load_exact_pair(
    job: Job,
    client,
    owner_id: str,
) -> tuple[Version, Artifact, Version, Artifact]:
    if len(job.input_version_ids) != 2:
        raise ValueError("text_passage_find requires source audio and performance MIDI inputs")

    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)
    source_version = version_repo.get(job.input_version_ids[0], owner_id)
    performance_version = version_repo.get(job.input_version_ids[1], owner_id)
    if not source_version or not performance_version:
        raise ValueError("text_passage_find input Version not found")

    source_artifact = artifact_repo.get(source_version.artifact_id, owner_id)
    performance_artifact = artifact_repo.get(performance_version.artifact_id, owner_id)
    if not source_artifact or not performance_artifact:
        raise ValueError("text_passage_find input Artifact not found")
    if source_artifact.work_id != performance_artifact.work_id:
        raise ValueError("text_passage_find inputs must belong to one exact Work")
    if source_artifact.kind not in _ALLOWED_SOURCE_KINDS:
        raise ValueError("text_passage_find source input must be audio")
    if performance_artifact.kind != ArtifactKind.midi_performance:
        raise ValueError("text_passage_find second input must be performance MIDI")
    if performance_version.parent_version_id != source_version.id:
        raise ValueError("performance MIDI must be directly parented to the source audio Version")

    return source_version, source_artifact, performance_version, performance_artifact


def handle_text_passage_find(job: Job, client) -> list[str]:
    """Execute C2 retrieval and persist one exact-Version-scoped analysis report."""

    owner_id = _owner_id(job)
    _update_progress(client, job.id, 0.08, "loading exact Find inputs")
    source_version, source_artifact, performance_version, _ = _load_exact_pair(
        job, client, owner_id
    )

    query = TextPassageFindQuery(
        text=str(job.parameters.get("text") or ""),
        max_matches=job.parameters.get("max_matches", 3),
    )
    # Reload durable Work truth at execution time; dispatch-time lookup is not authority.
    snapshot = WorkBundleRepository(client).load(source_artifact.work_id, owner_id)
    if not snapshot:
        raise ValueError("text_passage_find Work not found")

    _update_progress(client, job.id, 0.2, "loading exact performance MIDI")

    def load_performance(version: Version) -> bytes:
        if version.id != performance_version.id:
            raise PermissionError("unexpected performance Version requested")
        return client.storage.from_(version.storage_bucket).download(version.storage_key)

    _update_progress(client, job.id, 0.32, "finding passages under CLaMP3 C2")
    retriever = default_clamp3_c2_retriever()
    result = find_text_passages(
        snapshot,
        source_version=source_version,
        performance_version=performance_version,
        query=query,
        load_performance=load_performance,
        retrieve=retriever.retrieve,
    )
    if result.status != "supported" or result.observation is None:
        detail = "; ".join(result.reasons) or result.status
        if result.status == "withheld":
            raise ValueError(f"text_passage_find withheld: {detail}")
        raise RuntimeError(f"text_passage_find {result.status}: {detail}")

    report_bytes = result.model_dump_json(indent=2).encode("utf-8")
    _update_progress(client, job.id, 0.82, "storing passage Find result")
    storage_key = f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/text-passage-find.json"
    client.storage.from_(_STORAGE_BUCKET).upload(
        storage_key,
        report_bytes,
        {"content-type": "application/json"},
    )

    artifact_repo = ArtifactRepo(client)
    version_repo = VersionRepo(client)
    output_artifact = artifact_repo.create(
        Artifact(
            work_id=source_artifact.work_id,
            kind=ArtifactKind.analysis_report,
            mime_type="application/json",
        ),
        owner_id,
    )
    observation = result.observation
    output_version = version_repo.create(
        Version(
            artifact_id=output_artifact.id,
            parent_version_id=source_version.id,
            lineage=[source_version.id, performance_version.id],
            storage_key=storage_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=len(report_bytes),
            sha256=hashlib.sha256(report_bytes).hexdigest(),
            produced_by_job_id=job.id,
            created_by=owner_id,
            label="Experimental passage Find",
            metadata={
                "report_type": "text_passage_find",
                "experimental": True,
                "issue": 1254,
                "source_version_id": str(source_version.id),
                "performance_version_id": str(performance_version.id),
                "method": _METHOD_ID,
                "candidate_count": len(observation.candidates),
                "query_sha256": hashlib.sha256(observation.query_text.encode("utf-8")).hexdigest(),
                "model": observation.provenance.get("model"),
                "upstream_revision": observation.provenance.get("upstream_revision"),
                "checkpoint_sha256": observation.provenance.get("checkpoint_sha256"),
                "factual_truth": False,
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "passage Find ready")
    return [str(output_version.id)]


def register_text_passage_find_capability(worker) -> None:
    worker.register("text_passage_find", "1.0", handle_text_passage_find)


__all__ = [
    "handle_text_passage_find",
    "register_text_passage_find_capability",
]
