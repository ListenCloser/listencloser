#!/usr/bin/env python3
"""Compare hello-ai's current queue claim pattern with pgmq on local Postgres.

This is an evaluation tool, not a production queue implementation. By default it
refuses non-local database URLs so a benchmark cannot accidentally create queues
or scratch tables in production. Pass --allow-remote only for an explicitly
disposable remote database.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from threading import Barrier
from urllib.parse import urlparse
from uuid import uuid4


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class ClaimStats:
    claimed: int
    calls: int
    lost_claims: int
    duplicate_claims: int

    @property
    def calls_per_claim(self) -> float:
        return self.calls / self.claimed if self.claimed else 0.0

    def to_dict(self) -> dict[str, int | float]:
        return {**asdict(self), "calls_per_claim": round(self.calls_per_claim, 4)}


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_psql(db_url: str, sql: str) -> list[str]:
    completed = subprocess.run(
        [
            "psql",
            db_url,
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-F",
            "|",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def assert_safe_database(db_url: str, *, allow_remote: bool = False) -> None:
    host = urlparse(db_url).hostname
    if allow_remote or host in _LOCAL_HOSTS:
        return
    raise ValueError(
        "queue bakeoff refuses non-local databases by default; use --allow-remote "
        "only with an explicitly disposable database"
    )


def _create_pgmq_queue(db_url: str, queue_name: str) -> None:
    queue = _sql_literal(queue_name)
    _run_psql(db_url, "create extension if not exists pgmq;")
    _run_psql(db_url, f"select pgmq.create({queue});")


def _drop_pgmq_queue(db_url: str, queue_name: str) -> None:
    queue = _sql_literal(queue_name)
    _run_psql(db_url, f"select pgmq.drop_queue({queue});")


def _send_pgmq_messages(db_url: str, queue_name: str, count: int) -> None:
    queue = _sql_literal(queue_name)
    _run_psql(
        db_url,
        (
            "select pgmq.send("
            f"queue_name => {queue}, "
            "msg => jsonb_build_object('sequence', g)) "
            f"from generate_series(1, {count}) as g;"
        ),
    )


def _read_pgmq_one(db_url: str, queue_name: str, visibility_timeout: int = 30) -> int | None:
    queue = _sql_literal(queue_name)
    rows = _run_psql(
        db_url,
        (
            "select msg_id from pgmq.read("
            f"queue_name => {queue}, vt => {visibility_timeout}, qty => 1);"
        ),
    )
    return int(rows[0]) if rows else None


def _delete_pgmq_message(db_url: str, queue_name: str, message_id: int) -> None:
    queue = _sql_literal(queue_name)
    _run_psql(
        db_url,
        f"select pgmq.delete(queue_name => {queue}, msg_id => {message_id});",
    )


def benchmark_pgmq_claims(
    db_url: str,
    queue_name: str,
    *,
    message_count: int,
    workers: int,
) -> ClaimStats:
    _send_pgmq_messages(db_url, queue_name, message_count)
    claimed_ids: list[int] = []
    calls = 0
    lost_claims = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while len(claimed_ids) < message_count:
            remaining = message_count - len(claimed_ids)
            batch_workers = min(workers, remaining)
            futures = [
                executor.submit(_read_pgmq_one, db_url, queue_name)
                for _ in range(batch_workers)
            ]
            batch = [future.result() for future in futures]
            calls += batch_workers
            lost_claims += sum(message_id is None for message_id in batch)
            for message_id in batch:
                if message_id is None:
                    continue
                claimed_ids.append(message_id)
                _delete_pgmq_message(db_url, queue_name, message_id)

    return ClaimStats(
        claimed=len(claimed_ids),
        calls=calls,
        lost_claims=lost_claims,
        duplicate_claims=len(claimed_ids) - len(set(claimed_ids)),
    )


def _create_current_pattern_table(db_url: str, table_name: str, message_count: int) -> None:
    _run_psql(
        db_url,
        (
            f"create table public.{table_name} ("
            "id bigint generated always as identity primary key, "
            "stage text not null default 'queued', "
            "worker_id text, "
            "created_at timestamptz not null default clock_timestamp()); "
            f"insert into public.{table_name} (stage) "
            f"select 'queued' from generate_series(1, {message_count});"
        ),
    )


def _drop_current_pattern_table(db_url: str, table_name: str) -> None:
    _run_psql(db_url, f"drop table if exists public.{table_name};")


def _current_pattern_attempt(
    db_url: str,
    table_name: str,
    worker_id: str,
    barrier: Barrier,
) -> tuple[int | None, bool]:
    selected = _run_psql(
        db_url,
        (
            f"select id from public.{table_name} "
            "where stage = 'queued' order by created_at, id limit 1;"
        ),
    )
    job_id = int(selected[0]) if selected else None
    barrier.wait(timeout=10)
    if job_id is None:
        return None, False

    worker = _sql_literal(worker_id)
    updated = _run_psql(
        db_url,
        (
            f"update public.{table_name} set stage = 'claimed', worker_id = {worker} "
            f"where id = {job_id} and stage = 'queued' returning id;"
        ),
    )
    return job_id, bool(updated)


def benchmark_current_claim_pattern(
    db_url: str,
    table_name: str,
    *,
    message_count: int,
    workers: int,
) -> ClaimStats:
    claimed_ids: list[int] = []
    calls = 0
    lost_claims = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while len(claimed_ids) < message_count:
            barrier = Barrier(workers)
            futures = [
                executor.submit(
                    _current_pattern_attempt,
                    db_url,
                    table_name,
                    f"worker-{index}",
                    barrier,
                )
                for index in range(workers)
            ]
            batch = [future.result() for future in futures]
            calls += workers * 2  # select + conditional update per worker
            for job_id, won in batch:
                if won and job_id is not None:
                    claimed_ids.append(job_id)
                elif job_id is not None:
                    lost_claims += 1

    return ClaimStats(
        claimed=len(claimed_ids),
        calls=calls,
        lost_claims=lost_claims,
        duplicate_claims=len(claimed_ids) - len(set(claimed_ids)),
    )


def verify_visibility_replay(db_url: str, queue_name: str) -> dict[str, int | bool]:
    queue = _sql_literal(queue_name)
    sent = _run_psql(
        db_url,
        f"select pgmq.send(queue_name => {queue}, msg => '{{\"kind\":\"replay\"}}'::jsonb);",
    )
    message_id = int(sent[0])

    first = _run_psql(
        db_url,
        f"select msg_id, read_ct from pgmq.read({queue}, 1, 1);",
    )
    immediate = _run_psql(
        db_url,
        f"select msg_id, read_ct from pgmq.read({queue}, 1, 1);",
    )
    time.sleep(1.2)
    replay = _run_psql(
        db_url,
        f"select msg_id, read_ct from pgmq.read({queue}, 30, 1);",
    )

    first_id, first_read_count = (int(value) for value in first[0].split("|"))
    replay_id, replay_read_count = (int(value) for value in replay[0].split("|"))
    _delete_pgmq_message(db_url, queue_name, message_id)

    return {
        "message_id": message_id,
        "first_read_count": first_read_count,
        "immediate_second_read_hidden": not immediate,
        "replay_message_matches": replay_id == first_id == message_id,
        "replay_read_count": replay_read_count,
    }


def run_bakeoff(
    db_url: str,
    *,
    message_count: int = 12,
    workers: int = 4,
    allow_remote: bool = False,
) -> dict[str, object]:
    if message_count < workers or workers < 2:
        raise ValueError("message_count must be >= workers and workers must be >= 2")
    assert_safe_database(db_url, allow_remote=allow_remote)

    suffix = uuid4().hex[:10]
    queue_name = f"hello_ai_bakeoff_{suffix}"
    table_name = f"queue_bakeoff_jobs_{suffix}"

    _create_pgmq_queue(db_url, queue_name)
    _create_current_pattern_table(db_url, table_name, message_count)
    try:
        current = benchmark_current_claim_pattern(
            db_url,
            table_name,
            message_count=message_count,
            workers=workers,
        )
        pgmq = benchmark_pgmq_claims(
            db_url,
            queue_name,
            message_count=message_count,
            workers=workers,
        )
        replay = verify_visibility_replay(db_url, queue_name)
    finally:
        _drop_current_pattern_table(db_url, table_name)
        _drop_pgmq_queue(db_url, queue_name)

    return {
        "message_count": message_count,
        "workers": workers,
        "current_select_then_claim": current.to_dict(),
        "pgmq": pgmq.to_dict(),
        "visibility_replay": replay,
        "interpretation": {
            "delivery_semantics": "at-least-once across visibility-timeout expiry",
            "domain_state": "public.jobs remains authoritative in any production design",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_url", help="Postgres connection URL; local databases only by default")
    parser.add_argument("--messages", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = run_bakeoff(
        args.db_url,
        message_count=args.messages,
        workers=args.workers,
        allow_remote=args.allow_remote,
    )
    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
