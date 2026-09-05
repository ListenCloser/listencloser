"""Unit coverage for transport-neutral Job execution policy."""

import threading
from datetime import UTC, datetime
from unittest.mock import ANY, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from domain.job_worker import JobWorker, _capability_key
from domain.models import Job


def make_result(data):
    result = MagicMock()
    result.data = data
    return result


def make_job_row(**overrides):
    now = datetime.now(UTC).isoformat()
    row: dict = {
        "id": str(uuid4()),
        "workflow_id": str(uuid4()),
        "capability_name": "transcribe",
        "capability_version": "1.0",
        "stage": "claimed",
        "progress": 0.0,
        "status_message": "",
        "retry_count": 0,
        "max_retries": 3,
        "lease_expires_at": None,
        "started_at": None,
        "completed_at": None,
        "input_version_ids": [],
        "output_version_ids": [],
        "parameters": {},
        "cache_key": None,
        "error_message": None,
        "error_details": {},
        "provenance": {},
        "created_at": now,
        "created_by": None,
    }
    row.update(overrides)
    return row


@pytest.fixture
def mock_supabase():
    return MagicMock()


@pytest.fixture
def worker(mock_supabase):
    instance = JobWorker(
        heartbeat_interval_sec=0.05,
        poll_interval_sec=0.01,
        max_workers=2,
    )
    instance._client = mock_supabase
    return instance


def test_custom_transport_methods_are_not_part_of_base_worker() -> None:
    assert not hasattr(JobWorker, "_claim_job")
    assert not hasattr(JobWorker, "_claim_next_job")
    assert not hasattr(JobWorker, "_renew_lease")
    assert not hasattr(JobWorker, "_recover_orphans")


def test_handler_runs_and_job_succeeds(worker):
    job_row = make_job_row()
    handler = MagicMock(return_value=["out-1", "out-2"])
    worker.register("transcribe", "1.0", handler)

    with _mock_execute_env(worker) as mocked:
        worker._execute_job(job_row)

    handler.assert_called_once()
    job_arg, client_arg = handler.call_args[0]
    assert isinstance(job_arg, Job)
    assert job_arg.id == UUID(job_row["id"])
    assert client_arg is worker._client
    mocked["_mark_running"].assert_called_once_with(job_row["id"])
    mocked["_mark_succeeded"].assert_called_once_with(job_row["id"], ["out-1", "out-2"])


def test_handler_non_list_return_is_normalized(worker):
    job_row = make_job_row()
    worker.register("transcribe", "1.0", MagicMock(return_value={"version-a"}))

    with _mock_execute_env(worker) as mocked:
        worker._execute_job(job_row)

    assert mocked["_mark_succeeded"].call_args[0][1] == ["version-a"]


def test_unregistered_capability_fails_job(worker):
    job_row = make_job_row(capability_name="mystery", capability_version="0.1")

    with _mock_execute_env(worker) as mocked:
        worker._execute_job(job_row)

    mocked["_mark_failed"].assert_called_once()
    assert "mystery:0.1" in mocked["_mark_failed"].call_args[0][1]


def test_bad_job_row_fails_parsing(worker):
    job_row = make_job_row(id=None)
    worker.register("transcribe", "1.0", MagicMock(return_value=[]))

    with _mock_execute_env(worker) as mocked:
        worker._execute_job(job_row)

    mocked["_mark_failed"].assert_called_once()
    assert "Failed to parse" in mocked["_mark_failed"].call_args[0][1]


def test_handler_failure_requeues_with_product_retry_policy(worker):
    job_row = make_job_row(retry_count=0, max_retries=3)
    worker.register("transcribe", "1.0", MagicMock(side_effect=ValueError("bad input")))

    with (
        _mock_execute_env(worker) as mocked,
        patch("domain.job_worker.time.sleep", return_value=None) as sleep,
    ):
        worker._execute_job(job_row)

    sleep.assert_called_once_with(2)
    mocked["_requeue_job"].assert_called_once_with(
        job_row["id"], 1, "Processing could not be completed. Retry processing.", ANY
    )
    details = mocked["_requeue_job"].call_args[0][3]
    assert details == {"exception": "bad input", "type": "ValueError"}
    mocked["_mark_failed"].assert_not_called()


def test_exhausted_retry_budget_marks_failed(worker):
    job_row = make_job_row(retry_count=3, max_retries=3)
    worker.register("transcribe", "1.0", MagicMock(side_effect=RuntimeError("fatal")))

    with _mock_execute_env(worker) as mocked:
        worker._execute_job(job_row)

    mocked["_requeue_job"].assert_not_called()
    mocked["_mark_failed"].assert_called_once_with(
        job_row["id"], "Processing could not be completed. Retry processing.", ANY
    )


def test_cancelled_job_never_runs_handler(worker):
    job_row = make_job_row()
    handler = MagicMock()
    worker.register("transcribe", "1.0", handler)

    with _mock_execute_env(worker, cancel_result=True) as mocked:
        worker._execute_job(job_row)

    handler.assert_not_called()
    mocked["_mark_running"].assert_not_called()


