from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from domain import upload_api
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.upload_api import FinalizeUploadBody, finalize_upload

_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
_WORK_ID = UUID("33333333-3333-3333-3333-333333333333")
_OTHER_WORK_ID = UUID("44444444-4444-4444-4444-444444444444")
_STORAGE_KEY = (
    "owner-1/11111111-1111-1111-1111-111111111111/"
    "pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.musicxml"
)


def _body(work_id: UUID = _WORK_ID) -> FinalizeUploadBody:
    return FinalizeUploadBody(
        filename="original.musicxml",
        byte_size=64,
        content_type="application/xml",
        storage_key=_STORAGE_KEY,
        work_id=work_id,
    )


def _source_models(work_id: UUID = _WORK_ID) -> tuple[Artifact, Version]:
    artifact = Artifact(
        id=uuid4(),
        work_id=work_id,
        kind=ArtifactKind.musicxml_score,
        mime_type="application/vnd.recordare.musicxml+xml",
    )
    version = Version(
        id=uuid4(),
        artifact_id=artifact.id,
        storage_key=_STORAGE_KEY,
        storage_bucket="artifacts",
        byte_size=64,
        created_by="owner-1",
        label="original.musicxml",
        metadata={"representation": "score_source", "source": "user_upload"},
    )
    return artifact, version


def test_source_finalize_is_idempotent_for_same_storage_key(monkeypatch):
    work = Work(id=_WORK_ID, project_id=_PROJECT_ID, title="Existing recording")
    artifact, version = _source_models()
    sb = SimpleNamespace()

    monkeypatch.setattr(upload_api, "_sb", lambda: sb)
    monkeypatch.setattr(
        upload_api,
        "_require_project_and_work",
        lambda client, project_id, work_id, owner_id: work,
    )
    monkeypatch.setattr(upload_api, "_existing_upload", lambda *args: (artifact, version))

    def unexpected_storage_read(*args):
        raise AssertionError("idempotent finalize must not re-read or republish Storage")

    monkeypatch.setattr(upload_api, "_find_storage_object", unexpected_storage_read)

    response = finalize_upload(
        _PROJECT_ID,
        _body(),
        SimpleNamespace(),
        auth=SimpleNamespace(user=SimpleNamespace(id="owner-1")),
    )

    assert response.artifact.id == artifact.id
    assert response.version.id == version.id


def test_source_finalize_rejects_storage_key_already_bound_to_other_work(monkeypatch):
    work = Work(id=_WORK_ID, project_id=_PROJECT_ID, title="Existing recording")
    artifact, version = _source_models(_OTHER_WORK_ID)

    monkeypatch.setattr(upload_api, "_sb", lambda: SimpleNamespace())
    monkeypatch.setattr(
        upload_api,
        "_require_project_and_work",
        lambda client, project_id, work_id, owner_id: work,
    )
    monkeypatch.setattr(upload_api, "_existing_upload", lambda *args: (artifact, version))

    with pytest.raises(HTTPException) as exc:
        finalize_upload(
            _PROJECT_ID,
            _body(),
            SimpleNamespace(),
            auth=SimpleNamespace(user=SimpleNamespace(id="owner-1")),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Upload was already finalized for another work"
