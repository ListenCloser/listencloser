"""
Comprehensive unit tests for the listencloser JobWorker.

All supabase calls are mocked.  No real database is required.
"""

import threading
from datetime import UTC, datetime
from unittest.mock import ANY, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from domain.job_worker import JobWorker, _capability_key
from domain.models import Job

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_result(data):
    """Return a MagicMock whose ``.data`` attribute holds *data*."""
    r = MagicMock()
    r.data = data
    return r


def make_job_row(**overrides):
    """Build a realistic ``jobs`` table row dict.

    All keys that the worker reads are present with sensible defaults.
    """
    now = datetime.now(UTC).isoformat()
    base: dict = {
        "id": str(uuid4()),
        "workflow_id": str(uuid4()),
        "capability_name": "transcribe",
        "capability_version": "1.0",
        "stage": "queued",
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
    base.update(overrides)
    return base


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_supabase():
    """The root MagicMock that simulates the supabase ``Client``."""
    return MagicMock()


@pytest.fixture
def worker(mock_supabase):
    """A ``JobWorker`` pre-wired to *mock_supabase* with short intervals."""
    w = JobWorker(
        lease_duration_sec=5.0,
        heartbeat_interval_sec=0.05,
        poll_interval_sec=0.1,
        max_workers=2,
    )
    w._client = mock_supabase
    return w


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Claim a queued job
# ═══════════════════════════════════════════════════════════════════════════════


class TestClaimJob:
    def test_successful_claim(self, worker, mock_supabase):
        job_row = make_job_row()
        job_id = job_row["id"]
        _configure_update_eq_eq(mock_supabase, [job_row])

        claimed = worker._claim_job(job_id)

        assert claimed is True
        mock_supabase.table.assert_any_call("jobs")
        update_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert update_args["stage"] == "claimed"
        assert update_args["worker_id"] == worker._worker_id
        assert update_args["lease_expires_at"] is not None

    def test_claim_lost_to_another_worker(self, worker, mock_supabase):
        _configure_update_eq_eq(mock_supabase, [])  # no rows matched

        claimed = worker._claim_job(str(uuid4()))

        assert claimed is False

    def test_claim_returns_false_when_data_is_none(self, worker, mock_supabase):
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=None
        )

        claimed = worker._claim_job(str(uuid4()))

        assert claimed is False


class TestClaimNextJob:
    def test_claim_next_job_uses_atomic_rpc(self, worker, mock_supabase):
        job_row = make_job_row(stage="claimed", worker_id=worker._worker_id)
        mock_supabase.rpc.return_value.execute.return_value = make_result([job_row])

        claimed = worker._claim_next_job()

        assert claimed == job_row
        mock_supabase.rpc.assert_called_once_with(
            "claim_next_job",
            {
                "p_worker_id": worker._worker_id,
                "p_lease_seconds": worker._lease_duration,
            },
        )

    def test_claim_next_job_returns_none_for_empty_queue(self, worker, mock_supabase):
        mock_supabase.rpc.return_value.execute.return_value = make_result([])

        assert worker._claim_next_job() is None

    def test_claim_next_job_db_error_is_retryable_poll_miss(self, worker, mock_supabase):
        mock_supabase.rpc.return_value.execute.side_effect = Exception("database unavailable")

        assert worker._claim_next_job() is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Lease expiry / orphan recovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrphanRecovery:
    def test_recovers_expired_claimed_jobs(self, worker, mock_supabase):
        _configure_update_lt_in(mock_supabase, [{"id": "a"}, {"id": "b"}])

        count = worker._recover_orphans()

        assert count == 2
        update = mock_supabase.table.return_value.update.call_args[0][0]
        assert update["stage"] == "queued"
        assert update["worker_id"] is None
        assert update["lease_expires_at"] is None

    def test_no_orphans(self, worker, mock_supabase):
        _configure_update_lt_in(mock_supabase, [])

        count = worker._recover_orphans()

        assert count == 0

    def test_supabase_error_during_recovery(self, worker, mock_supabase):
        mock_supabase.table.return_value.update.return_value.lt.return_value.in_.return_value.execute.side_effect = Exception(
            "timeout"
        )

        count = worker._recover_orphans()

        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Job execution succeeds
# ═══════════════════════════════════════════════════════════════════════════════


