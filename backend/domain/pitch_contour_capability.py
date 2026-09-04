"""Durable worker capability for experimental continuous-pitch evidence."""

from __future__ import annotations

import json
from pathlib import Path

from audio_processing import decode_audio_to_wav
from domain.capabilities import (
    _artifact_kind_for_version,
    _create_output_version,
    _job_storage_key,
    _lookup_version,
    _resolve_owner_id,
    _resolve_work_id,
    _update_progress,
    _upload_bytes,
    download_version_bytes,
)
from domain.models import ArtifactKind, Job
from engines.pitch.pyin import estimate_pitch_contour

_ALLOWED_AUDIO_KINDS = {ArtifactKind.audio_original, ArtifactKind.audio_enhanced}


def handle_pitch_contour(job: Job, client) -> list[str]:
    """Extract pYIN F0 evidence from one immutable audio Version."""
    if len(job.input_version_ids) != 1:
        raise ValueError("pitch_contour requires exactly one audio input version")

    input_version = _lookup_version(client, job.input_version_ids[0])
    input_kind = _artifact_kind_for_version(client, input_version.id)
    if input_kind not in _ALLOWED_AUDIO_KINDS:
        raise ValueError("pitch_contour requires an original or enhanced audio version")

    owner_id = _resolve_owner_id(client, job.workflow_id)
    work_id = _resolve_work_id(client, input_version.id)
    _update_progress(client, job.id, 0.08, "downloading source audio")
    audio_bytes = download_version_bytes(input_version, client)

    fmt = Path(input_version.label).suffix.lstrip(".").lower() or "wav"
    _update_progress(client, job.id, 0.2, "decoding mono analysis audio")
    decoded_wav = decode_audio_to_wav(audio_bytes, fmt=fmt)

    _update_progress(client, job.id, 0.35, "estimating continuous pitch")
    result = estimate_pitch_contour(decoded_wav)
    payload = {
        "schema_version": 1,
        "representation_type": "pitch_contour",
        "status": "experimental",
        "source_audio_version_id": str(input_version.id),
        "source_audio_artifact_kind": input_kind.value,
        **result,
    }
    content = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")

    _update_progress(client, job.id, 0.9, "persisting pitch contour")
    storage_key = _job_storage_key(job, "pitch-contour.json")
    _upload_bytes(client, "artifacts", storage_key, content, "application/json")
    output_version_id = _create_output_version(
        client,
        work_id,
        ArtifactKind.analysis_report,
        storage_key,
        content,
        input_version.id,
        job,
        owner_id,
        mime_type="application/json",
        label="Pitch contour · Experimental",
        metadata={
            "representation_type": "pitch_contour",
            "status": "experimental",
            "source_audio_version_id": str(input_version.id),
            "engine": result["engine"],
            "preprocessing": result["preprocessing"],
            "quality_notice": (
                "Experimental monophonic F0 evidence. Polyphony, noisy mixtures, and strong "
                "overtones can produce octave or subharmonic errors."
            ),
        },
    )
    _update_progress(client, job.id, 1.0, "pitch contour ready")
    return [str(output_version_id)]


def register_pitch_contour_capability(worker) -> None:
    worker.register("pitch_contour", "1.0", handle_pitch_contour)
