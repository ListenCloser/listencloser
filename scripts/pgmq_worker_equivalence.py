#!/usr/bin/env python3
"""Exercise the remaining PGMQ worker-equivalence gates on local Postgres.

Evaluation only. The prototype creates uniquely named scratch tables and a
scratch PGMQ queue, refuses non-local databases by default, and never changes
the production ``jobs`` table or worker routing.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from uuid import uuid4

from scripts.queue_transport_bakeoff import (
    _drop_pgmq_queue,
    _run_psql,
    _sql_literal,
    assert_safe_database,
)


@dataclass(frozen=True)
class PrototypeNames:
    queue: str
    jobs: str
    outputs: str


def _names() -> PrototypeNames:
    suffix = uuid4().hex[:10]
    return PrototypeNames(
        queue=f"listencloser_pgmq_worker_{suffix}",
        jobs=f"pgmq_worker_jobs_{suffix}",
        outputs=f"pgmq_worker_outputs_{suffix}",
    )


def _create_objects(db_url: str, names: PrototypeNames) -> None:
    queue = _sql_literal(names.queue)
    _run_psql(db_url, "create extension if not exists pgmq;")
    _run_psql(db_url, f"select pgmq.create({queue});")
    _run_psql(
        db_url,
        f"""
        create table public.{names.jobs} (
          id uuid primary key,
          stage text not null default 'queued',
          attempt_token uuid,
          retry_count integer not null default 0,
          progress double precision not null default 0,
          status_message text not null default '',
          created_at timestamptz not null default clock_timestamp()
        );

        create table public.{names.outputs} (
          id bigint generated always as identity primary key,
          job_id uuid not null unique,
          attempt_token uuid not null,
          payload text not null,
          created_at timestamptz not null default clock_timestamp()
        );
        """,
    )


def _drop_objects(db_url: str, names: PrototypeNames) -> None:
    _run_psql(db_url, f"drop table if exists public.{names.outputs};")
    _run_psql(db_url, f"drop table if exists public.{names.jobs};")
    _drop_pgmq_queue(db_url, names.queue)


def _enqueue_job(db_url: str, names: PrototypeNames) -> str:
    job_id = str(uuid4())
    queue = _sql_literal(names.queue)
    _run_psql(
        db_url,
        (
            "begin; "
            f"insert into public.{names.jobs} (id, stage) values ('{job_id}'::uuid, 'queued'); "
            "select pgmq.send("
            f"queue_name => {queue}, "
            f"msg => jsonb_build_object('job_id', '{job_id}')); "
            "commit;"
        ),
    )
    return job_id


def _read_delivery(
    db_url: str,
    names: PrototypeNames,
    *,
    visibility_timeout: int,
) -> dict[str, object] | None:
    queue = _sql_literal(names.queue)
    rows = _run_psql(
        db_url,
        (
            "select msg_id, read_ct, "
            "extract(epoch from (clock_timestamp() - enqueued_at))::double precision, "
            "message::text "
            "from pgmq.read("
            f"queue_name => {queue}, vt => {visibility_timeout}, qty => 1);"
        ),
    )
    if not rows:
        return None
    msg_id, read_ct, queue_wait_sec, payload = rows[0].split("|", 3)
    return {
        "msg_id": int(msg_id),
        "read_ct": int(read_ct),
        "queue_wait_sec": max(0.0, float(queue_wait_sec)),
        "message": json.loads(payload),
    }


def _set_visibility(db_url: str, names: PrototypeNames, message_id: int, seconds: int) -> bool:
    queue = _sql_literal(names.queue)
    rows = _run_psql(
        db_url,
        f"select msg_id from pgmq.set_vt({queue}, {message_id}, {seconds});",
    )
    return rows == [str(message_id)]


def _archive(db_url: str, names: PrototypeNames, message_id: int) -> bool:
    queue = _sql_literal(names.queue)
    rows = _run_psql(
        db_url,
        f"select pgmq.archive(queue_name => {queue}, msg_id => {message_id});",
    )
    return rows == ["t"]


def _queue_metrics(db_url: str, names: PrototypeNames) -> dict[str, int]:
    queue = _sql_literal(names.queue)
    rows = _run_psql(
        db_url,
        (
            "select queue_length, coalesce(oldest_msg_age_sec, 0), total_messages "
            f"from pgmq.metrics({queue});"
        ),
    )
    queue_length, oldest_age, total_messages = (int(value) for value in rows[0].split("|"))
    return {
        "queue_length": queue_length,
        "oldest_msg_age_sec": oldest_age,
        "total_messages": total_messages,
    }


def _claim_delivery(
    db_url: str,
    names: PrototypeNames,
    *,
    visibility_timeout: int,
) -> dict[str, object] | None:
    delivery = _read_delivery(db_url, names, visibility_timeout=visibility_timeout)
    if delivery is None:
        return None

    job_id = str(dict(delivery["message"])["job_id"])
    attempt_token = str(uuid4())
    rows = _run_psql(
        db_url,
        (
            f"update public.{names.jobs} "
            "set stage = 'running', "
            f"attempt_token = '{attempt_token}'::uuid, "
            f"retry_count = greatest(retry_count, {int(delivery['read_ct']) - 1}), "
            f"status_message = 'attempt {int(delivery['read_ct'])}' "
            f"where id = '{job_id}'::uuid and stage in ('queued', 'running') "
            "returning id;"
        ),
    )
    if rows != [job_id]:
        return None

    return {
        **delivery,
        "job_id": job_id,
        "attempt_token": attempt_token,
    }


def _publish_if_current(
    db_url: str,
    names: PrototypeNames,
    *,
    job_id: str,
    attempt_token: str,
    payload: str,
) -> bool:
    payload_sql = _sql_literal(payload)
    rows = _run_psql(
        db_url,
        f"""
        with owned as (
          select id
          from public.{names.jobs}
          where id = '{job_id}'::uuid
            and stage = 'running'
            and attempt_token = '{attempt_token}'::uuid
        ), inserted as (
          insert into public.{names.outputs} (job_id, attempt_token, payload)
          select id, '{attempt_token}'::uuid, {payload_sql}
          from owned
          on conflict (job_id) do nothing
          returning job_id
        )
        update public.{names.jobs}
        set stage = 'succeeded',
            progress = 1.0,
            status_message = 'completed'
        where id in (select job_id from inserted)
          and attempt_token = '{attempt_token}'::uuid
        returning id;
        """,
    )
    return rows == [job_id]


def verify_visibility_extension(db_url: str, names: PrototypeNames) -> dict[str, object]:
    job_id = _enqueue_job(db_url, names)
    first = _read_delivery(db_url, names, visibility_timeout=1)
    if first is None:
        raise RuntimeError("PGMQ did not return the visibility-extension probe message")

    message_id = int(first["msg_id"])
    extended = _set_visibility(db_url, names, message_id, 30)
    hidden_after_extension = _read_delivery(db_url, names, visibility_timeout=1) is None
    archived = _archive(db_url, names, message_id)
    return {
        "job_id": job_id,
        "set_vt_returned_message": extended,
        "message_hidden_after_extension": hidden_after_extension,
        "archived": archived,
    }


def verify_takeover_fencing(db_url: str, names: PrototypeNames) -> dict[str, object]:
    job_id = _enqueue_job(db_url, names)
    metrics_before = _queue_metrics(db_url, names)

    attempt_a = _claim_delivery(db_url, names, visibility_timeout=1)
    if attempt_a is None:
        raise RuntimeError("worker A could not claim the PGMQ message")

    time.sleep(1.2)
    attempt_b = _claim_delivery(db_url, names, visibility_timeout=30)
    if attempt_b is None:
        raise RuntimeError("worker B did not receive the message after visibility expiry")

    stale_publish_succeeded = _publish_if_current(
        db_url,
        names,
        job_id=job_id,
        attempt_token=str(attempt_a["attempt_token"]),
        payload="stale-attempt-output",
    )
    current_publish_succeeded = _publish_if_current(
        db_url,
        names,
        job_id=job_id,
        attempt_token=str(attempt_b["attempt_token"]),
        payload="current-attempt-output",
    )
    archived = _archive(db_url, names, int(attempt_b["msg_id"]))

    output_rows = _run_psql(
        db_url,
        (
            f"select attempt_token::text, payload from public.{names.outputs} "
            f"where job_id = '{job_id}'::uuid;"
        ),
    )
    job_rows = _run_psql(
        db_url,
        (
            f"select stage, retry_count, attempt_token::text from public.{names.jobs} "
            f"where id = '{job_id}'::uuid;"
        ),
    )
    archive_rows = _run_psql(
        db_url,
        f"select count(*) from pgmq.a_{names.queue} where msg_id = {int(attempt_b['msg_id'])};",
    )
    metrics_after = _queue_metrics(db_url, names)

    output_token, output_payload = output_rows[0].split("|", 1)
    stage, retry_count, current_token = job_rows[0].split("|", 2)
    return {
        "same_message_redelivered": attempt_a["msg_id"] == attempt_b["msg_id"],
        "read_count_advanced": int(attempt_a["read_ct"]) == 1 and int(attempt_b["read_ct"]) == 2,
        "attempt_token_changed": attempt_a["attempt_token"] != attempt_b["attempt_token"],
        "stale_publish_rejected": not stale_publish_succeeded,
        "current_publish_succeeded": current_publish_succeeded,
        "authoritative_output_is_current_attempt": (
            output_token == str(attempt_b["attempt_token"])
            and output_payload == "current-attempt-output"
        ),
        "job_finished_under_current_attempt": (
            stage == "succeeded"
            and int(retry_count) == 1
            and current_token == str(attempt_b["attempt_token"])
        ),
        "archived": archived and archive_rows == ["1"],
        "first_queue_wait_sec": attempt_a["queue_wait_sec"],
        "second_queue_wait_sec": attempt_b["queue_wait_sec"],
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
    }


def run_prototype(db_url: str, *, allow_remote: bool = False) -> dict[str, object]:
    assert_safe_database(db_url, allow_remote=allow_remote)
    names = _names()
    _create_objects(db_url, names)
    try:
        visibility_extension = verify_visibility_extension(db_url, names)
        takeover_fencing = verify_takeover_fencing(db_url, names)
    finally:
        _drop_objects(db_url, names)

    return {
        "visibility_extension": visibility_extension,
        "takeover_fencing": takeover_fencing,
        "interpretation": {
            "delivery": "PGMQ owns visibility/redelivery/archive",
            "attempt_identity": "fresh token per successful delivery claim",
            "publish_boundary": "domain persistence commits only for the current attempt token",
            "production_enabled": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_url")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()

    report = run_prototype(args.db_url, allow_remote=args.allow_remote)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