class TestJobExecutionSuccess:
    """Business‑logic tests use ``patch.object`` on internal DB helpers.

    This keeps the test focused on the execution flow rather than
    the supabase chain plumbing for every step.
    """

    def test_handler_runs_and_job_succeeds(self, worker):
        job_row = make_job_row()
        handler = MagicMock(return_value=["out-1", "out-2"])
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker) as mocked:
            worker._execute_job(job_row)

        handler.assert_called_once()
        mocked["_mark_running"].assert_called_once_with(job_row["id"])
        mocked["_mark_succeeded"].assert_called_once()
        assert mocked["_mark_succeeded"].call_args[0][0] == job_row["id"]
        assert mocked["_mark_succeeded"].call_args[0][1] == ["out-1", "out-2"]

    def test_handler_receives_domain_job_and_client(self, worker):
        job_row = make_job_row()
        handler = MagicMock(return_value=[])
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker):
            worker._execute_job(job_row)

        job_arg, client_arg = handler.call_args[0]
        assert isinstance(job_arg, Job)
        assert job_arg.id == UUID(job_row["id"])
        assert client_arg is worker._client

    def test_handler_non_list_return_wrapped(self, worker):
        job_row = make_job_row()
        handler = MagicMock(return_value={"k": "v"})
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker) as mocked:
            worker._execute_job(job_row)

        assert mocked["_mark_succeeded"].call_args[0][1] == ["k"]

    def test_handler_none_return_becomes_empty_list(self, worker):
        job_row = make_job_row()
        handler = MagicMock(return_value=None)
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker) as mocked:
            worker._execute_job(job_row)

        assert mocked["_mark_succeeded"].call_args[0][1] == []

    def test_unregistered_capability_fails_job(self, worker):
        job_row = make_job_row(capability_name="mystery", capability_version="0.1")

        with _mock_execute_env(worker) as mocked:
            worker._execute_job(job_row)

        mocked["_mark_failed"].assert_called_once()
        error_msg = mocked["_mark_failed"].call_args[0][1]
        assert "mystery:0.1" in error_msg

    def test_bad_job_row_fails_parsing(self, worker):
        job_row = make_job_row(id=None)
        # A handler must be registered so the code reaches _row_to_job;
        # otherwise the handler-missing check fires first.
        worker.register("transcribe", "1.0", MagicMock(return_value=[]))

        with _mock_execute_env(worker) as mocked:
            worker._execute_job(job_row)

        mocked["_mark_failed"].assert_called_once()
        assert "Failed to parse" in mocked["_mark_failed"].call_args[0][1]

    def test_worker_skips_when_claim_lost(self, worker):
        job_row = make_job_row()
        handler = MagicMock()

        with _mock_execute_env(worker, claim_result=False) as mocked:
            worker._execute_job(job_row)

        handler.assert_not_called()
        mocked["_mark_running"].assert_not_called()

    # ── Same scenario exercised with raw mock_client (the user‑preferred pattern) ──

    def test_success_with_mock_client_chain(self, worker, mock_supabase):
        job_row = make_job_row()
        handler = MagicMock(return_value=["ok"])
        worker.register("transcribe", "1.0", handler)

        _configure_update_eq_eq(mock_supabase, [job_row])  # claim & mark_*
        _configure_sel_eq(mock_supabase, [{"stage": "running"}])  # cancel check

        worker._execute_job(job_row)

        handler.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Job execution fails with retry
# ═══════════════════════════════════════════════════════════════════════════════


