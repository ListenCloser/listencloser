"""
Seed helpers for integration tests.

These functions use the supabase-py client with the service-role key to
directly create domain records equivalent to what the HTTP API endpoints
produce.  This lets integration tests seed data without a running FastAPI
server — only a reachable Supabase project is required.

Typical usage in a test::

    import os
    from supabase import create_client
    from fixtures import create_test_project, upload_test_audio, wait_for_job

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    proj = create_test_project(sb, owner_id="abc-123", name="my-fixture")
    result = upload_test_audio(sb, proj["id"], "tests/fixtures/audio/c_major.wav")
    job = wait_for_job(sb, result["job"]["id"], timeout=30)
"""

import mimetypes
import time
from pathlib import Path
from uuid import UUID, uuid4

from supabase import Client


# ---------------------------------------------------------------------------
# create_test_project
# ---------------------------------------------------------------------------


def create_test_project(
    client: Client,
    owner_id: str,
    name: str = "Test Project",
    description: str = "",
) -> dict:
    """Insert a project row and return it as a plain dict.

    The returned dict contains at least ``id``, ``owner_id``, ``name``,
    ``description``, ``created_at``, and ``updated_at``.
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    row = {
        "owner_id": owner_id,
        "name": name,
        "description": description,
        "created_at": now,
        "updated_at": now,
    }
    result = client.table("projects").insert(row).execute()
    if not result.data:
        raise RuntimeError("create_test_project: insert returned no rows")
    return result.data[0]


# ---------------------------------------------------------------------------
# upload_test_audio
# ---------------------------------------------------------------------------


def upload_test_audio(
    client: Client,
    project_id: str,
    audio_path: str,
    owner_id: str | None = None,
    title: str | None = None,
) -> dict:
    """Upload a local audio file and create the full domain chain.

    This mimics ``POST /api/v1/projects/{project_id}/artifacts/upload``:

    1. Creates a ``Work`` row (or uses the project owner as fallback).
    2. Creates an ``Artifact`` row (kind = ``audio_original``).
    3. Uploads the raw file bytes to Supabase Storage under
       ``artifact_data/{project_id}/{artifact_id}/{uuid}.{ext}``.
    4. Creates a ``Version`` row pointing to the storage object.

    Returns a dict with keys ``work``, ``artifact``, ``version``.
    """
    from datetime import UTC, datetime

    audio_file = Path(audio_path)
    if not audio_file.is_file():
        raise FileNotFoundError(f"audio fixture not found: {audio_path}")

    raw = audio_file.read_bytes()
    filename = audio_file.name
    ext = audio_file.suffix.lstrip(".") or "bin"
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    size = len(raw)
    now = datetime.now(UTC).isoformat()

    project_id_uuid = UUID(project_id)

    # Resolve owner_id if not provided
    if owner_id is None:
        proj = (
            client.table("projects")
            .select("owner_id")
            .eq("id", project_id)
            .execute()
        )
        if not proj.data:
            raise ValueError(f"project not found: {project_id}")
        owner_id = proj.data[0]["owner_id"]

    # 1. Work
    work = {
        "project_id": str(project_id_uuid),
        "title": title or audio_file.stem,
        "created_at": now,
        "updated_at": now,
    }
    work_result = client.table("works").insert(work).execute()
    if not work_result.data:
        raise RuntimeError("upload_test_audio: work insert returned no rows")
    work_row = work_result.data[0]

    # 2. Artifact
    artifact = {
        "work_id": work_row["id"],
        "kind": "audio_original",
        "mime_type": mime_type,
        "created_at": now,
    }
    art_result = client.table("artifacts").insert(artifact).execute()
    if not art_result.data:
        raise RuntimeError("upload_test_audio: artifact insert returned no rows")
    art_row = art_result.data[0]

    # 3. Upload to storage
    storage_key = f"{project_id}/{art_row['id']}/{uuid4().hex}.{ext}"
    client.storage.from_("artifact_data").upload(
        storage_key,
        raw,
        {"content-type": mime_type},
    )

    # 4. Version
    version = {
        "artifact_id": art_row["id"],
        "storage_key": storage_key,
        "storage_bucket": "artifact_data",
        "byte_size": size,
        "created_by": owner_id,
        "label": filename,
        "created_at": now,
    }
    ver_result = client.table("artifact_versions").insert(version).execute()
    if not ver_result.data:
        raise RuntimeError("upload_test_audio: version insert returned no rows")
    ver_row = ver_result.data[0]

    return {
        "work": work_row,
        "artifact": art_row,
        "version": ver_row,
    }


# ---------------------------------------------------------------------------
# wait_for_job
# ---------------------------------------------------------------------------


def wait_for_job(
    client: Client,
    job_id: str,
    timeout: int = 60,
    poll_interval: float = 1.0,
) -> dict:
    """Poll the ``jobs`` table until the job reaches a terminal stage.

    Terminal stages are ``succeeded``, ``failed``, and ``cancelled``.

    Returns the final job row dict.

    Raises ``TimeoutError`` if the job does not finish within *timeout*
    seconds.
    """
    deadline = time.monotonic() + timeout
    terminal = {"succeeded", "failed", "cancelled"}

    while time.monotonic() < deadline:
        result = (
            client.table("jobs")
            .select("*")
            .eq("id", job_id)
            .execute()
        )
        if not result.data:
            raise ValueError(f"job not found: {job_id}")

        job = result.data[0]
        stage = job.get("stage", "queued")

        if stage in terminal:
            return job

        time.sleep(poll_interval)

    raise TimeoutError(
        f"job {job_id} did not reach a terminal state within {timeout}s"
    )
