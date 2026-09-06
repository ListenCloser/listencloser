from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest


def _local_db_url() -> str:
    if db_url := os.environ.get("DB_URL"):
        return db_url
    completed = subprocess.run(
        ["supabase", "status", "-o", "env"],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in completed.stdout.splitlines():
        if line.startswith("DB_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("local Supabase status did not provide DB_URL")


def _psql(db_url: str, sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["psql", db_url, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=check,
        capture_output=True,
        text=True,
    )


def _fixture_sql(
    owner_id: str,
    project_id: str,
    work_id: str,
    artifact_id: str,
    source_id: str,
    source_created_at: datetime,
) -> str:
    return f"""
    insert into public.projects (id, owner_id, name)
    values ('{project_id}', '{owner_id}', 'storage rehome fence test');
    insert into public.works (id, project_id, title)
    values ('{work_id}', '{project_id}', 'storage rehome fence work');
    insert into public.artifacts (id, work_id, kind, mime_type)
    values ('{artifact_id}', '{work_id}', 'midi_performance', 'audio/midi');
    insert into public.artifact_versions (
      id, artifact_id, storage_key, storage_bucket, created_at, created_by
    ) values (
      '{source_id}', '{artifact_id}', 'transcriptions/legacy.mid', 'artifacts',
      '{source_created_at.isoformat()}', '{owner_id}'
    );
    """


def _replacement_payload(
    replacement_id: str,
    source_id: str,
    artifact_id: str,
    owner_id: str,
    created_at: datetime,
) -> str:
    return json.dumps(
        {
            "id": replacement_id,
            "artifact_id": artifact_id,
            "parent_version_id": source_id,
            "lineage": [source_id],
            "storage_key": f"{owner_id}/project/artifact/{replacement_id}.mid",
            "storage_bucket": "artifacts",
            "byte_size": 3,
            "sha256": "0" * 64,
            "label": "legacy.mid",
            "metadata": {"storage_locator_rehome": {"method": "storage_locator_rehome_v1"}},
            "created_at": created_at.isoformat(),
            "created_by": owner_id,
            "produced_by_job_id": None,
        }
    )


@pytest.mark.real_stack
def test_storage_rehome_publish_rechecks_latest_at_write_boundary() -> None:
    db_url = _local_db_url()
    owner_id = str(uuid4())
    project_id = str(uuid4())
    work_id = str(uuid4())
    artifact_id = str(uuid4())
    source_id = str(uuid4())
    newer_id = str(uuid4())
    replacement_id = str(uuid4())
    source_created_at = datetime.now(UTC) - timedelta(seconds=10)
    newer_created_at = source_created_at + timedelta(seconds=5)
    replacement_created_at = datetime.now(UTC)

    _psql(
        db_url,
        _fixture_sql(
            owner_id,
            project_id,
            work_id,
            artifact_id,
            source_id,
            source_created_at,
        ),
    )
    try:
        # This is the race the read-only audit cannot see: another Version
        # becomes current after planning but before the recovery write.
        _psql(
            db_url,
            f"""
            insert into public.artifact_versions (
              id, artifact_id, storage_key, storage_bucket, created_at, created_by
            ) values (
              '{newer_id}', '{artifact_id}', 'owner/newer.mid', 'artifacts',
              '{newer_created_at.isoformat()}', '{owner_id}'
            );
            """,
        )
        payload = _replacement_payload(
            replacement_id,
            source_id,
            artifact_id,
            owner_id,
            replacement_created_at,
        )
        attempted = _psql(
            db_url,
            "select id::text from public.publish_storage_rehome_version("
            f"'{source_id}', $payload${payload}$payload$::jsonb);",
            check=False,
        )

        assert attempted.returncode != 0
        assert "source Version is no longer latest" in attempted.stderr
        count = _psql(
            db_url,
            "select count(*) from public.artifact_versions " f"where id = '{replacement_id}';",
        ).stdout.strip()
        assert count == "0"
    finally:
        _psql(db_url, f"delete from public.projects where id = '{project_id}';")


@pytest.mark.real_stack
def test_storage_rehome_publish_is_service_role_only() -> None:
    db_url = _local_db_url()
    signature = "public.publish_storage_rehome_version(uuid,jsonb)"
    row = _psql(
        db_url,
        "select "
        f"has_function_privilege('service_role', '{signature}', 'EXECUTE'), "
        f"has_function_privilege('authenticated', '{signature}', 'EXECUTE'), "
        f"has_function_privilege('anon', '{signature}', 'EXECUTE');",
    ).stdout.strip()
    assert row == "t|f|f"
