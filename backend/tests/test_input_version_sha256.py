from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

import pytest

from domain.fenced_job_worker import _HandlerClient


class _Bucket:
    def __init__(self, payload: bytes = b"payload") -> None:
        self.payload = payload
        self.downloaded: list[str] = []

    def download(self, path: str) -> bytes:
        self.downloaded.append(path)
        return self.payload


class _Storage:
    def __init__(self) -> None:
        self.buckets: dict[str, _Bucket] = {}

    def from_(self, bucket: str) -> _Bucket:
        return self.buckets.setdefault(bucket, _Bucket())


class _VersionQuery:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def select(self, _columns: str = "*") -> _VersionQuery:
        return self

    def in_(self, column: str, values: list[str]) -> _VersionQuery:
        requested = {str(value) for value in values}
        self.rows = [row for row in self.rows if str(row.get(column)) in requested]
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=list(self.rows))


class _RpcCall:
    def __init__(self, client: _RawClient, name: str, params: dict[str, Any]) -> None:
        self.client = client
        self.name = name
        self.params = params

    def execute(self) -> SimpleNamespace:
        self.client.rpc_calls.append((self.name, dict(self.params)))
        if self.client.rpc_error is not None:
            raise self.client.rpc_error
        return SimpleNamespace(data=[self.params["p_sha256"]])


class _RawClient:
    def __init__(self, versions: list[dict[str, Any]]) -> None:
        self.storage = _Storage()
        self.versions = versions
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []
        self.rpc_error: Exception | None = None

    def table(self, name: str) -> _VersionQuery:
        assert name == "artifact_versions"
        return _VersionQuery(self.versions)

    def rpc(self, name: str, params: dict[str, Any]) -> _RpcCall:
        return _RpcCall(self, name, params)


def _client(raw: _RawClient, input_version_ids: list[str]) -> _HandlerClient:
    return _HandlerClient(raw, "job-1", "token-a", input_version_ids)


def test_declared_input_download_enriches_exact_downloaded_bytes() -> None:
    raw = _RawClient(
        [
            {
                "id": "input-1",
                "storage_bucket": "artifacts",
                "storage_key": "uploads/user/original.wav",
            }
        ]
    )
    client = _client(raw, ["input-1"])

    payload = client.storage.from_("artifacts").download("uploads/user/original.wav")

    assert payload == b"payload"
    assert raw.rpc_calls == [
        (
            "fenced_job_verify_input_sha256",
            {
                "p_job_id": "job-1",
                "p_execution_token": "token-a",
                "p_version_id": "input-1",
                "p_sha256": hashlib.sha256(b"payload").hexdigest(),
            },
        )
    ]


def test_non_declared_and_same_job_generated_downloads_do_not_enrich() -> None:
    raw = _RawClient(
        [
            {
                "id": "input-1",
                "storage_bucket": "artifacts",
                "storage_key": "uploads/user/original.wav",
            }
        ]
    )
    client = _client(raw, ["input-1"])

    client.storage.from_("artifacts").download(
        "jobs/job-1/execution-token-a/attempt-0/transcribed.mid"
    )
    client.storage.from_("artifacts").download("uploads/other/not-an-input.wav")

    assert raw.rpc_calls == []


def test_integrity_rpc_failure_fails_closed_after_existing_download() -> None:
    raw = _RawClient(
        [
            {
                "id": "input-1",
                "storage_bucket": "artifacts",
                "storage_key": "uploads/user/original.wav",
            }
        ]
    )
    raw.rpc_error = RuntimeError("input Version sha256 conflicts with measured bytes")
    client = _client(raw, ["input-1"])

    with pytest.raises(RuntimeError, match="sha256 conflicts"):
        client.storage.from_("artifacts").download("uploads/user/original.wav")

    assert raw.storage.from_("artifacts").downloaded == ["uploads/user/original.wav"]
    assert len(raw.rpc_calls) == 1


def test_shared_declared_input_locator_enriches_every_matching_version() -> None:
    raw = _RawClient(
        [
            {
                "id": "input-1",
                "storage_bucket": "artifacts",
                "storage_key": "uploads/user/original.wav",
            },
            {
                "id": "input-2",
                "storage_bucket": "artifacts",
                "storage_key": "uploads/user/original.wav",
            },
        ]
    )
    client = _client(raw, ["input-1", "input-2"])

    client.storage.from_("artifacts").download("uploads/user/original.wav")

    assert [params["p_version_id"] for _name, params in raw.rpc_calls] == [
        "input-1",
        "input-2",
    ]
