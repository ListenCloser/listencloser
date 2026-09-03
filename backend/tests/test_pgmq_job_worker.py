from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from domain.fenced_job_worker import FencedJobWorker
from domain.pgmq_job_worker import PgmqJobWorker


def _job_row(**overrides):
    row = {
        "id": str(uuid4()),
        "workflow_id": str(uuid4()),
        "capability_name": "transcribe",
        "capability_version": "1.0",
        "stage": "claimed",
        "progress": 0.0,
        "status_message": "",
        "retry_count": 0,
        "max_retries": 3,
        "input_version_ids": [],
        "output_version_ids": [],
        "parameters": {},
        "provenance": {},
        "execution_token": str(uuid4()),
        "_queue_msg_id": 41,
    }
    row.update(overrides)
    return row


def _worker() -> tuple[PgmqJobWorker, MagicMock]:
    client = MagicMock()
    worker = PgmqJobWorker(
        visibility_timeout_sec=30,
        heartbeat_interval_sec=5,
        poll_interval_sec=0.01,
        max_workers=2,
    )
    worker._client = client
    return worker, client


def test_receive_installs_delivery_identity_and_excludes_local_in_flight() -> None:
    worker, client = _worker()
    local_job_id = str(uuid4())
    row = _job_row()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=row)
    worker._in_flight.add(local_job_id)

    received = worker._claim_next_job()

    assert received == row
    client.rpc.assert_called_once_with(
        "receive_job_delivery",
        {
            "p_worker_id": worker._worker_id,
            "p_visibility_seconds": 30,
            "p_in_flight_job_ids": [local_job_id],
        },
    )
    assert worker._execution_token(row["id"]) == row["execution_token"]
    assert worker._delivery_id(row["id"]) == 41


def test_receive_failure_is_a_retryable_poll_miss() -> None:
    worker, client = _worker()
    client.rpc.return_value.execute.side_effect = RuntimeError("database unavailable")

    assert worker._claim_next_job() is None


def test_heartbeat_extends_exact_pgmq_delivery() -> None:
    worker, client = _worker()
    row = _job_row()
    worker._remember_execution_token(row["id"], row["execution_token"])
    worker._remember_delivery(row["id"], row["_queue_msg_id"])
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=True)

    worker._renew_lease(row["id"])

    client.rpc.assert_called_once_with(
        "extend_job_delivery",
        {
            "p_job_id": row["id"],
            "p_execution_token": row["execution_token"],
            "p_msg_id": row["_queue_msg_id"],
            "p_visibility_seconds": 30,
        },
    )


def test_execution_finishes_delivery_only_after_job_execution_returns() -> None:
    worker, client = _worker()
    row = _job_row()
    worker._remember_execution_token(row["id"], row["execution_token"])
    worker._remember_delivery(row["id"], row["_queue_msg_id"])
    client.rpc.return_value.execute.return_value = SimpleNamespace(data="archived")
    calls: list[str] = []

    def execute_job(_self, _row, *, already_claimed=False):
        assert already_claimed is True
        calls.append("execute")

    with patch.object(FencedJobWorker, "_execute_job", autospec=True, side_effect=execute_job):
        worker._execute_job(row, already_claimed=True)
        calls.append("finished")

    assert calls == ["execute", "finished"]
    client.rpc.assert_called_once_with(
        "finish_job_delivery",
        {
            "p_job_id": row["id"],
            "p_execution_token": row["execution_token"],
            "p_msg_id": row["_queue_msg_id"],
            "p_retry_delay_seconds": 0,
        },
    )
    assert worker._delivery_id(row["id"]) is None


def test_transport_does_not_scan_jobs_for_orphans() -> None:
    worker, client = _worker()

    assert worker._recover_orphans() == 0
    client.table.assert_not_called()


def test_visibility_timeout_must_exceed_heartbeat_interval() -> None:
    with pytest.raises(ValueError, match="heartbeat interval"):
        PgmqJobWorker(visibility_timeout_sec=10, heartbeat_interval_sec=10)
