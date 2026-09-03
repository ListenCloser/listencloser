from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from storage3.exceptions import StorageApiError

from domain.models import Version
from domain.storage_locator_audit import AuditRows
from domain.storage_locator_policy import StorageLocatorKind, classify_version_storage_locator
from domain.storage_locator_rehome import rehome_selected_storage


def _legacy_rows(
    *,
    content: bytes,
    stored_sha256: str | None = None,
    stored_byte_size: int | None = None,
) -> tuple[AuditRows, dict, str, UUID, UUID, UUID, str]:
    owner_id = str(uuid4())
    project_id = uuid4()
    work_id = uuid4()
    artifact_id = uuid4()
    lineage_parent = uuid4()
    storage_key = "transcriptions/private-take.mid"
    actual_sha256 = hashlib.sha256(content).hexdigest()
    version = Version(
        artifact_id=artifact_id,
        parent_version_id=lineage_parent,
        lineage=[lineage_parent],
        storage_key=storage_key,
        storage_bucket="artifacts",
        byte_size=len(content) if stored_byte_size is None else stored_byte_size,
        sha256=actual_sha256 if stored_sha256 is None else stored_sha256,
        created_by=owner_id,
        label="private-take.mid",
        metadata={"semantic_role": "performance_transcription"},
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
    return rows, version, owner_id, project_id, work_id, artifact_id, storage_key


class _Bucket:
    def __init__(self, client: "_Client", bucket: str):
        self.client = client
        self.bucket = bucket

    def download(self, key: str) -> bytes:
        try:
            return self.client.objects[(self.bucket, key)]
        except KeyError as exc:
            raise StorageApiError("private source missing", "NoSuchKey", 404) from exc

    def upload(self, key: str, content: bytes, _options: dict) -> None:
        self.client.uploads.append((self.bucket, key))
        stored = b"corrupt-copy" if self.client.corrupt_upload else content
        self.client.objects[(self.bucket, key)] = stored

    def remove(self, keys: list[str]) -> None:
        for key in keys:
            self.client.removes.append((self.bucket, key))
            self.client.objects.pop((self.bucket, key), None)


class _Storage:
    def __init__(self, client: "_Client"):
        self.client = client

    def from_(self, bucket: str) -> _Bucket:
        return _Bucket(self.client, bucket)


class _InsertQuery:
    def __init__(self, client: "_Client"):
        self.client = client
        self.row: dict | None = None

    def insert(self, row: dict) -> "_InsertQuery":
        self.row = row
        return self

    def execute(self):
        assert self.row is not None
        if self.client.insert_error is not None:
            raise self.client.insert_error
        self.client.inserted_rows.append(self.row)
        return SimpleNamespace(data=[self.row])


class _Client:
    def __init__(
        self,
        objects: dict[tuple[str, str], bytes],
        *,
        corrupt_upload: bool = False,
        insert_error: Exception | None = None,
    ):
        self.objects = dict(objects)
        self.storage = _Storage(self)
        self.corrupt_upload = corrupt_upload
        self.insert_error = insert_error
        self.uploads: list[tuple[str, str]] = []
        self.removes: list[tuple[str, str]] = []
        self.inserted_rows: list[dict] = []

    def table(self, table: str) -> _InsertQuery:
        assert table == "artifact_versions"
        return _InsertQuery(self)


def test_rehome_dry_run_verifies_source_without_mutation_or_private_locator_leakage():
    content = b"legacy-midi"
    rows, version, owner_id, _project_id, _work_id, _artifact_id, storage_key = _legacy_rows(
        content=content
    )
    client = _Client({("artifacts", storage_key): content})

    result = rehome_selected_storage(client, rows, [version["id"]])[0]

    assert result["state"] == "ready"
    assert result["applied"] is False
    assert result["actual_byte_size"] == len(content)
    assert result["actual_sha256"] == hashlib.sha256(content).hexdigest()
    assert result["source_byte_size_matches"] is True
    assert result["source_sha256_matches"] is True
    assert client.uploads == []
    assert client.inserted_rows == []

    serialized = json.dumps(result)
    assert owner_id not in serialized
    assert storage_key not in serialized
    assert version["label"] not in serialized


def test_rehome_apply_copies_exact_bytes_and_publishes_trusted_immutable_version():
    content = b"legacy-midi"
    rows, version, owner_id, project_id, _work_id, artifact_id, storage_key = _legacy_rows(
        content=content
    )
    client = _Client({("artifacts", storage_key): content})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]

    assert result["state"] == "applied"
    assert result["applied"] is True
    assert len(client.uploads) == 1
    assert len(client.inserted_rows) == 1
    assert client.objects[("artifacts", storage_key)] == content

    created = Version.model_validate(client.inserted_rows[0])
    assert created.parent_version_id == UUID(version["id"])
    assert created.lineage == [UUID(value) for value in [*version["lineage"], version["id"]]]
    assert created.created_by == owner_id
    assert created.produced_by_job_id is None
    assert created.byte_size == len(content)
    assert created.sha256 == hashlib.sha256(content).hexdigest()
    assert created.metadata["semantic_role"] == "performance_transcription"
    provenance = created.metadata["storage_locator_rehome"]
    assert provenance["method"] == "storage_locator_rehome_v1"
    assert provenance["source_version_id"] == version["id"]

    decision = classify_version_storage_locator(
        created,
        owner_id=owner_id,
        project_id=project_id,
        artifact_id=artifact_id,
        allowed_job_ids=set(),
    )
    assert decision.trusted is True
    assert decision.kind is StorageLocatorKind.owner_upload

    serialized = json.dumps(result)
    assert owner_id not in serialized
    assert storage_key not in serialized
    assert created.storage_key not in serialized


