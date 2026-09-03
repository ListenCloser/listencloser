from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from domain.job_worker import JobWorker


def _worker(client: MagicMock) -> JobWorker:
    worker = JobWorker(heartbeat_interval_sec=60.0)
    worker._client = client
    return worker


def test_cached_output_lookup_uses_oldest_succeeded_job():
    client = MagicMock()
    worker = _worker(client)
    outputs = [str(uuid4()), str(uuid4())]
    result = MagicMock()
    result.data = [{"id": str(uuid4()), "output_version_ids": outputs}]
    select_query = client.table.return_value.select.return_value
    cache_query = select_query.eq.return_value.eq.return_value
    ordered_query = cache_query.order.return_value
    ordered_query.limit.return_value.execute.return_value = result

    resolved = worker._cached_output_version_ids({"cache_key": "same-work"})

    assert resolved == outputs
    client.table.assert_called_once_with("jobs")
    client.table.return_value.select.assert_called_once_with("id,output_version_ids")
    cache_query.order.assert_called_once_with("created_at", desc=False)
    ordered_query.limit.assert_called_once_with(1)


@pytest.mark.parametrize("outputs", [[str(uuid4()), str(uuid4())], []])
def test_cache_hit_marks_duplicate_succeeded_with_canonical_outputs(outputs):
    client = MagicMock()
    worker = _worker(client)
    handler = MagicMock()
    worker.register("transcribe", "1.0", handler)
    job_id = str(uuid4())
    job_row = {
        "id": job_id,
        "capability_name": "transcribe",
        "capability_version": "1.0",
        "cache_key": "same-work",
    }

    with (
        patch.object(worker, "_claim_job", return_value=True),
        patch.object(worker, "_check_cancelled", return_value=False),
        patch.object(worker, "_check_cache_hit", return_value=True),
        patch.object(worker, "_cached_output_version_ids", return_value=outputs),
        patch.object(worker, "_mark_running") as mark_running,
    ):
        worker._execute_job(job_row)

    handler.assert_not_called()
    mark_running.assert_not_called()
    payload = client.table.return_value.update.call_args.args[0]
    assert payload["stage"] == "succeeded"
    assert payload["progress"] == 1.0
    assert payload["output_version_ids"] == outputs
    update_query = client.table.return_value.update.return_value
    update_query.eq.assert_called_once_with("id", job_id)
