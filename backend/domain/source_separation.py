"""Optional, user-triggered source separation for Experimental Layers.

This capability is deliberately not part of the universal understand workflow.
It runs HTDemucs in a child process so the model's ~GB-scale working set is
released after the job and so a separator failure cannot corrupt the durable
source Work or its normal playback path.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from domain.capabilities import (
    _artifact_kind_for_version,
    _cleanup_partial_job_outputs,
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

logger = logging.getLogger("domain.source_separation")

DEMUCS_PACKAGE_VERSION = "4.1.0"
HTDEMUCS_MODEL = "htdemucs"
HTDEMUCS_MODEL_SIGNATURE = "955717e8"
HTDEMUCS_CHECKPOINT = "adefossez/HTDemucs/955717e8.safetensors"
HTDEMUCS_CHECKPOINT_SHA256 = "d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd"
HTDEMUCS_CODE_LICENSE = "MIT"
HTDEMUCS_CHECKPOINT_LICENSE = "MIT"
HTDEMUCS_UPSTREAM = "https://github.com/adefossez/demucs"
HTDEMUCS_WEIGHTS = "https://huggingface.co/adefossez/HTDemucs"
STEM_ROLES = ("vocals", "drums", "bass", "other")

_STORAGE_BUCKET = "artifacts"
_ALLOWED_INPUT_FORMATS = {"wav", "mp3", "m4a", "flac", "ogg", "aac"}
_SEPARATION_TIMEOUT_SECONDS = 30 * 60
_SEPARATION_POLL_SECONDS = 0.5
_SEPARATION_TERMINATE_GRACE_SECONDS = 5.0
# Historical #507 measured ~1.6-1.8 GB peak RSS per CPU inference. Keep one
# separator child active per worker process until real production concurrency is
# measured; this semaphore lives only inside this capability and therefore does
# not serialize unrelated worker handlers when WORKER_CONCURRENCY > 1.
_SEPARATION_SLOT = threading.Semaphore(1)


def _input_format(value: object) -> str:
    fmt = str(value or "wav").lower().lstrip(".")
    if fmt not in _ALLOWED_INPUT_FORMATS:
        raise ValueError(f"unsupported source-separation input format: {fmt}")
    return fmt


def _validate_stem_bytes(role: str, data: bytes) -> None:
    # Demucs' default output is a PCM WAV. Validate the literal media contract,
    # not musical quality; leakage or missing musical content can still occur.
    if len(data) <= 44 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
        raise RuntimeError(f"HTDemucs did not produce a valid {role} WAV")


def _job_cancelled(client, job_id: UUID) -> bool:
    """Read the durable cancellation bit without creating a second job system."""
    try:
        result = client.table("jobs").select("stage").eq("id", str(job_id)).limit(1).execute()
    except Exception:
        # The worker's own heartbeat independently observes cancellation and
        # lease state. A transient cancellation-read failure must not turn into
        # an invented cancellation or silently abandon a running child.
        logger.exception("source_separation_cancel_check_failed", extra={"job_id": str(job_id)})
        return False
    return bool(result.data and result.data[0].get("stage") == "cancelled")


def _terminate_process(process: subprocess.Popen) -> None:
    """Terminate the dedicated Demucs process group, escalating after a short grace."""
    if process.poll() is not None:
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        # Production is Linux and uses start_new_session=True. Keep a narrow
        # fallback for test/dev environments where process groups are unavailable.
        process.terminate()

    try:
        process.wait(timeout=_SEPARATION_TERMINATE_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
    process.wait(timeout=_SEPARATION_TERMINATE_GRACE_SECONDS)


def run_htdemucs(
    audio_bytes: bytes,
    fmt: str,
    *,
    runtime_python: str | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    timeout_seconds: float = _SEPARATION_TIMEOUT_SECONDS,
    poll_seconds: float = _SEPARATION_POLL_SECONDS,
) -> dict[str, bytes]:
    """Run the exact pinned four-stem model and return validated WAV bytes.

    HTDemucs receives its own process group. Cancellation, timeout, or any
    exception while supervising it terminates that group before control returns
    to the durable worker thread, so a failed optional capability cannot leave a
    runaway separator consuming worker memory/CPU.
    """
    if timeout_seconds <= 0:
        raise ValueError("source-separation timeout must be positive")
    if poll_seconds <= 0:
        raise ValueError("source-separation poll interval must be positive")

    python = runtime_python or sys.executable
    source_format = _input_format(fmt)

    with tempfile.TemporaryDirectory(prefix="listencloser-layers-") as tmp:
        root = Path(tmp)
        input_path = root / f"source.{source_format}"
        output_root = root / "separated"
        log_path = root / "demucs.log"
        input_path.write_bytes(audio_bytes)

        command = [
            python,
            "-m",
            "demucs",
            "-n",
            HTDEMUCS_MODEL,
            "--shifts",
            "0",
            "-d",
            "cpu",
            "--out",
            str(output_root),
            str(input_path),
        ]
        env = os.environ.copy()
        # The production image acquires and verifies the checkpoint at build
        # time. Runtime inference must never turn a user's click into an
        # unpinned network model download.
        env["HF_HUB_OFFLINE"] = "1"
        env["OMP_NUM_THREADS"] = "2"
        env["MKL_NUM_THREADS"] = "2"
        env["OPENBLAS_NUM_THREADS"] = "2"

        deadline = time.monotonic() + timeout_seconds
        with log_path.open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                command,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                start_new_session=True,
            )
            try:
                while True:
                    returncode = process.poll()
                    if returncode is not None:
                        break
                    if is_cancelled is not None and is_cancelled():
                        _terminate_process(process)
                        raise RuntimeError("HTDemucs source separation was cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        _terminate_process(process)
                        raise RuntimeError("HTDemucs source separation timed out")
                    time.sleep(min(poll_seconds, remaining))
            except BaseException:
                _terminate_process(process)
                raise

        if returncode != 0:
            try:
                log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            except OSError:
                log_tail = ""
            logger.error(
                "htdemucs_failed",
                extra={
                    "returncode": returncode,
                    "log_tail": log_tail,
                },
            )
            raise RuntimeError("HTDemucs source separation failed")

        stem_dir = output_root / HTDEMUCS_MODEL / input_path.stem
        stems: dict[str, bytes] = {}
        for role in STEM_ROLES:
            stem_path = stem_dir / f"{role}.wav"
            if not stem_path.is_file():
                raise RuntimeError(f"HTDemucs output is missing the {role} stem")
            data = stem_path.read_bytes()
            _validate_stem_bytes(role, data)
            stems[role] = data
        return stems


def stem_metadata(source_version_id: UUID, role: str, job: Job) -> dict:
    """Capability-specific provenance persisted on each independent stem Version.

    The Version already structurally owns parent_version_id, produced_by_job_id,
    immutable storage/hash fields, and lineage. Metadata below records only the
    separator-specific role/model/parameter facts needed to interpret the stem.
    """
    if role not in STEM_ROLES:
        raise ValueError(f"unsupported stem role: {role}")
    return {
        "representation": "source_stem",
        "experimental": True,
        "stem_role": role,
        "separator": {
            "wrapper": "demucs",
            "wrapper_version": DEMUCS_PACKAGE_VERSION,
            "wrapper_license": HTDEMUCS_CODE_LICENSE,
            "model": HTDEMUCS_MODEL,
            "model_signature": HTDEMUCS_MODEL_SIGNATURE,
            "checkpoint": HTDEMUCS_CHECKPOINT,
            "checkpoint_sha256": HTDEMUCS_CHECKPOINT_SHA256,
            "checkpoint_license": HTDEMUCS_CHECKPOINT_LICENSE,
            "upstream": HTDEMUCS_UPSTREAM,
            "weights_source": HTDEMUCS_WEIGHTS,
        },
        "parameters": {
            "device": "cpu",
            "shifts": 0,
        },
        "truth_contract": (
            "This is the model-emitted stem role only. Separation can leak, omit, "
            "or distort sources and does not establish arrangement function, "
            "importance, or instrumentation beyond the emitted role."
        ),
    }


def _acquire_separation_slot(client, job_id: UUID) -> None:
    """Serialize only Demucs execution while remaining responsive to cancellation."""
    while not _SEPARATION_SLOT.acquire(timeout=_SEPARATION_POLL_SECONDS):
        if _job_cancelled(client, job_id):
            raise RuntimeError("HTDemucs source separation was cancelled")


def handle_separate(job: Job, client) -> list[str]:
    """Persist four independently playable HTDemucs stems from Original audio."""
    if len(job.input_version_ids) != 1:
        raise ValueError("source separation requires exactly one source Version")

    source_version_id = job.input_version_ids[0]
    source_version = _lookup_version(client, source_version_id)
    source_kind = _artifact_kind_for_version(client, source_version_id)
    if source_kind != ArtifactKind.audio_original:
        raise ValueError("source separation requires an Original audio Version")

    cleanup_job_ids: list[str] = []
    if job.lifecycle.retry_count > 0:
        cleanup_job_ids.append(str(job.id))
    retry_of = job.provenance.get("retry_of_job_id")
    if retry_of:
        cleanup_job_ids.append(str(retry_of))
    _cleanup_partial_job_outputs(client, cleanup_job_ids)

    work_id = _resolve_work_id(client, source_version_id)
    owner_id = _resolve_owner_id(client, job.workflow_id)
    fmt = _input_format(job.parameters.get("fmt"))

    _update_progress(client, job.id, 0.05, "Preparing layer separation")
    audio_bytes = download_version_bytes(source_version, client)
    if not audio_bytes:
        raise ValueError("Original audio is empty")

    _update_progress(client, job.id, 0.12, "Separating vocals, drums, bass, and other")
    _acquire_separation_slot(client, job.id)
    try:
        stems = run_htdemucs(
            audio_bytes,
            fmt,
            is_cancelled=lambda: _job_cancelled(client, job.id),
        )
    finally:
        _SEPARATION_SLOT.release()
    _update_progress(client, job.id, 0.72, "Saving isolated layers")

    output_ids: list[str] = []
    for index, role in enumerate(STEM_ROLES):
        content = stems[role]
        storage_key = _job_storage_key(job, f"stem-{role}.wav")
        uploaded = False
        try:
            _upload_bytes(client, _STORAGE_BUCKET, storage_key, content, "audio/wav")
            uploaded = True
            version_id = _create_output_version(
                client,
                work_id,
                ArtifactKind.stems,
                storage_key,
                content,
                parent_version_id=source_version.id,
                job=job,
                owner_id=owner_id,
                mime_type="audio/wav",
                label=role.capitalize(),
                metadata=stem_metadata(source_version.id, role, job),
            )
        except Exception:
            # If row persistence for the current stem fails, remove the just-
            # uploaded object. Earlier successful partial Versions remain tied
            # to this failed Job and are removed by the normal retry cleanup;
            # the UI exposes only complete four-role sets owned by one succeeded Job.
            if uploaded:
                try:
                    client.storage.from_(_STORAGE_BUCKET).remove([storage_key])
                except Exception:
                    logger.exception(
                        "source_separation_storage_cleanup_failed",
                        extra={"job_id": str(job.id), "storage_key": storage_key},
                    )
            raise
        output_ids.append(str(version_id))
        _update_progress(
            client,
            job.id,
            0.78 + 0.05 * (index + 1),
            f"Saved {role} layer",
        )

    _update_progress(client, job.id, 0.99, "Layers ready")
    return output_ids


def register_source_separation(worker) -> None:
    worker.register("separate", "1.0", handle_separate)
