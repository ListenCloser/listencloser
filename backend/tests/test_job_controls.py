from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from domain.models import Capability, Job, JobLifecycle, JobStage
from domain.repositories import JobRepo


def _job(stage: JobStage) -> Job:
    return Job(
        workflow_id=uuid4(),
        capability=Capability(name="understand", version="1.0"),
        lifecycle=JobLifecycle(current=stage),
    )


def _updated_row(repo: JobRepo, job: Job, stage: JobStage) -> dict:
    row = repo._job_to_row(job)
    row["stage"] = stage.value
    row["status_message"] = (
        "cancelled by user" if stage == JobStage.cancelled else "queued for manual retry"
    )
    return row


def test_cancel_transitions_owned_running_job_atomically():
    client = MagicMock()
    repo = JobRepo(client)
    job = _job(JobStage.running)
    repo.get = MagicMock(return_value=job)
    result = SimpleNamespace(data=[_updated_row(repo, job, JobStage.cancelled)])
    chain = client.table.return_value.update.return_value.eq.return_value.in_
    chain.return_value.execute.return_value = result

    cancelled = repo.cancel(job.id, "owner")

    assert cancelled.lifecycle.current == JobStage.cancelled
    patch = client.table.return_value.update.call_args.args[0]
    assert patch["stage"] == "cancelled"
    assert patch["lease_expires_at"] is None
    chain.assert_called_once_with("stage", ["queued", "claimed", "running"])


def test_cancel_is_idempotent_for_cancelled_job():
    client = MagicMock()
    repo = JobRepo(client)
    job = _job(JobStage.cancelled)
    repo.get = MagicMock(return_value=job)

    assert repo.cancel(job.id, "owner") is job
    client.table.assert_not_called()


def test_cancel_rejects_completed_job():
    repo = JobRepo(MagicMock())
    job = _job(JobStage.succeeded)
    repo.get = MagicMock(return_value=job)

    with pytest.raises(RuntimeError, match="cannot cancel a succeeded job"):
        repo.cancel(job.id, "owner")


def test_retry_creates_a_linked_job_without_rewriting_terminal_history():
    client = MagicMock()
    repo = JobRepo(client)
    job = _job(JobStage.failed)
    retry_id = uuid5(NAMESPACE_URL, f"listencloser:retry:{job.id}")
    repo.get = MagicMock(side_effect=lambda candidate, _owner: job if candidate == job.id else None)
    repo._verify_workflow_owner = MagicMock()

    def insert(row):
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(data=[row]),
        )

    client.table.return_value.insert.side_effect = insert

    retried = repo.retry(job.id, "owner")

    assert retried.lifecycle.current == JobStage.queued
    assert retried.id == retry_id
    assert retried.provenance["retry_of_job_id"] == str(job.id)
    assert job.lifecycle.current == JobStage.failed
    client.table.return_value.update.assert_not_called()


def test_retry_rejects_active_job():
    repo = JobRepo(MagicMock())
    job = _job(JobStage.running)
    repo.get = MagicMock(return_value=job)

    with pytest.raises(RuntimeError, match="cannot retry a running job"):
        repo.retry(job.id, "owner")


def test_retry_is_idempotent_for_the_same_terminal_attempt():
    client = MagicMock()
    repo = JobRepo(client)
    failed = _job(JobStage.failed)
    existing = _job(JobStage.queued)
    repo.get = MagicMock(side_effect=[failed, existing])

    assert repo.retry(failed.id, "owner") is existing
    client.table.assert_not_called()
