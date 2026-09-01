from __future__ import annotations

import hashlib
from typing import Any

from domain.fenced_job_worker import _HandlerClient


class _Bucket:
    def __init__(self) -> None:
        self.downloaded: list[str] = []

    def download(self, path: str, *args: Any, **kwargs: Any) -> bytes:
        assert not args
        assert not kwargs
        self.downloaded.append(path)
        return b"trusted stored bytes"


class _Storage:
    def __init__(self) -> None:
        self.bucket = _Bucket()
        self.requested_buckets: list[str] = []

    def from_(self, bucket: str) -> _Bucket:
        self.requested_buckets.append(bucket)
        return self.bucket


class _RpcCall:
    def execute(self) -> object:
        return object()


class _RawClient:
    def __init__(self) -> None:
        self.storage = _Storage()
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def rpc(self, name: str, params: dict[str, Any]) -> _RpcCall:
        self.rpc_calls.append((name, dict(params)))
        return _RpcCall()


def test_trusted_storage_read_verifies_declared_input_without_second_download() -> None:
    raw = _RawClient()
    client = _HandlerClient(raw, "job-1", "token-a")

    content = client.storage.from_("artifacts").download("uploads/source.wav")

    assert content == b"trusted stored bytes"
    assert raw.storage.requested_buckets == ["artifacts"]
    assert raw.storage.bucket.downloaded == ["uploads/source.wav"]
    assert raw.rpc_calls == [
        (
            "fenced_job_verify_input_sha256",
            {
                "p_job_id": "job-1",
                "p_execution_token": "token-a",
                "p_storage_bucket": "artifacts",
                "p_storage_key": "uploads/source.wav",
                "p_sha256": hashlib.sha256(b"trusted stored bytes").hexdigest(),
            },
        )
    ]
