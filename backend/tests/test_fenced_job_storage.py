from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from domain.fenced_job_worker import FencedJobWorker
from domain.job_worker import JobWorker


class _Bucket:
    def __init__(self) -> None:
        self.downloaded: list[str] = []
        self.uploaded: list[str] = []
        self.removed: list[str] = []
        self.fail_upload = False

    def download(self, path: str) -> bytes:
        self.downloaded.append(path)
        return b"payload"

    def upload(self, path: str, *_args: Any, **_kwargs: Any) -> dict[str, str]:
        if self.fail_upload:
            raise RuntimeError("simulated upload failure")
        self.uploaded.append(path)
        return {"path": path}

    def remove(self, paths: list[str]) -> dict[str, list[str]]:
        self.removed.extend(paths)
        return {"removed": paths}


class _Storage:
    def __init__(self) -> None:
        self.bucket = _Bucket()

    def from_(self, _bucket: str) -> _Bucket:
        return self.bucket


class _Query:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def select(self, _columns: str = "*", *_args: Any, **_kwargs: Any) -> _Query:
        return self

    def eq(self, column: str, value: Any) -> _Query:
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=list(self.rows))


class _JobMutation:
    def __init__(self, client: _Client) -> None:
        self.client = client
        self.values: dict[str, Any] = {}
        self.filters: list[tuple[str, Any]] = []

    def update(self, values: dict[str, Any]) -> _JobMutation:
        self.values = dict(values)
        return self

    def eq(self, column: str, value: Any) -> _JobMutation:
        self.filters.append((column, value))
        return self

    def execute(self) -> SimpleNamespace:
        self.client.job_updates.append((dict(self.values), list(self.filters)))
        return SimpleNamespace(data=[dict(self.values)])


class _Client:
    def __init__(self) -> None:
        self.storage = _Storage()
        self.tables: dict[str, list[dict[str, Any]]] = {"artifacts": []}
        self.job_updates: list[tuple[dict[str, Any], list[tuple[str, Any]]]] = []

    def table(self, name: str) -> _Query | _JobMutation:
        if name == "jobs":
            return _JobMutation(self)
        return _Query(self.tables.get(name, []))


def _handler_client() -> tuple[FencedJobWorker, _Client, Any]:
    worker = FencedJobWorker()
    raw = _Client()
    worker._client = raw
    worker._remember_execution_token("job-1", "token-a")
    return worker, raw, worker._handler_client("job-1")


def test_handler_storage_is_attempt_scoped_and_cleanup_is_non_destructive() -> None:
    _worker, raw, client = _handler_client()

    original_key = "jobs/job-1/attempt-0/output.bin"
    scoped_key = "jobs/job-1/execution-token-a/attempt-0/output.bin"

    assert client.storage.from_("artifacts").download("source/input.bin") == b"payload"
    assert raw.storage.bucket.downloaded == ["source/input.bin"]

    client.storage.from_("artifacts").upload(original_key, b"payload")
    assert raw.storage.bucket.uploaded == [scoped_key]
    assert client.rewrite_output_row({"storage_key": original_key}) == {
        "storage_key": scoped_key,
    }

    # A stale handler must never call the external Storage delete API: there is
    # no cross-system transaction that can make deletion atomic with the Job
    # execution-token check. Database references are fenced separately; private
    # orphan bytes can be collected out of band without risking successor data.
    assert client.storage.from_("artifacts").remove([scoped_key]) == []
    assert raw.storage.bucket.removed == []

    with pytest.raises(RuntimeError, match="current Job namespace"):
        client.storage.from_("artifacts").upload("shared/output.bin", b"payload")

    with pytest.raises(RuntimeError, match="unfenced storage operation move"):
        client.storage.from_("artifacts").move(scoped_key, f"{scoped_key}.moved")

    with pytest.raises(RuntimeError, match="unfenced table operation schema"):
        _ = client.table("artifacts").schema

    with pytest.raises(RuntimeError, match="raw client operation raw"):
        _ = client.raw


def test_failed_upload_is_not_publishable_by_logical_storage_key() -> None:
    _worker, raw, client = _handler_client()
    original_key = "jobs/job-1/attempt-0/missing.bin"

    raw.storage.bucket.fail_upload = True
    with pytest.raises(RuntimeError, match="simulated upload failure"):
        client.storage.from_("artifacts").upload(original_key, b"payload")

    # Only a successful Storage write may establish the logical→scoped mapping.
    # If a capability catches an upload error and continues, the database fence
    # must see the original unscoped key and reject publication rather than
    # accepting a Version that points at an object that was never written.
    assert client.rewrite_output_row({"storage_key": original_key}) == {
        "storage_key": original_key,
    }


def test_pending_artifact_is_visible_to_repository_owner_verification() -> None:
    _worker, raw, client = _handler_client()

    artifact = {"id": "artifact-1", "work_id": "work-1", "kind": "musicxml_score"}
    result = client.table("artifacts").insert(artifact).execute()
    assert result.data == [artifact]

    # The Artifact is intentionally not durable before its Version. VersionRepo
    # nevertheless reads artifacts(work_id) to verify ownership before insert,
    # so the fenced client must provide read-your-writes for this exact pending id.
    assert raw.tables["artifacts"] == []
    pending = client.table("artifacts").select("work_id").eq("id", "artifact-1").execute()
    assert pending.data == [{"work_id": "work-1"}]

    missing = client.table("artifacts").select("work_id").eq("id", "other").execute()
    assert missing.data == []


def test_stale_finisher_cannot_forget_successor_generation() -> None:
    worker = FencedJobWorker()
    worker._remember_execution_token("job-1", "token-a")
    worker._remember_execution_token("job-1", "token-b")

    worker._forget_execution_token("job-1", "token-a")
    assert worker._execution_token("job-1") == "token-b"

    worker._forget_execution_token("job-1", "token-b")
    with pytest.raises(RuntimeError, match="no active execution token"):
        worker._execution_token("job-1")


def test_queue_claim_releases_duplicate_local_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = FencedJobWorker()
    raw = _Client()
    worker._client = raw
    worker._remember_execution_token("job-1", "token-a")
    with worker._in_flight_lock:
        worker._in_flight.add("job-1")

    monkeypatch.setattr(
        JobWorker,
        "_claim_next_job",
        lambda _self: {"id": "job-1", "execution_token": "token-b"},
    )

    assert worker._claim_next_job() is None
    assert worker._execution_token("job-1") == "token-a"
    assert raw.job_updates == [
        (
            {
                "stage": "queued",
                "worker_id": None,
                "lease_expires_at": None,
                "execution_token": None,
            },
            [
                ("id", "job-1"),
                ("worker_id", worker._worker_id),
                ("execution_token", "token-b"),
                ("stage", "claimed"),
            ],
        ),
    ]
