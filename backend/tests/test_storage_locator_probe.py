from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

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
    version = Version(
        artifact_id=artifact_id,
        storage_key=storage_key,
        storage_bucket="artifacts",
        byte_size=len(content) if stored_byte_size is None else stored_byte_size,
        sha256=hashlib.sha256(content).hexdigest() if stored_sha256 is None else stored_sha256,
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
    def __init__(self, objects: dict[tuple[str, str], bytes], bucket: str):
        self.objects = objects
        self.bucket = bucket

    def download(self, key: str) -> bytes:
        try:
            return self.objects[(self.bucket, key)]
        except KeyError as exc:
            raise FileNotFoundError(f"missing private object: {key}") from exc


class _Storage:
    def __init__(self, objects: dict[tuple[str, str], bytes]):
        self.objects = objects

    def from_(self, bucket: str) -> _Bucket:
        return _Bucket(self.objects, bucket)


class _Client:
    def __init__(self, objects: dict[tuple[str, str], bytes]):
        self.storage = _Storage(objects)


def test_selected_probe_reports_exact_byte_integrity_without_locator_leakage():
    content = b"legacy-midi-bytes"
    rows, version, owner_id, storage_key = _legacy_rows(content=content)
    client = _Client({("artifacts", storage_key): content})

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
            "actual_sha256": hashlib.sha256(content).hexdigest(),
            "stored_byte_size": len(content),
            "stored_sha256": hashlib.sha256(content).hexdigest(),
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

    with pytest.raises(ValueError, match="at least one Version"):
        probe_selected_storage(
            client,
            AuditRows(
                projects=[],
                works=[],
                artifacts=[],
                versions=[],
                workflows=[],
                jobs=[],
            ),
            [],
        )