class TestJobRetry:
    def test_retries_on_handler_failure(self, worker):
        job_row = make_job_row(retry_count=0, max_retries=3)
        handler = MagicMock(side_effect=ValueError("bad input"))
        worker.register("transcribe", "1.0", handler)

        with (
            _mock_execute_env(worker) as mocked,
            patch("domain.job_worker.time.sleep", return_value=None),
        ):
            worker._execute_job(job_row)

        mocked["_requeue_job"].assert_called_once_with(
            job_row["id"], 1, "Processing could not be completed. Retry processing.", ANY
        )
        mocked["_mark_failed"].assert_not_called()

    def test_raw_exception_preserved_in_error_details(self, worker):
        job_row = make_job_row(retry_count=0, max_retries=3)
        handler = MagicMock(side_effect=ValueError("bad input"))
        worker.register("transcribe", "1.0", handler)

        with (
            _mock_execute_env(worker) as mocked,
            patch("domain.job_worker.time.sleep", return_value=None),
        ):
            worker._execute_job(job_row)

        error_details = mocked["_requeue_job"].call_args[0][3]
        assert error_details["exception"] == "bad input"
        assert error_details["type"] == "ValueError"

    def test_retry_increments_count_correctly(self, worker):
        job_row = make_job_row(retry_count=2, max_retries=5)
        handler = MagicMock(side_effect=RuntimeError("oops"))
        worker.register("transcribe", "1.0", handler)

        with (
            _mock_execute_env(worker) as mocked,
            patch("domain.job_worker.time.sleep", return_value=None),
        ):
            worker._execute_job(job_row)

        assert mocked["_requeue_job"].call_args[0][1] == 3

    def test_exponential_backoff_applied(self, worker):
        job_row = make_job_row(retry_count=0)
        handler = MagicMock(side_effect=Exception("fail"))
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker), patch("domain.job_worker.time.sleep") as mock_sleep:
            worker._execute_job(job_row)

        mock_sleep.assert_called_once_with(2)  # 2^1


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Job exhausts retries
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetryExhaustion:
    def test_exceeds_max_retries_marks_failed(self, worker):
        job_row = make_job_row(retry_count=3, max_retries=3)
        handler = MagicMock(side_effect=Exception("fatal"))
        worker.register("transcribe", "1.0", handler)

        with (
            _mock_execute_env(worker) as mocked,
            patch("domain.job_worker.time.sleep", return_value=None),
        ):
            worker._execute_job(job_row)

        mocked["_requeue_job"].assert_not_called()
        mocked["_mark_failed"].assert_called_once_with(
            job_row["id"], "Processing could not be completed. Retry processing.", ANY
        )

    def test_last_retry_allowed_after_that_exhausted(self, worker):
        job_row = make_job_row(retry_count=2, max_retries=3)
        handler = MagicMock(side_effect=Exception("retryable"))
        worker.register("transcribe", "1.0", handler)

        with (
            _mock_execute_env(worker) as mocked,
            patch("domain.job_worker.time.sleep", return_value=None),
        ):
            worker._execute_job(job_row)

        # retry_count → 3, 3 <= 3  →  still within budget
        mocked["_requeue_job"].assert_called_once()
        mocked["_mark_failed"].assert_not_called()

    def test_already_past_max_retries_fails_immediately(self, worker):
        job_row = make_job_row(retry_count=5, max_retries=3)
        handler = MagicMock(side_effect=Exception("very late"))
        worker.register("transcribe", "1.0", handler)

        with (
            _mock_execute_env(worker) as mocked,
            patch("domain.job_worker.time.sleep", return_value=None),
        ):
            worker._execute_job(job_row)

        mocked["_requeue_job"].assert_not_called()
        mocked["_mark_failed"].assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Job cancellation
# ═══════════════════════════════════════════════════════════════════════════════


class TestJobCancellation:
    def test_cancelled_job_skipped_by_worker(self, worker):
        job_row = make_job_row()
        handler = MagicMock()
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker, cancel_result=True) as mocked:
            worker._execute_job(job_row)

        handler.assert_not_called()
        mocked["_mark_running"].assert_not_called()
        mocked["_mark_succeeded"].assert_not_called()

    def test_check_cancelled_true_for_cancelled_stage(self, worker, mock_supabase):
        _configure_sel_eq(mock_supabase, [{"stage": "cancelled"}])

        result = worker._check_cancelled(str(uuid4()))

        assert result is True

    def test_check_cancelled_false_for_non_cancelled(self, worker, mock_supabase):
        _configure_sel_eq(mock_supabase, [{"stage": "running"}])

        result = worker._check_cancelled(str(uuid4()))

        assert result is False

    def test_check_cancelled_safe_on_db_error(self, worker, mock_supabase):
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = (
            Exception("timeout")
        )

        result = worker._check_cancelled(str(uuid4()))

        assert result is False

    def test_cancelled_handler_result_cannot_overwrite_terminal_state(self, worker):
        job_row = make_job_row()
        handler = MagicMock(return_value=[str(uuid4())])
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker) as mocked:
            mocked["_check_cancelled"].side_effect = [False, True]
            worker._execute_job(job_row)

        handler.assert_called_once()
        mocked["_mark_succeeded"].assert_not_called()

    def test_cancelled_handler_failure_is_not_requeued(self, worker):
        job_row = make_job_row()
        handler = MagicMock(side_effect=Exception("stopped"))
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker) as mocked:
            mocked["_check_cancelled"].side_effect = [False, True]
            worker._execute_job(job_row)

        mocked["_requeue_job"].assert_not_called()
        mocked["_mark_failed"].assert_not_called()

    def test_state_change_before_running_prevents_handler_execution(self, worker):
        job_row = make_job_row()
        handler = MagicMock(return_value=[])
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker) as mocked:
            mocked["_mark_running"].return_value = False
            worker._execute_job(job_row)

        handler.assert_not_called()
        mocked["_mark_succeeded"].assert_not_called()


