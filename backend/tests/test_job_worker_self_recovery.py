"""Regression coverage for same-process orphan recovery fencing."""

from unittest.mock import MagicMock

from domain.job_worker import JobWorker


def _result(data):
    result = MagicMock()
    result.data = data
    return result


def _worker():
    worker = JobWorker(
        lease_duration_sec=5.0,
        heartbeat_interval_sec=0.05,
        poll_interval_sec=0.1,
        max_workers=2,
    )
    worker._client = MagicMock()
    return worker


def _orphan_query(worker):
    return worker._client.table.return_value.update.return_value.lt.return_value.in_.return_value


def test_in_flight_process_excludes_its_own_worker_id_from_recovery():
    worker = _worker()
    worker._in_flight.add("live-job")
    query = _orphan_query(worker)
    query.neq.return_value.execute.return_value = _result([{"id": "other-worker-job"}])

    recovered = worker._recover_orphans()

    assert recovered == 1
    query.neq.assert_called_once_with("worker_id", worker._worker_id)
    query.execute.assert_not_called()


def test_drained_process_can_recover_abandoned_rows_from_any_worker():
    worker = _worker()
    query = _orphan_query(worker)
    query.execute.return_value = _result([{"id": "abandoned-job"}])

    recovered = worker._recover_orphans()

    assert recovered == 1
    query.neq.assert_not_called()
    query.execute.assert_called_once_with()
