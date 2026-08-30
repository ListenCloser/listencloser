#!/usr/bin/env python3
"""Prove whether a Postgres trigger can atomically signal pgmq job delivery.

Evaluation only. The prototype creates uniquely named scratch objects and refuses
non-local databases by default. It never modifies listencloser's production jobs
table or installs anything in a remote project unless an operator explicitly
passes ``--allow-remote`` for a disposable database.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from uuid import uuid4

from scripts.queue_transport_bakeoff import (
    _delete_pgmq_message,
    _drop_pgmq_queue,
    _read_pgmq_one,
    _run_psql,
    _sql_literal,
    assert_safe_database,
)


@dataclass(frozen=True)
class PrototypeNames:
    table: str
    function: str
    trigger: str
    queue: str


def _names() -> PrototypeNames:
    suffix = uuid4().hex[:10]
    return PrototypeNames(
        table=f"queue_signal_jobs_{suffix}",
        function=f"queue_signal_fn_{suffix}",
        trigger=f"queue_signal_trg_{suffix}",
        queue=f"listencloser_signal_{suffix}",
    )


def _create_objects(db_url: str, names: PrototypeNames) -> None:
    queue = _sql_literal(names.queue)
    _run_psql(db_url, "create extension if not exists pgmq;")
    _run_psql(db_url, f"select pgmq.create({queue});")
    _run_psql(
        db_url,
        f"""
        create table public.{names.table} (
          id uuid primary key,
          stage text not null
        );

        create function public.{names.function}()
        returns trigger
        language plpgsql
        security invoker
        set search_path = ''
        as $$
        begin
          if new.stage <> 'queued' then
            return new;
          end if;

          if tg_op = 'INSERT'
             or (tg_op = 'UPDATE' and old.stage is distinct from new.stage) then
            perform pgmq.send(
              queue_name => {queue},
              msg => jsonb_build_object('job_id', new.id::text)
            );
          end if;
          return new;
        end;
        $$;

        revoke all on function public.{names.function}() from public;
        grant execute on function public.{names.function}() to service_role;

        create trigger {names.trigger}
          after insert or update of stage on public.{names.table}
          for each row execute function public.{names.function}();
        """,
    )


def _drop_objects(db_url: str, names: PrototypeNames) -> None:
    _run_psql(db_url, f"drop table if exists public.{names.table};")
    _run_psql(db_url, f"drop function if exists public.{names.function}();")
    _drop_pgmq_queue(db_url, names.queue)


def _read_payload(db_url: str, queue_name: str, visibility_timeout: int = 30) -> dict | None:
    queue = _sql_literal(queue_name)
    rows = _run_psql(
        db_url,
        (
            "select msg_id, message::text from pgmq.read("
            f"queue_name => {queue}, vt => {visibility_timeout}, qty => 1);"
        ),
    )
    if not rows:
        return None
    msg_id_text, payload_text = rows[0].split("|", 1)
    return {"msg_id": int(msg_id_text), "message": json.loads(payload_text)}


def _drain_one(db_url: str, queue_name: str) -> dict | None:
    payload = _read_payload(db_url, queue_name)
    if payload is not None:
        _delete_pgmq_message(db_url, queue_name, int(payload["msg_id"]))
    return payload


def verify_insert_signal(db_url: str, names: PrototypeNames) -> dict[str, object]:
    job_id = str(uuid4())
    _run_psql(
        db_url,
        f"insert into public.{names.table} (id, stage) values ('{job_id}'::uuid, 'queued');",
    )
    message = _drain_one(db_url, names.queue)
    return {
        "job_id": job_id,
        "message_received": message is not None,
        "message_job_id_matches": bool(message and message["message"].get("job_id") == job_id),
    }


def verify_nonqueued_insert_silent(db_url: str, names: PrototypeNames) -> bool:
    job_id = str(uuid4())
    _run_psql(
        db_url,
        f"insert into public.{names.table} (id, stage) values ('{job_id}'::uuid, 'running');",
    )
    return _read_pgmq_one(db_url, names.queue, visibility_timeout=1) is None


def verify_requeue_signal(db_url: str, names: PrototypeNames) -> dict[str, object]:
    job_id = str(uuid4())
    _run_psql(
        db_url,
        f"insert into public.{names.table} (id, stage) values ('{job_id}'::uuid, 'running');",
    )
    _run_psql(
        db_url,
        f"update public.{names.table} set stage = 'queued' where id = '{job_id}'::uuid;",
    )
    message = _drain_one(db_url, names.queue)

    _run_psql(
        db_url,
        f"update public.{names.table} set stage = 'queued' where id = '{job_id}'::uuid;",
    )
    duplicate = _read_pgmq_one(db_url, names.queue, visibility_timeout=1)

    return {
        "job_id": job_id,
        "requeue_message_received": message is not None,
        "requeue_message_job_id_matches": bool(
            message and message["message"].get("job_id") == job_id
        ),
        "same_stage_update_silent": duplicate is None,
    }


def verify_insert_rollback_is_atomic(db_url: str, names: PrototypeNames) -> dict[str, object]:
    job_id = str(uuid4())
    _run_psql(
        db_url,
        (
            "begin; "
            f"insert into public.{names.table} (id, stage) values ('{job_id}'::uuid, 'queued'); "
            "rollback;"
        ),
    )
    rows = _run_psql(
        db_url,
        f"select count(*) from public.{names.table} where id = '{job_id}'::uuid;",
    )
    message = _read_pgmq_one(db_url, names.queue, visibility_timeout=1)
    return {
        "job_row_rolled_back": rows == ["0"],
        "queue_signal_rolled_back": message is None,
    }


def verify_requeue_rollback_is_atomic(db_url: str, names: PrototypeNames) -> dict[str, object]:
    job_id = str(uuid4())
    _run_psql(
        db_url,
        f"insert into public.{names.table} (id, stage) values ('{job_id}'::uuid, 'running');",
    )
    _run_psql(
        db_url,
        (
            "begin; "
            f"update public.{names.table} set stage = 'queued' where id = '{job_id}'::uuid; "
            "rollback;"
        ),
    )
    rows = _run_psql(
        db_url,
        f"select stage from public.{names.table} where id = '{job_id}'::uuid;",
    )
    message = _read_pgmq_one(db_url, names.queue, visibility_timeout=1)
    return {
        "job_stage_rolled_back": rows == ["running"],
        "queue_signal_rolled_back": message is None,
    }


def run_prototype(db_url: str, *, allow_remote: bool = False) -> dict[str, object]:
    assert_safe_database(db_url, allow_remote=allow_remote)
    names = _names()
    _create_objects(db_url, names)
    try:
        insert_signal = verify_insert_signal(db_url, names)
        nonqueued_silent = verify_nonqueued_insert_silent(db_url, names)
        requeue_signal = verify_requeue_signal(db_url, names)
        insert_rollback = verify_insert_rollback_is_atomic(db_url, names)
        requeue_rollback = verify_requeue_rollback_is_atomic(db_url, names)
    finally:
        _drop_objects(db_url, names)

    return {
        "insert_signal": insert_signal,
        "nonqueued_insert_silent": nonqueued_silent,
        "requeue_signal": requeue_signal,
        "insert_rollback": insert_rollback,
        "requeue_rollback": requeue_rollback,
        "interpretation": {
            "pattern": "same-database transactional signal",
            "authoritative_state": "public.jobs",
            "delivery_payload": "{job_id}",
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
