import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import partitura
import pytest
from fastapi import HTTPException

from domain import upload_api
from domain.models import ArtifactKind, Work
from domain.upload_api import (
    FinalizeUploadBody,
    _score_descriptor,
    _upload_descriptor,
    _validate_musicxml_bytes,
    finalize_upload,
)

_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
_WORK_ID = UUID("33333333-3333-3333-3333-333333333333")


@pytest.mark.parametrize("filename", ["source.musicxml", "source.xml"])
def test_score_descriptor_requires_existing_work_and_normalizes_mime(filename):
    assert _score_descriptor(filename, 1024, _WORK_ID) == (
        Path(filename).suffix.lstrip("."),
        "application/vnd.recordare.musicxml+xml",
    )
    ext, mime_type, kind = _upload_descriptor(filename, 1024, "application/xml", _WORK_ID)
    assert ext == Path(filename).suffix.lstrip(".")
    assert mime_type == "application/vnd.recordare.musicxml+xml"
    assert kind == ArtifactKind.musicxml_score

    with pytest.raises(HTTPException) as exc:
        _score_descriptor(filename, 1024, None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "MusicXML must be attached to an existing Work"


def test_upload_descriptor_preserves_audio_kind():
    ext, mime_type, kind = _upload_descriptor("take.wav", 1024, "audio/wav", None)
    assert ext == "wav"
    assert mime_type == "audio/x-wav"
    assert kind == ArtifactKind.audio_original


def test_musicxml_validation_uses_partitura_parser(monkeypatch):
    observed = {}

    def fake_load_musicxml(filename, *, validate=False):
        observed["bytes"] = Path(filename).read_bytes()
        observed["validate"] = validate
        return object()

    monkeypatch.setattr(partitura, "load_musicxml", fake_load_musicxml)
    _validate_musicxml_bytes(b"<score-partwise version='4.0'/>")
    assert observed == {
        "bytes": b"<score-partwise version='4.0'/>",
        "validate": False,
    }


def test_musicxml_validation_fails_closed_on_parser_error(monkeypatch):
    def reject_musicxml(*args, **kwargs):
        raise ValueError("not MusicXML")

    monkeypatch.setattr(partitura, "load_musicxml", reject_musicxml)
    with pytest.raises(HTTPException) as exc:
        _validate_musicxml_bytes(b"<html/>")
    assert exc.value.status_code == 422
    assert exc.value.detail == "Invalid or unsupported MusicXML"


def test_finalize_source_score_publishes_immutable_role_hash_and_no_alignment(monkeypatch):
    score_bytes = b"<score-partwise version='4.0'><part-list/></score-partwise>"
    storage_key = f"owner-1/{_PROJECT_ID}/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.musicxml"
    work = Work(id=_WORK_ID, project_id=_PROJECT_ID, title="Existing recording")
    captured = {}
    sb = SimpleNamespace()

    monkeypatch.setattr(upload_api, "_sb", lambda: sb)
    monkeypatch.setattr(
        upload_api,
        "_require_project_and_work",
        lambda client, project_id, work_id, owner_id: work,
    )
    monkeypatch.setattr(upload_api, "_existing_upload", lambda *args: None)
    monkeypatch.setattr(
        upload_api,
        "_find_storage_object",
        lambda *args: {"metadata": {"size": len(score_bytes)}},
    )
    monkeypatch.setattr(upload_api, "_download_storage_bytes", lambda *args: score_bytes)
    monkeypatch.setattr(upload_api, "_validate_musicxml_bytes", lambda content: None)

    class FakeWorkRepo:
        def __init__(self, client):
            pass

    class FakeArtifactRepo:
        def __init__(self, client):
            pass

        def create(self, artifact, owner_id):
            captured["artifact"] = artifact
            return artifact

    class FakeVersionRepo:
        def __init__(self, client):
            pass

        def create(self, version, owner_id):
            captured["version"] = version
            return version

    monkeypatch.setattr(upload_api, "WorkRepo", FakeWorkRepo)
    monkeypatch.setattr(upload_api, "ArtifactRepo", FakeArtifactRepo)
    monkeypatch.setattr(upload_api, "VersionRepo", FakeVersionRepo)

    response = finalize_upload(
        _PROJECT_ID,
        FinalizeUploadBody(
            filename="original.musicxml",
            byte_size=len(score_bytes),
            content_type="application/xml",
            storage_key=storage_key,
            work_id=_WORK_ID,
        ),
        SimpleNamespace(),
        auth=SimpleNamespace(user=SimpleNamespace(id="owner-1")),
    )

    artifact = captured["artifact"]
    version = captured["version"]
    assert response.artifact.id == artifact.id
    assert response.version.id == version.id
    assert artifact.work_id == _WORK_ID
    assert artifact.kind == ArtifactKind.musicxml_score
    assert artifact.mime_type == "application/vnd.recordare.musicxml+xml"
    assert version.parent_version_id is None
    assert version.lineage == []
    assert version.byte_size == len(score_bytes)
    assert version.sha256 == hashlib.sha256(score_bytes).hexdigest()
    assert version.metadata == {
        "representation": "score_source",
        "source": "user_upload",
        "original_filename": "original.musicxml",
    }
    assert "measure_starts_seconds" not in version.metadata


def test_finalize_invalid_source_score_removes_pending_object_before_publication(monkeypatch):
    score_bytes = b"<html/>"
    storage_key = f"owner-1/{_PROJECT_ID}/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.musicxml"
    work = Work(id=_WORK_ID, project_id=_PROJECT_ID, title="Existing recording")
    removed = []

    class FakeBucket:
        def remove(self, keys):
            removed.extend(keys)

    class FakeStorage:
        def from_(self, bucket):
            assert bucket == "artifacts"
            return FakeBucket()

    sb = SimpleNamespace(storage=FakeStorage())
    monkeypatch.setattr(upload_api, "_sb", lambda: sb)
    monkeypatch.setattr(
        upload_api,
        "_require_project_and_work",
        lambda client, project_id, work_id, owner_id: work,
    )
    monkeypatch.setattr(upload_api, "_existing_upload", lambda *args: None)
    monkeypatch.setattr(
        upload_api,
        "_find_storage_object",
        lambda *args: {"metadata": {"size": len(score_bytes)}},
    )
    monkeypatch.setattr(upload_api, "_download_storage_bytes", lambda *args: score_bytes)

    def reject(content):
        raise HTTPException(status_code=422, detail="Invalid or unsupported MusicXML")

    monkeypatch.setattr(upload_api, "_validate_musicxml_bytes", reject)

    with pytest.raises(HTTPException) as exc:
        finalize_upload(
            _PROJECT_ID,
            FinalizeUploadBody(
                filename="bad.musicxml",
                byte_size=len(score_bytes),
                content_type="application/xml",
                storage_key=storage_key,
                work_id=_WORK_ID,
            ),
            SimpleNamespace(),
            auth=SimpleNamespace(user=SimpleNamespace(id="owner-1")),
        )

    assert exc.value.status_code == 422
    assert removed == [storage_key]
