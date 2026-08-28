from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest


_SCRIPT = Path(__file__).parents[3] / "scripts" / "queue_transport_bakeoff.py"
_SPEC = importlib.util.spec_from_file_location("queue_transport_bakeoff", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
queue_transport_bakeoff = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = queue_transport_bakeoff
_SPEC.loader.exec_module(queue_transport_bakeoff)


@pytest.mark.real_stack
def test_pgmq_beats_select_then_conditional_claim_contention() -> None:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        pytest.skip("DB_URL is provided by the fresh local Supabase integration workflow")

    report = queue_transport_bakeoff.run_bakeoff(
        db_url,
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
    db_url = os.environ.get("DB_URL")
    if not db_url:
        pytest.skip("DB_URL is provided by the fresh local Supabase integration workflow")

    report = queue_transport_bakeoff.run_bakeoff(
        db_url,
        message_count=4,
        workers=2,
    )
    replay = cast(dict[str, Any], report["visibility_replay"])

    assert replay["first_read_count"] == 1
    assert replay["immediate_second_read_hidden"] is True
    assert replay["replay_message_matches"] is True
    assert replay["replay_read_count"] == 2
