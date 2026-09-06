from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from storage3.exceptions import StorageApiError

from domain.models import Version
from domain.storage_locator_audit import AuditRows
from domain.storage_locator_probe import probe_selected_storage


def _legacy_rows(
    *,
    content: bytes,
    stored_sha256: str | None = None,
    stored_byte_size: int | None = None,
) -> tuple[AuditRows, dict, str, str]:
    owner_id = str(uuid4())
    project_id = uuid4()
    work_id = uuid4()
    artifact_id = uuid4()
    storage_key = "transcriptions/private-take.mid"
    actual_sha256 = hashlib.sha256(content).hexdigest()
    version = Version(
        artifact_id=artifact_id,
        storage_key=storage_key,
        storage_bucket="artifacts",
        byte_size=len(content) if stored_byte_size is None else stored_byte_size,
        sha256=actual_sha256 if stored_sha256 is None else stored_sha256,
        created_by=owner_id,
        created_at=datetime.now(UTC),
    ).model_dump(mode="json")
    rows = AuditRows(
        projects=[{"id": str(project_id), "owner_id": owner_id}],
        works=[{"id": str(work_id), "project_id": str(project_id)}],
        artifacts=[
            {
                "id": str(artifact_id),
                "work_id": str(work_id),
                "kind": "midi_performance",
            }
        ],
        versions=[version],
        workflows=[],
        jobs=[],
    )
    return rows, version, owner_id, storage_key


class _Bucket:
    def __init__(
        self,
        objects: dict[tuple[str, str], bytes],
        bucket: str,
        error: Exception | None,
    ):
        self.objects = objects
        self.bucket = bucket
        self.error = error

    def download(self, key: str) -> bytes:
        if self.error is not None:
            raise self.error
        try:
            return self.objects[(self.bucket, key)]
        except KeyError as exc:
            message = f"missing private object: {key}"
            raise StorageApiError(message, "NoSuchKey", 404) from exc


class _Storage:
    def __init__(
        self,
        objects: dict[tuple[str, str], bytes],
        error: Exception | None = None,
    ):
        self.objects = objects
        self.error = error

    def from_(self, bucket: str) -> _Bucket:
        return _Bucket(self.objects, bucket, self.error)


class _Client:
    def __init__(
        self,
        objects: dict[tuple[str, str], bytes],
        error: Exception | None = None,
    ):
        self.storage = _Storage(objects, error)


def test_selected_probe_reports_exact_byte_integrity_without_locator_leakage():
    content = b"legacy-midi-bytes"
    rows, version, owner_id, storage_key = _legacy_rows(content=content)
    client = _Client({("artifacts", storage_key): content})
    expected_sha256 = hashlib.sha256(content).hexdigest()

    probes = probe_selected_storage(client, rows, [version["id"]])

    assert probes == [
        {
            "version_id": version["id"],
            "reason": "owner_path_shape",
            "legacy_path_class": "transcriptions",
            "is_latest": True,
            "storage_key_sha256": hashlib.sha256(storage_key.encode()).hexdigest(),
            "object_exists": True,
            "actual_byte_size": len(content),
            "actual_sha256": expected_sha256,
            "stored_byte_size": len(content),
            "stored_sha256": expected_sha256,
            "byte_size_matches": True,
            "sha256_matches": True,
        }
    ]

    serialized = json.dumps(probes)
    assert owner_id not in serialized
    assert storage_key not in serialized


def test_selected_probe_reports_missing_object_without_provider_exception_text():
    content = b"missing-source"
    rows, version, owner_id, storage_key = _legacy_rows(content=content)
    client = _Client({})

    probes = probe_selected_storage(client, rows, [version["id"]])

    assert probes[0]["object_exists"] is False
    assert probes[0]["actual_byte_size"] is None
    assert probes[0]["actual_sha256"] is None
    assert probes[0]["byte_size_matches"] is None
    assert probes[0]["sha256_matches"] is None

    serialized = json.dumps(probes)
    assert owner_id not in serialized
    assert storage_key not in serialized
    assert "missing private object" not in serialized


def test_selected_probe_fails_closed_on_non_missing_storage_error():
    content = b"unknown-state"
    rows, version, _owner_id, storage_key = _legacy_rows(content=content)
    provider_message = f"gateway failure while reading {storage_key}"
    error = StorageApiError(provider_message, "InternalError", 500)
    client = _Client({}, error=error)

    with pytest.raises(RuntimeError) as captured:
        probe_selected_storage(client, rows, [version["id"]])

    assert "without proving the source object is missing" in str(captured.value)
    assert storage_key not in str(captured.value)
    assert provider_message not in str(captured.value)


def test_selected_probe_surfaces_stored_metadata_mismatch():
    content = b"actual-bytes"
    rows, version, _owner_id, storage_key = _legacy_rows(
        content=content,
        stored_sha256="0" * 64,
        stored_byte_size=len(content) + 1,
    )
    client = _Client({("artifacts", storage_key): content})

    probe = probe_selected_storage(client, rows, [version["id"]])[0]

    assert probe["object_exists"] is True
    assert probe["byte_size_matches"] is False
    assert probe["sha256_matches"] is False


def test_selected_probe_rejects_already_trusted_version():
    content = b"modern"
    owner_id = str(uuid4())
    project_id = uuid4()
    work_id = uuid4()
    artifact_id = uuid4()
    storage_key = f"{owner_id}/{project_id}/{artifact_id}/source.wav"
    version = Version(
        artifact_id=artifact_id,
        storage_key=storage_key,
        storage_bucket="artifacts",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        created_by=owner_id,
        created_at=datetime.now(UTC),
    ).model_dump(mode="json")
    rows = AuditRows(
        projects=[{"id": str(project_id), "owner_id": owner_id}],
        works=[{"id": str(work_id), "project_id": str(project_id)}],
        artifacts=[
            {
                "id": str(artifact_id),
                "work_id": str(work_id),
                "kind": "audio_original",
            }
        ],
        versions=[version],
        workflows=[],
        jobs=[],
    )
    client = _Client({("artifacts", storage_key): content})

    with pytest.raises(ValueError, match="already trusted"):
        probe_selected_storage(client, rows, [version["id"]])


def test_selected_probe_requires_explicit_version_selection():
    client = _Client({})
    empty_rows = AuditRows(
        projects=[],
        works=[],
        artifacts=[],
        versions=[],
        workflows=[],
        jobs=[],
    )

    with pytest.raises(ValueError, match="at least one Version"):
        probe_selected_storage(client, empty_rows, [])
