from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
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


def _psql(db_url: str, sql: str) -> list[str]:
    completed = subprocess.run(
        ["psql", db_url, "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


@pytest.mark.real_stack
def test_atomic_job_claim_skips_locked_queue_head() -> None:
    db_url = _local_db_url()
    suffix = uuid4().hex
    owner_id = str(uuid4())
    project_id = str(uuid4())
    workflow_id = str(uuid4())
    workers = [f"claim-test-{suffix}-{index}" for index in range(4)]

    _psql(
        db_url,
        f"""
        insert into public.projects (id, owner_id, name)
        values ('{project_id}', '{owner_id}', 'atomic claim test');
        insert into public.workflows (id, project_id, kind)
        values ('{workflow_id}', '{project_id}', 'understand');
        insert into public.jobs (workflow_id, capability_name, capability_version)
        select '{workflow_id}', 'test', '1.0' from generate_series(1, 4);
        """,
    )
    try:

        def claim(worker_id: str) -> str | None:
            rows = _psql(
                db_url,
                "select id::text from public.claim_next_job(" f"'{worker_id}', 30.0);",
            )
            return rows[0] if rows else None

        with ThreadPoolExecutor(max_workers=4) as executor:
            claimed = list(executor.map(claim, workers))

        assert all(claimed)
        assert len(set(claimed)) == 4
        assert claim("after-drain") is None

        rows = _psql(
            db_url,
            f"select count(*) from public.jobs where workflow_id = '{workflow_id}' "
            "and stage = 'claimed' and worker_id is not null and lease_expires_at > now();",
        )
        assert rows == ["4"]
    finally:
        _psql(db_url, f"delete from public.projects where id = '{project_id}';")


@pytest.mark.real_stack
def test_atomic_job_claim_execute_privilege_is_service_role_only() -> None:
    db_url = _local_db_url()
    signature = "public.claim_next_job(text,double precision)"
    rows = _psql(
        db_url,
        "select "
        f"has_function_privilege('service_role', '{signature}', 'EXECUTE'), "
        f"has_function_privilege('authenticated', '{signature}', 'EXECUTE'), "
        f"has_function_privilege('anon', '{signature}', 'EXECUTE');",
    )
    assert rows == ["t|f|f"]