class TestWorkerHeartbeat:
    def test_heartbeat_publishes_liveness_and_capabilities(self, worker, mock_supabase):
        worker.register("understand", "1.0", MagicMock())

        worker._heartbeat_worker()

        mock_supabase.table.assert_called_with("worker_heartbeats")
        row = mock_supabase.table.return_value.upsert.call_args[0][0]
        assert row["worker_id"] == worker._worker_id
        assert row["status"] == "running"
        assert row["capabilities"] == ["understand:1.0"]


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Idempotency via cache_key
# ═══════════════════════════════════════════════════════════════════════════════


class TestCacheIdempotency:
    def test_cache_hit_skips_handler(self, worker):
        job_row = make_job_row(cache_key="abc-123")
        handler = MagicMock()
        worker.register("transcribe", "1.0", handler)

        with _mock_execute_env(worker, cache_hit=True) as mocked:
            worker._execute_job(job_row)

        handler.assert_not_called()
        mocked["_claim_job"].assert_called_once_with(job_row["id"])
        mocked["_mark_running"].assert_not_called()

    def test_cache_hit_detects_existing_succeeded(self, worker, mock_supabase):
        job_row = make_job_row(cache_key="dup-key")
        _configure_sel_eq_eq(mock_supabase, [{"id": str(uuid4())}])

        hit = worker._check_cache_hit(job_row)

        assert hit is True

    def test_no_cache_key_triggers_no_hit(self, worker):
        job_row = make_job_row(cache_key=None)

        hit = worker._check_cache_hit(job_row)

        assert hit is False

    def test_cache_only_matches_succeeded_jobs(self, worker, mock_supabase):
        job_row = make_job_row(cache_key="key-1")
        _configure_sel_eq_eq(mock_supabase, [])

        hit = worker._check_cache_hit(job_row)

        assert hit is False

    def test_cache_check_error_returns_false(self, worker, mock_supabase):
        job_row = make_job_row(cache_key="err-key")
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception(
            "boom"
        )

        hit = worker._check_cache_hit(job_row)

        assert hit is False


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Progress updates
# ═══════════════════════════════════════════════════════════════════════════════


class TestProgressUpdates:
    def test_update_progress_sends_correct_values(self, worker, mock_supabase):
        job_id = str(uuid4())
        _configure_update_eq_eq(mock_supabase, [{"id": job_id}])

        worker.update_progress(job_id, 0.65, "halfway")

        update_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert update_args["progress"] == 0.65
        assert update_args["status_message"] == "halfway"

    def test_progress_clamped_below_zero(self, worker, mock_supabase):
        _configure_update_eq_eq(mock_supabase, [{}])

        worker.update_progress(str(uuid4()), -0.3, "negative")

        update_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert update_args["progress"] == 0.0

    def test_progress_clamped_above_one(self, worker, mock_supabase):
        _configure_update_eq_eq(mock_supabase, [{}])

        worker.update_progress(str(uuid4()), 9.9, "overflow")

        update_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert update_args["progress"] == 1.0

    def test_progress_db_error_does_not_raise(self, worker, mock_supabase):
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception(
            "DB down"
        )

        worker.update_progress(str(uuid4()), 0.3, "still here")

        # no exception → pass


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Capability registry
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilityRegistry:
    def test_register_stores_handler(self, worker):
        handler = MagicMock()
        worker.register("transcribe", "1.0", handler)
        assert worker._capabilities["transcribe:1.0"] is handler

    def test_register_multiple_versions(self, worker):
        h1, h2 = MagicMock(), MagicMock()
        worker.register("transcribe", "1.0", h1)
        worker.register("transcribe", "2.0", h2)
        assert worker._capabilities["transcribe:1.0"] is h1
        assert worker._capabilities["transcribe:2.0"] is h2

    def test_register_overwrites_previous(self, worker):
        h1, h2 = MagicMock(), MagicMock()
        worker.register("x", "1", h1)
        worker.register("x", "1", h2)
        assert worker._capabilities["x:1"] is h2

    def test_capability_key_format(self):
        assert _capability_key("transcribe", "1.0") == "transcribe:1.0"
        assert _capability_key("analyze", "2-beta") == "analyze:2-beta"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Worker stop — graceful shutdown
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkerStop:
    def test_stop_sets_event(self, worker):
        assert not worker._stop_event.is_set()
        worker.stop()
        assert worker._stop_event.is_set()

    def test_run_exits_quickly_when_signaled(self, worker):
        poll_calls = []

        def _fake_poll():
            poll_calls.append(1)
            if len(poll_calls) >= 2:
                worker.stop()
            return None

        with (
            patch.object(worker, "_recover_orphans", return_value=0),
            patch.object(worker, "_claim_next_job", side_effect=_fake_poll),
        ):
            worker.run()

        assert len(poll_calls) >= 2
        assert worker._running is False

    def test_run_recovers_orphans_that_expire_after_startup(self, worker):
        worker._lease_duration = 0.01

        def _stop_after_poll():
            worker.stop()
            return None

        with (
            patch.object(worker, "_recover_orphans", return_value=0) as recover,
            patch.object(worker, "_claim_next_job", side_effect=_stop_after_poll),
            patch(
                "domain.job_worker.time.monotonic",
                side_effect=[0.0, 0.0, 0.02],
            ),
        ):
            worker.run()

        assert recover.call_count == 2

    def test_stop_from_another_thread(self, worker):
        def _delayed_stop():
            import time as _time

            _time.sleep(0.15)
            worker.stop()

        stopper = threading.Thread(target=_delayed_stop)
        stopper.start()

        with (
            patch.object(worker, "_recover_orphans", return_value=0),
            patch.object(worker, "_claim_next_job", return_value=None),
        ):
            worker.run()

        stopper.join(timeout=2.0)
        assert worker._running is False
        assert not stopper.is_alive()


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _configure_update_eq_eq(mock, data):
    """``client.table().update().eq().eq().execute()``"""
    chain = mock.table.return_value.update.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = make_result(data)


