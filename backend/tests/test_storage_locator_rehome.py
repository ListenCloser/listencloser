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


def _legacy_rows(content: bytes) -> tuple[AuditRows, dict, str, UUID, UUID, str]:
    owner_id = str(uuid4())
    project_id = uuid4()
    work_id = uuid4()
    artifact_id = uuid4()
    parent_id = uuid4()
    storage_key = "transcriptions/private-take.mid"
    version = Version(
        artifact_id=artifact_id,
        parent_version_id=parent_id,
        lineage=[parent_id],
        storage_key=storage_key,
        storage_bucket="artifacts",
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
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
    return rows, version, owner_id, project_id, artifact_id, storage_key


class _Bucket:
    def __init__(self, client: _Client, bucket: str):
        self.client = client
        self.bucket = bucket

    def download(self, key: str) -> bytes:
        try:
            return self.client.objects[(self.bucket, key)]
        except KeyError as exc:
            raise StorageApiError("private source missing", "NoSuchKey", 404) from exc

    def upload(self, key: str, content: bytes, _options: dict) -> None:
        self.client.uploads.append((self.bucket, key))
        self.client.objects[(self.bucket, key)] = (
            b"corrupt-copy" if self.client.corrupt_upload else content
        )

    def remove(self, keys: list[str]) -> None:
        for key in keys:
            self.client.removes.append((self.bucket, key))
            self.client.objects.pop((self.bucket, key), None)


class _Storage:
    def __init__(self, client: _Client):
        self.client = client

    def from_(self, bucket: str) -> _Bucket:
        return _Bucket(self.client, bucket)


class _RpcQuery:
    def __init__(self, client: _Client, function: str, params: dict):
        self.client = client
        self.function = function
        self.params = params

    def execute(self):
        assert self.function == "publish_storage_rehome_version"
        if self.client.insert_error is not None:
            raise self.client.insert_error
        row = self.params["p_version"]
        self.client.rpc_calls.append((self.function, self.params))
        self.client.inserted_rows.append(row)
        return SimpleNamespace(data=[row])


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
        self.rpc_calls: list[tuple[str, dict]] = []

    def rpc(self, function: str, params: dict) -> _RpcQuery:
        return _RpcQuery(self, function, params)


def test_dry_run_verifies_source_without_mutation_or_private_locator_leakage():
    content = b"legacy-midi"
    rows, version, owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
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


def test_apply_requires_exactly_one_selected_version():
    content = b"legacy-midi"
    rows, version, _owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
    client = _Client({("artifacts", storage_key): content})

    with pytest.raises(ValueError, match="exactly one Version"):
        rehome_selected_storage(
            client,
            rows,
            [version["id"], str(uuid4())],
            apply=True,
        )

    assert client.uploads == []
    assert client.inserted_rows == []


def test_apply_copies_exact_bytes_and_publishes_trusted_immutable_version():
    content = b"legacy-midi"
    rows, version, owner_id, project_id, artifact_id, storage_key = _legacy_rows(content)
    client = _Client({("artifacts", storage_key): content})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]

    assert result["state"] == "applied"
    assert len(client.uploads) == 1
    assert len(client.inserted_rows) == 1
    assert client.rpc_calls[0][1]["p_source_version_id"] == version["id"]
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


def test_missing_historical_sha_is_computed_for_replacement():
    content = b"production-shaped-no-historical-hash"
    rows, version, _owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
    version["sha256"] = None
    rows = AuditRows(
        projects=rows.projects,
        works=rows.works,
        artifacts=rows.artifacts,
        versions=[version],
        workflows=[],
        jobs=[],
    )
    client = _Client({("artifacts", storage_key): content})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]
    created = Version.model_validate(client.inserted_rows[0])

    assert result["source_sha256_matches"] is None
    assert created.byte_size == len(content)
    assert created.sha256 == hashlib.sha256(content).hexdigest()


def test_missing_source_is_explicit_and_non_mutating():
    content = b"missing"
    rows, version, _owner_id, _project_id, _artifact_id, _storage_key = _legacy_rows(content)
    client = _Client({})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]

    assert result["state"] == "source_object_missing"
    assert result["applied"] is False
    assert client.uploads == []
    assert client.inserted_rows == []


def test_source_metadata_mismatch_prevents_copy():
    content = b"actual"
    rows, version, _owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
    version["byte_size"] = len(content) + 1
    version["sha256"] = "0" * 64
    rows = AuditRows(
        projects=rows.projects,
        works=rows.works,
        artifacts=rows.artifacts,
        versions=[version],
        workflows=[],
        jobs=[],
    )
    client = _Client({("artifacts", storage_key): content})

    result = rehome_selected_storage(client, rows, [version["id"]], apply=True)[0]

    assert result["state"] == "source_metadata_mismatch"
    assert result["source_byte_size_matches"] is False
    assert result["source_sha256_matches"] is False
    assert client.uploads == []
    assert client.inserted_rows == []


def test_non_latest_source_is_rejected_to_avoid_resurrecting_history():
    content = b"legacy"
    rows, version, owner_id, project_id, artifact_id, storage_key = _legacy_rows(content)
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


def test_corrupt_copy_is_removed_before_version_publication():
    content = b"legacy"
    rows, version, _owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
    client = _Client({("artifacts", storage_key): content}, corrupt_upload=True)

    with pytest.raises(RuntimeError, match="post-copy verification"):
        rehome_selected_storage(client, rows, [version["id"]], apply=True)

    assert len(client.uploads) == 1
    assert client.removes == client.uploads
    assert client.objects == {("artifacts", storage_key): content}
    assert client.inserted_rows == []


def test_uncertain_version_publication_preserves_verified_destination_for_retry():
    content = b"legacy"
    rows, version, _owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
    client = _Client(
        {("artifacts", storage_key): content},
        insert_error=TimeoutError("response lost after possible commit"),
    )

    with pytest.raises(RuntimeError, match="outcome is unknown"):
        rehome_selected_storage(client, rows, [version["id"]], apply=True)

    assert len(client.uploads) == 1
    assert client.removes == []
    assert len(client.objects) == 2
    assert client.objects[("artifacts", storage_key)] == content


def test_rerun_after_replacement_exists_is_idempotent():
    content = b"legacy"
    rows, version, _owner_id, _project_id, _artifact_id, storage_key = _legacy_rows(content)
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