def test_rehome_apply_leaves_missing_source_as_explicit_non_mutating_state():
    content = b"missing"
    rows, version, _owner_id, _project_id, _work_id, _artifact_id, _storage_key = _legacy_rows(
        content=content
    )
    client = _Client({})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]

    assert result["state"] == "source_object_missing"
    assert result["applied"] is False
    assert client.uploads == []
    assert client.inserted_rows == []


def test_rehome_refuses_source_metadata_mismatch_before_copy():
    content = b"actual"
    rows, version, _owner_id, _project_id, _work_id, _artifact_id, storage_key = _legacy_rows(
        content=content,
        stored_sha256="0" * 64,
        stored_byte_size=len(content) + 1,
    )
    client = _Client({("artifacts", storage_key): content})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]

    assert result["state"] == "source_metadata_mismatch"
    assert result["source_byte_size_matches"] is False
    assert result["source_sha256_matches"] is False
    assert client.uploads == []
    assert client.inserted_rows == []


def test_rehome_rejects_non_latest_source_to_avoid_resurrecting_history():
    content = b"legacy"
    rows, version, owner_id, project_id, _work_id, artifact_id, storage_key = _legacy_rows(
        content=content
    )
    newer = Version(
        artifact_id=artifact_id,
        storage_key=f"{owner_id}/{project_id}/{artifact_id}/newer.mid",
        storage_bucket="artifacts",
        byte_size=1,
        sha256=hashlib.sha256(b"x").hexdigest(),
        created_by=owner_id,
        created_at=datetime.now(UTC) + timedelta(seconds=1),
    ).model_dump(mode="json")
    rows = AuditRows(
        projects=rows.projects,
        works=rows.works,
        artifacts=rows.artifacts,
        versions=[version, newer],
        workflows=[],
        jobs=[],
    )
    client = _Client({("artifacts", storage_key): content})

    with pytest.raises(ValueError, match="not latest"):
        rehome_selected_storage(client, rows, [version["id"]], apply=True)

    assert client.uploads == []
    assert client.inserted_rows == []


def test_rehome_removes_new_destination_when_post_copy_verification_fails():
    content = b"legacy"
    rows, version, _owner_id, _project_id, _work_id, _artifact_id, storage_key = _legacy_rows(
        content=content
    )
    client = _Client({("artifacts", storage_key): content}, corrupt_upload=True)

    with pytest.raises(RuntimeError, match="post-copy verification"):
        rehome_selected_storage(client, rows, [version["id"]], apply=True)

    assert len(client.uploads) == 1
    assert client.removes == client.uploads
    assert len(client.objects) == 1
    assert client.objects[("artifacts", storage_key)] == content
    assert client.inserted_rows == []


def test_rehome_is_idempotent_after_replacement_version_exists():
    content = b"legacy"
    rows, version, _owner_id, _project_id, _work_id, _artifact_id, storage_key = _legacy_rows(
        content=content
    )
    client = _Client({("artifacts", storage_key): content})

    first = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]
    replacement = client.inserted_rows[0]
    rows_after = AuditRows(
        projects=rows.projects,
        works=rows.works,
        artifacts=rows.artifacts,
        versions=[version, replacement],
        workflows=[],
        jobs=[],
    )

    second = rehome_selected_storage(client, rows_after, [version["id"]], apply=True)[0]

    assert first["state"] == "applied"
    assert second["state"] == "already_applied"
    assert second["replacement_version_id"] == first["replacement_version_id"]
    assert len(client.uploads) == 1
    assert len(client.inserted_rows) == 1