def _configure_update_eq(mock, data):
    """``client.table().update().eq().execute()``"""
    chain = mock.table.return_value.update.return_value.eq.return_value
    chain.execute.return_value = make_result(data)


def _configure_update_lt_in(mock, data):
    """``client.table().update().lt().in_().execute()``"""
    chain = mock.table.return_value.update.return_value.lt.return_value.in_.return_value
    chain.execute.return_value = make_result(data)


def _configure_sel_eq(mock, data):
    """``client.table().select().eq().execute()``"""
    chain = mock.table.return_value.select.return_value.eq.return_value
    chain.execute.return_value = make_result(data)


def _configure_sel_eq_eq(mock, data):
    """``client.table().select().eq().eq().execute()``"""
    chain = mock.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = make_result(data)


def _configure_sel_eq_order_limit(mock, data):
    """``client.table().select().eq().order().limit().execute()``"""
    chain = mock.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value
    chain.execute.return_value = make_result(data)


# ── Context manager for _execute_job patches ─────────────────────────────────


def _mock_execute_env(
    worker,
    *,
    cache_hit: bool = False,
    claim_result: bool = True,
    cancel_result: bool = False,
):
    """Patch every DB helper used by ``_execute_job``.

    Returns a dict mapping helper names to the mocked versions so tests
    can assert calls on specific helpers.

    Also patches ``_renew_lease`` so the heartbeat thread is a no-op.
    """
    patches = {
        "_check_cache_hit": patch.object(worker, "_check_cache_hit", return_value=cache_hit),
        "_claim_job": patch.object(worker, "_claim_job", return_value=claim_result),
        "_check_cancelled": patch.object(worker, "_check_cancelled", return_value=cancel_result),
        "_mark_running": patch.object(worker, "_mark_running"),
        "_mark_succeeded": patch.object(worker, "_mark_succeeded"),
        "_mark_failed": patch.object(worker, "_mark_failed"),
        "_requeue_job": patch.object(worker, "_requeue_job"),
        "_renew_lease": patch.object(worker, "_renew_lease"),
    }
    mocks = {}
    # Start all patches and collect their mocks
    for name, p in patches.items():
        mocks[name] = p.start()

    return _MultiContext(patches.values(), mocks)


class _MultiContext:
    """Combine multiple patch contexts so they can be used in a single ``with``."""

    def __init__(self, contexts, mocks):
        self._contexts = list(contexts)
        self._mocks = mocks

    def __enter__(self):
        return self._mocks

    def __exit__(self, *args):
        for ctx in self._contexts:
            ctx.__exit__(*args)
        return False
