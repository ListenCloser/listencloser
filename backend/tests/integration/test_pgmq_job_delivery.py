from __future__ import annotations

import json
import os
import subprocess
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


def _fixture_ids() -> tuple[str, str, str, str]:
    return (
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
    )


def _insert_fixture(db_url: str, owner_id: str, project_id: str, workflow_id: str) -> None:
    _psql(
        db_url,
        f"""
        insert into public.projects (id, owner_id, name)
        values ('{project_id}', '{owner_id}', 'pgmq delivery test');
        insert into public.workflows (id, project_id, kind)
        values ('{workflow_id}', '{project_id}', 'understand');
        """,
    )


def _cleanup_job_message(db_url: str, job_id: str) -> None:
    _psql(
        db_url,
        f"""
        select pgmq.archive('job_delivery', msg_id)
          from pgmq.q_job_delivery
         where message ->> 'job_id' = '{job_id}';
        """,
    )


def _receive(
    db_url: str,
    worker_id: str,
    visibility: int = 5,
    in_flight: tuple[str, ...] = (),
) -> dict | None:
    if in_flight:
        ids = ",".join(f"'{job_id}'::uuid" for job_id in in_flight)
        in_flight_sql = f"array[{ids}]"
    else:
        in_flight_sql = "'{}'::uuid[]"
    rows = _psql(
        db_url,
        "select public.receive_job_delivery("
        f"'{worker_id}', {visibility}, {in_flight_sql})::text;",
    )
    return json.loads(rows[0]) if rows else None


@pytest.mark.real_stack
def test_job_insert_and_pgmq_signal_share_one_transaction() -> None:
    db_url = _local_db_url()
    owner_id, project_id, workflow_id, job_id = _fixture_ids()
    _insert_fixture(db_url, owner_id, project_id, workflow_id)
    try:
        _psql(
            db_url,
            f"""
            begin;
            insert into public.jobs (
              id, workflow_id, capability_name, capability_version
            ) values (
              '{job_id}', '{workflow_id}', 'pgmq_test', '1.0'
            );
            rollback;
            """,
        )
        assert _psql(
            db_url,
            "select count(*) from pgmq.q_job_delivery "
            f"where message ->> 'job_id' = '{job_id}';",
        ) == ["0"]

        _psql(
            db_url,
            f"""
            insert into public.jobs (
              id, workflow_id, capability_name, capability_version
            ) values (
              '{job_id}', '{workflow_id}', 'pgmq_test', '1.0'
            );
            """,
        )
        assert _psql(
            db_url,
            "select count(*) from pgmq.q_job_delivery "
            f"where message ->> 'job_id' = '{job_id}';",
        ) == ["1"]
    finally:
        _cleanup_job_message(db_url, job_id)
        _psql(db_url, f"delete from public.projects where id = '{project_id}';")


@pytest.mark.real_stack
def test_visibility_expiry_allows_takeover_but_stale_attempt_cannot_ack() -> None:
    db_url = _local_db_url()
    owner_id, project_id, workflow_id, job_id = _fixture_ids()
    _insert_fixture(db_url, owner_id, project_id, workflow_id)
    _psql(
        db_url,
        f"""
        insert into public.jobs (id, workflow_id, capability_name, capability_version)
        values ('{job_id}', '{workflow_id}', 'pgmq_test', '1.0');
        """,
    )
    try:
        attempt_a = _receive(db_url, "worker-a")
        assert attempt_a is not None
        assert attempt_a["id"] == job_id
        assert attempt_a["stage"] == "claimed"
        assert attempt_a["worker_id"] == "worker-a"
        assert attempt_a["lease_expires_at"] is None
        token_a = attempt_a["execution_token"]
        msg_id = int(attempt_a["_queue_msg_id"])

        # Deterministically model a handler whose process stops extending VT.
        _psql(db_url, f"select pgmq.set_vt('job_delivery', {msg_id}, 0);")

        # The same process must not overwrite its own live execution generation.
        assert _receive(db_url, "worker-a", in_flight=(job_id,)) is None
        assert _psql(
            db_url,
            f"select execution_token::text from public.jobs where id = '{job_id}';",
        ) == [token_a]

        # Once visible again, a different worker can take over the same message.
        _psql(db_url, f"select pgmq.set_vt('job_delivery', {msg_id}, 0);")
        attempt_b = _receive(db_url, "worker-b")
        assert attempt_b is not None
        assert attempt_b["id"] == job_id
        assert int(attempt_b["_queue_msg_id"]) == msg_id
        assert int(attempt_b["_queue_read_ct"]) >= 2
        token_b = attempt_b["execution_token"]
        assert token_b != token_a

        # A finishes late after B owns the Job. Its transport acknowledgement is
        # fenced by the exact same execution token as product-visible writes.
        assert _psql(
            db_url,
            "select public.finish_job_delivery("
            f"'{job_id}', '{token_a}', {msg_id}, 0);",
        ) == ["stale"]
        assert _psql(
            db_url,
            f"select count(*) from pgmq.q_job_delivery where msg_id = {msg_id};",
        ) == ["1"]

        _psql(
            db_url,
            f"""
            update public.jobs
               set stage = 'running'
             where id = '{job_id}' and execution_token = '{token_b}';
            update public.jobs
               set stage = 'succeeded', progress = 1, completed_at = clock_timestamp()
             where id = '{job_id}' and execution_token = '{token_b}';
            """,
        )
        assert _psql(
            db_url,
            "select public.finish_job_delivery("
            f"'{job_id}', '{token_b}', {msg_id}, 0);",
        ) == ["archived"]
        assert _psql(
            db_url,
            f"select count(*) from pgmq.q_job_delivery where msg_id = {msg_id};",
        ) == ["0"]
    finally:
        _cleanup_job_message(db_url, job_id)
        _psql(db_url, f"delete from public.projects where id = '{project_id}';")


