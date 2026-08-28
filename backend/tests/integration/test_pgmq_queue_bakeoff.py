from __future__ import annotations

import os
import subprocess
from typing import Any, cast

import pytest

from scripts.queue_transport_bakeoff import run_bakeoff


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
def test_pgmq_beats_select_then_conditional_claim_contention() -> None:
    report = run_bakeoff(
        _local_db_url(),
        message_count=8,
        workers=4,
    )

    current = cast(dict[str, Any], report["current_select_then_claim"])
    pgmq = cast(dict[str, Any], report["pgmq"])

    assert current["claimed"] == 8
    assert current["duplicate_claims"] == 0
    assert current["lost_claims"] > 0

    assert pgmq["claimed"] == 8
    assert pgmq["duplicate_claims"] == 0
    assert pgmq["lost_claims"] == 0
    assert pgmq["calls_per_claim"] < current["calls_per_claim"]


@pytest.mark.real_stack
def test_pgmq_visibility_timeout_replays_unacked_work() -> None:
    report = run_bakeoff(
        _local_db_url(),
        message_count=4,
        workers=2,
    )
    replay = cast(dict[str, Any], report["visibility_replay"])

    assert replay["first_read_count"] == 1
    assert replay["immediate_second_read_hidden"] is True
    assert replay["replay_message_matches"] is True
    assert replay["replay_read_count"] == 2
