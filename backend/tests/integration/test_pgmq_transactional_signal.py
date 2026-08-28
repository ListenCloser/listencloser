from __future__ import annotations

import os
import subprocess
from typing import Any, cast

import pytest

from scripts.queue_transactional_signal_prototype import run_prototype


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


@pytest.mark.real_stack
def test_queued_transitions_emit_exact_job_identity() -> None:
    report = run_prototype(_local_db_url())

    insert = cast(dict[str, Any], report["insert_signal"])
    requeue = cast(dict[str, Any], report["requeue_signal"])

    assert insert["message_received"] is True
    assert insert["message_job_id_matches"] is True
    assert report["nonqueued_insert_silent"] is True
    assert requeue["requeue_message_received"] is True
    assert requeue["requeue_message_job_id_matches"] is True
    assert requeue["same_stage_update_silent"] is True


@pytest.mark.real_stack
def test_job_and_queue_signal_share_transaction_rollback() -> None:
    report = run_prototype(_local_db_url())

    insert_rollback = cast(dict[str, Any], report["insert_rollback"])
    requeue_rollback = cast(dict[str, Any], report["requeue_rollback"])

    assert insert_rollback["job_row_rolled_back"] is True
    assert insert_rollback["queue_signal_rolled_back"] is True
    assert requeue_rollback["job_stage_rolled_back"] is True
    assert requeue_rollback["queue_signal_rolled_back"] is True