@pytest.mark.real_stack
def test_retry_reuses_same_delivery_and_cancellation_archives_it() -> None:
    db_url = _local_db_url()
    owner_id, project_id, workflow_id, job_id = _fixture_ids()
    _insert_fixture(db_url, owner_id, project_id, workflow_id)
    _psql(
        db_url,
        f"""
        insert into public.jobs (id, workflow_id, capability_name, capability_version)
        values ('{job_id}', '{workflow_id}', 'pgmq_test', '1.0');
        """,
    )
    try:
        attempt_a = _receive(db_url, "worker-a")
        assert attempt_a is not None
        token_a = attempt_a["execution_token"]
        msg_id = int(attempt_a["_queue_msg_id"])

        _psql(
            db_url,
            f"""
            update public.jobs
               set stage = 'running'
             where id = '{job_id}' and execution_token = '{token_a}';
            update public.jobs
               set stage = 'queued', retry_count = 1, worker_id = null
             where id = '{job_id}' and execution_token = '{token_a}';
            """,
        )
        assert _psql(
            db_url,
            "select public.finish_job_delivery("
            f"'{job_id}', '{token_a}', {msg_id}, 0);",
        ) == ["released"]
        assert _psql(
            db_url,
            "select count(*) from pgmq.q_job_delivery "
            f"where message ->> 'job_id' = '{job_id}';",
        ) == ["1"]

        attempt_b = _receive(db_url, "worker-b")
        assert attempt_b is not None
        assert int(attempt_b["_queue_msg_id"]) == msg_id
        assert int(attempt_b["retry_count"]) == 1
        token_b = attempt_b["execution_token"]

        _psql(
            db_url,
            f"""
            update public.jobs
               set stage = 'cancelled', completed_at = clock_timestamp()
             where id = '{job_id}' and execution_token = '{token_b}';
            """,
        )
        assert _psql(
            db_url,
            "select public.finish_job_delivery("
            f"'{job_id}', '{token_b}', {msg_id}, 0);",
        ) == ["archived"]
        assert _psql(
            db_url,
            f"select count(*) from pgmq.q_job_delivery where msg_id = {msg_id};",
        ) == ["0"]
    finally:
        _cleanup_job_message(db_url, job_id)
        _psql(db_url, f"delete from public.projects where id = '{project_id}';")


@pytest.mark.real_stack
def test_pgmq_worker_rpcs_are_service_role_only() -> None:
    db_url = _local_db_url()
    signatures = (
        "public.receive_job_delivery(text,integer,uuid[])",
        "public.extend_job_delivery(uuid,uuid,bigint,integer)",
        "public.finish_job_delivery(uuid,uuid,bigint,integer)",
    )
    for signature in signatures:
        rows = _psql(
            db_url,
            "select "
            f"has_function_privilege('service_role', '{signature}', 'EXECUTE'), "
            f"has_function_privilege('authenticated', '{signature}', 'EXECUTE'), "
            f"has_function_privilege('anon', '{signature}', 'EXECUTE');",
        )
        assert rows == ["t|f|f"]