def test_cancelled_handler_result_cannot_overwrite_terminal_state(worker):
    job_row = make_job_row()
    handler = MagicMock(return_value=[str(uuid4())])
    worker.register("transcribe", "1.0", handler)

    with _mock_execute_env(worker) as mocked:
        mocked["_check_cancelled"].side_effect = [False, True]
        worker._execute_job(job_row)

    handler.assert_called_once()
    mocked["_mark_succeeded"].assert_not_called()


def test_cancelled_handler_failure_is_not_requeued(worker):
    job_row = make_job_row()
    worker.register("transcribe", "1.0", MagicMock(side_effect=RuntimeError("stopped")))

    with _mock_execute_env(worker) as mocked:
        mocked["_check_cancelled"].side_effect = [False, True]
        worker._execute_job(job_row)

    mocked["_requeue_job"].assert_not_called()
    mocked["_mark_failed"].assert_not_called()


def test_state_change_before_running_prevents_handler_execution(worker):
    job_row = make_job_row()
    handler = MagicMock(return_value=[])
    worker.register("transcribe", "1.0", handler)

    with _mock_execute_env(worker) as mocked:
        mocked["_mark_running"].return_value = False
        worker._execute_job(job_row)

    handler.assert_not_called()


def test_cache_hit_reuses_canonical_outputs_without_handler(worker):
    job_row = make_job_row(cache_key="abc-123")
    handler = MagicMock()
    worker.register("transcribe", "1.0", handler)
    worker._client.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = make_result(
        [{}]
    )

    with _mock_execute_env(
        worker,
        cache_hit=True,
        cached_outputs=["existing-version"],
    ) as mocked:
        worker._execute_job(job_row)

    handler.assert_not_called()
    mocked["_mark_running"].assert_not_called()
    update = worker._client.table.return_value.update.call_args[0][0]
    assert update["stage"] == "succeeded"
    assert update["output_version_ids"] == ["existing-version"]


def test_cache_lookup_matches_only_succeeded_jobs(worker, mock_supabase):
    job_row = make_job_row(cache_key="dup-key")
    chain = mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = make_result([{"id": str(uuid4())}])
    assert worker._check_cache_hit(job_row) is True

    job_row["cache_key"] = None
    assert worker._check_cache_hit(job_row) is False


def test_check_cancelled_reads_product_state(worker, mock_supabase):
    chain = mock_supabase.table.return_value.select.return_value.eq.return_value
    chain.execute.return_value = make_result([{"stage": "cancelled"}])
    assert worker._check_cancelled(str(uuid4())) is True


def test_progress_is_clamped(worker, mock_supabase):
    worker.update_progress("job-1", 9.9, "overflow")
    update = mock_supabase.table.return_value.update.call_args[0][0]
    assert update == {"progress": 1.0, "status_message": "overflow"}


def test_worker_heartbeat_publishes_liveness_and_capabilities(worker, mock_supabase):
    worker.register("understand", "1.0", MagicMock())
    worker._heartbeat_worker()

    row = mock_supabase.table.return_value.upsert.call_args[0][0]
    assert row["worker_id"] == worker._worker_id
    assert row["status"] == "running"
    assert row["capabilities"] == ["understand:1.0"]


def test_register_and_capability_key(worker):
    handler = MagicMock()
    worker.register("transcribe", "1.0", handler)
    assert worker._capabilities["transcribe:1.0"] is handler
    assert _capability_key("analyze", "2-beta") == "analyze:2-beta"


def test_run_uses_transport_receive_hook_and_exits(worker):
    calls = []

    def receive():
        calls.append(1)
        if len(calls) >= 2:
            worker.stop()
        return None

    with patch.object(worker, "_receive_next_job", side_effect=receive):
        worker.run()

    assert len(calls) >= 2
    assert worker._running is False


def test_stop_from_another_thread(worker):
    def delayed_stop():
        import time as _time

        _time.sleep(0.03)
        worker.stop()

    stopper = threading.Thread(target=delayed_stop)
    stopper.start()
    with patch.object(worker, "_receive_next_job", return_value=None):
        worker.run()
    stopper.join(timeout=2.0)

    assert worker._running is False
    assert not stopper.is_alive()


def _mock_execute_env(
    worker,
    *,
    cache_hit: bool = False,
    cached_outputs: list[str] | None = None,
    cancel_result: bool = False,
):
    patches = {
        "_check_cache_hit": patch.object(worker, "_check_cache_hit", return_value=cache_hit),
        "_cached_output_version_ids": patch.object(
            worker,
            "_cached_output_version_ids",
            return_value=cached_outputs,
        ),
        "_check_cancelled": patch.object(worker, "_check_cancelled", return_value=cancel_result),
        "_mark_running": patch.object(worker, "_mark_running", return_value=True),
        "_mark_succeeded": patch.object(worker, "_mark_succeeded"),
        "_mark_failed": patch.object(worker, "_mark_failed"),
        "_requeue_job": patch.object(worker, "_requeue_job"),
        "_heartbeat_delivery": patch.object(worker, "_heartbeat_delivery"),
    }
    mocks = {name: context.start() for name, context in patches.items()}
    return _MultiContext(patches.values(), mocks)


class _MultiContext:
    def __init__(self, contexts, mocks):
        self._contexts = list(contexts)
        self._mocks = mocks

    def __enter__(self):
        return self._mocks

    def __exit__(self, *args):
        for context in self._contexts:
            context.__exit__(*args)
        return False
