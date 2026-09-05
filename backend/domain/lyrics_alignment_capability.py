"""Worker capability for supplied-text audio alignment."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import UUID

from domain.lyrics_alignment_report import (
    METHOD_ID,
    REPORT_SCHEMA_VERSION,
    LyricsAlignmentRequest,
)
from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo
from lyrics_alignment import align_supplied_text_to_audio

_STORAGE_BUCKET = "artifacts"
_ALLOWED_INPUT_KINDS = {
    ArtifactKind.audio_original,
    ArtifactKind.audio_enhanced,
    ArtifactKind.audio_rendered,
}


def _owner_id(job: Job) -> str:
    if not job.created_by:
        raise ValueError("lyrics_alignment requires a job owner")
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


def handle_lyrics_alignment(job: Job, client) -> list[str]:
    if len(job.input_version_ids) != 1:
        raise ValueError("lyrics_alignment requires exactly one audio input version")

    request = LyricsAlignmentRequest.model_validate(job.parameters)
    owner_id = _owner_id(job)
    input_version_id = job.input_version_ids[0]
    version_repo = VersionRepo(client)
    artifact_repo = ArtifactRepo(client)

    _update_progress(client, job.id, 0.1, "loading exact source audio version")
    input_version = version_repo.get(input_version_id, owner_id)
    if not input_version:
        raise ValueError(f"version {input_version_id} not found")
    input_artifact = artifact_repo.get(input_version.artifact_id, owner_id)
    if not input_artifact:
        raise ValueError(f"artifact {input_version.artifact_id} not found")
    if input_artifact.kind not in _ALLOWED_INPUT_KINDS:
        raise ValueError("lyrics_alignment requires an audio input version")

    _update_progress(client, job.id, 0.25, "downloading exact source audio")
    audio_bytes = client.storage.from_(input_version.storage_bucket).download(
        input_version.storage_key
    )
    audio_sha256 = sha256(audio_bytes).hexdigest()
    if input_version.sha256 and input_version.sha256 != audio_sha256:
        raise ValueError("source audio sha256 does not match Version provenance")
    text_sha256 = sha256(request.text.encode("utf-8")).hexdigest()

    requested_fmt = str(job.parameters.get("fmt") or "").strip().lower()
    label_fmt = Path(input_version.label).suffix.lstrip(".").lower()
    fmt = requested_fmt or label_fmt or "wav"

    _update_progress(client, job.id, 0.45, "aligning supplied text to source audio")
    report = align_supplied_text_to_audio(
        audio_bytes,
        fmt=fmt,
        source_text=request.text,
        source_text_sha256=text_sha256,
        text_source=request.text_source,
        text_source_reference=request.text_source_reference,
        source_audio_version_id=input_version.id,
        source_audio_artifact_id=input_artifact.id,
        source_audio_sha256=audio_sha256,
        ambiguity_threshold=request.ambiguity_threshold,
    )
    report_bytes = report.model_dump_json(indent=2).encode("utf-8")

    _update_progress(client, job.id, 0.78, "storing supplied-text alignment")
    storage_key = (
        f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/lyrics-alignment.json"
    )
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
            sha256=sha256(report_bytes).hexdigest(),
            produced_by_job_id=job.id,
            created_by=owner_id,
            label="Experimental Supplied-text Alignment",
            metadata={
                "report_type": "lyrics_alignment",
                "schema_version": REPORT_SCHEMA_VERSION,
                "experimental": True,
                "fallback": True,
                "frontend_exposure": "deferred",
                "source_version_id": str(input_version.id),
                "source_artifact_id": str(input_artifact.id),
                "source_audio_sha256": audio_sha256,
                "source_text_sha256": text_sha256,
                "text_source": request.text_source,
                "language": request.language,
                "method": METHOD_ID,
                "alignment_status": report.status,
                "aligned_span_count": sum(
                    span.status == "aligned" for span in report.spans
                ),
                "ambiguous_span_count": sum(
                    span.status == "ambiguous" for span in report.spans
                ),
                "failed_span_count": sum(
                    span.status == "failed" for span in report.spans
                ),
                "transcription_used": False,
                "issue": 1181,
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "supplied-text alignment ready")
    return [str(output_version.id)]


def register_lyrics_alignment_capability(worker) -> None:
    worker.register("lyrics_alignment", "1.0", handle_lyrics_alignment)
