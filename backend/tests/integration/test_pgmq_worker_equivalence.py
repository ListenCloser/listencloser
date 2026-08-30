from __future__ import annotations

import os
import subprocess
from typing import Any, cast

import pytest

from scripts.pgmq_worker_equivalence import run_prototype


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
def test_pgmq_can_extend_visibility_and_archive() -> None:
    report = run_prototype(_local_db_url())
    visibility = cast(dict[str, Any], report["visibility_extension"])

    assert visibility["set_vt_returned_message"] is True
    assert visibility["message_hidden_after_extension"] is True
    assert visibility["archived"] is True


@pytest.mark.real_stack
def test_pgmq_redelivery_can_fence_stale_attempt_publication() -> None:
    report = run_prototype(_local_db_url())
    takeover = cast(dict[str, Any], report["takeover_fencing"])

    assert takeover["same_message_redelivered"] is True
    assert takeover["read_count_advanced"] is True
    assert takeover["attempt_token_changed"] is True
    assert takeover["stale_publish_rejected"] is True
    assert takeover["current_publish_succeeded"] is True
    assert takeover["authoritative_output_is_current_attempt"] is True
    assert takeover["job_finished_under_current_attempt"] is True
    assert takeover["archived"] is True

    metrics_before = cast(dict[str, int], takeover["metrics_before"])
    metrics_after = cast(dict[str, int], takeover["metrics_after"])
    assert metrics_before["queue_length"] == 1
    assert metrics_before["total_messages"] >= 2
    assert metrics_after["queue_length"] == 0
    assert float(takeover["first_queue_wait_sec"]) >= 0
    assert float(takeover["second_queue_wait_sec"]) >= 0
