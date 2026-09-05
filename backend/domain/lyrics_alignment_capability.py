"""Worker capability for experimental supplied-text alignment."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

from domain.lyrics_alignment import (
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_MODEL,
    DEFAULT_TRUSTED_SCORE,
    align_supplied_text,
)
from domain.lyrics_alignment_report import METHOD_ID, REPORT_SCHEMA_VERSION
from domain.models import Artifact, ArtifactKind, Job, Version
from domain.repositories import ArtifactRepo, VersionRepo

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

    source_text = str(job.parameters.get("source_text") or "")
    source_kind = str(job.parameters.get("text_source_kind") or "")
    if source_kind not in {"user_supplied", "licensed", "public_domain", "other_permitted"}:
        raise ValueError("lyrics_alignment requires an explicitly permitted text source")
    if not source_text.strip():
        raise ValueError("lyrics_alignment requires non-empty supplied text")

    language = job.parameters.get("language")
    if language is not None:
        language = str(language)
    model_name = str(job.parameters.get("model_name") or DEFAULT_MODEL)
    if model_name != DEFAULT_MODEL:
        raise ValueError(f"unsupported lyrics alignment model: {model_name}")
    match_threshold = float(job.parameters.get("match_threshold", DEFAULT_MATCH_THRESHOLD))
    trusted_score = float(job.parameters.get("trusted_score", DEFAULT_TRUSTED_SCORE))

    _update_progress(client, job.id, 0.25, "downloading exact source audio version")
    audio_bytes = client.storage.from_(input_version.storage_bucket).download(
        input_version.storage_key
    )
    suffix = Path(input_version.label).suffix or ".wav"

    _update_progress(client, job.id, 0.4, "aligning supplied text to audio evidence")
    with tempfile.NamedTemporaryFile(suffix=suffix) as audio_file:
        audio_file.write(audio_bytes)
        audio_file.flush()
        report = align_supplied_text(
            source_text=source_text,
            source_kind=source_kind,
            audio_path=Path(audio_file.name),
            work_id=input_artifact.work_id,
            artifact_id=input_artifact.id,
            version_id=input_version.id,
            model_name=model_name,
            language=language,
            match_threshold=match_threshold,
            trusted_score=trusted_score,
        )
    report_bytes = report.model_dump_json(indent=2).encode("utf-8")

    _update_progress(client, job.id, 0.78, "storing supplied-text alignment")
    storage_key = (
        f"jobs/{job.id}/attempt-{job.lifecycle.retry_count}/supplied-text-alignment.json"
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
            produced_by_job_id=job.id,
            created_by=owner_id,
            label="Experimental supplied-text alignment",
            metadata={
                "report_type": "supplied_text_alignment",
                "schema_version": REPORT_SCHEMA_VERSION,
                "experimental": True,
                "source_version_id": str(input_version.id),
                "source_artifact_id": str(input_artifact.id),
                "text_source_kind": source_kind,
                "text_sha256": report.text_provenance.sha256,
                "method": METHOD_ID,
                "engine": report.method.engine,
                "engine_version": report.method.engine_version,
                "engine_release": report.method.engine_release,
                "transcription_engine": report.method.transcription_engine,
                "transcription_engine_version": report.method.transcription_engine_version,
                "model_name": report.method.model_name,
                "aligned_word_count": sum(word.status == "aligned" for word in report.words),
                "ambiguous_word_count": sum(word.status == "ambiguous" for word in report.words),
                "failed_word_count": sum(word.status == "failed" for word in report.words),
                "issue": 1181,
            },
        ),
        owner_id,
    )
    _update_progress(client, job.id, 1.0, "supplied-text alignment ready")
    return [str(output_version.id)]


def register_lyrics_alignment_capability(worker) -> None:
    worker.register("lyrics_alignment", "1.0", handle_lyrics_alignment)
