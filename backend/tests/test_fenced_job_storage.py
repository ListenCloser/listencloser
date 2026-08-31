from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from domain.fenced_job_worker import FencedJobWorker


class _Bucket:
    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.removed: list[str] = []

    def upload(self, path: str, *_args: Any, **_kwargs: Any) -> dict[str, str]:
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


class _Client:
    def __init__(self) -> None:
        self.storage = _Storage()
        self.tables: dict[str, list[dict[str, Any]]] = {"artifacts": []}

    def table(self, name: str) -> _Query:
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

    client.storage.from_("artifacts").upload(original_key, b"payload")
    assert raw.storage.bucket.uploaded == [scoped_key]
    assert client.rewrite_output_row({"storage_key": original_key}) == {
        "storage_key": scoped_key
    }

    # A stale handler must never call the external Storage delete API: there is
    # no cross-system transaction that can make deletion atomic with the Job
    # execution-token check. Database references are fenced separately; private
    # orphan bytes can be collected out of band without risking successor data.
    assert client.storage.from_("artifacts").remove([scoped_key]) == []
    assert raw.storage.bucket.removed == []

    with pytest.raises(RuntimeError, match="current Job namespace"):
        client.storage.from_("artifacts").upload("shared/output.bin", b"payload")

    with pytest.raises(RuntimeError, match="unfenced storage move"):
        client.storage.from_("artifacts").move(scoped_key, f"{scoped_key}.moved")


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
