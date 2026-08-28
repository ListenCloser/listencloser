from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from domain.upload_api import (
    _audio_descriptor,
    _pending_storage_key,
    _signed_upload_token,
    _validate_pending_storage_key,
)


def test_pending_storage_key_is_owner_and_project_scoped():
    project_id = UUID("11111111-1111-1111-1111-111111111111")
    key = _pending_storage_key("user-123", project_id, "m4a")

    _validate_pending_storage_key(key, "user-123", project_id, "m4a")
    assert key.startswith(f"user-123/{project_id}/pending/")
    assert key.endswith(".m4a")


@pytest.mark.parametrize(
    "key",
    [
        "other-user/11111111-1111-1111-1111-111111111111/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav",
        "user-123/22222222-2222-2222-2222-222222222222/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav",
        "user-123/11111111-1111-1111-1111-111111111111/pending/../escape.wav",
        "user-123/11111111-1111-1111-1111-111111111111/not-pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav",
    ],
)
def test_pending_storage_key_rejects_cross_scope_and_traversal(key):
    project_id = UUID("11111111-1111-1111-1111-111111111111")

    with pytest.raises(HTTPException) as exc:
        _validate_pending_storage_key(key, "user-123", project_id, "wav")

    assert exc.value.status_code == 400


def test_audio_descriptor_preserves_existing_size_ceiling(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "16")

    assert _audio_descriptor("take.wav", 16, "audio/wav") == ("wav", "audio/x-wav")
    with pytest.raises(HTTPException) as exc:
        _audio_descriptor("take.wav", 17, "audio/wav")
    assert exc.value.status_code == 413


def test_audio_descriptor_rejects_paths_and_unsupported_formats(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")

    with pytest.raises(HTTPException) as path_exc:
        _audio_descriptor("../take.wav", 1, "audio/wav")
    assert path_exc.value.status_code == 400

    with pytest.raises(HTTPException) as format_exc:
        _audio_descriptor("take.exe", 1, "application/octet-stream")
    assert format_exc.value.status_code == 415


def test_signed_upload_token_normalizes_supported_response_shapes():
    assert _signed_upload_token({"token": "dict-token"}) == "dict-token"
    assert _signed_upload_token(SimpleNamespace(token="object-token")) == "object-token"


def test_pending_storage_key_requires_matching_extension():
    project_id = UUID("11111111-1111-1111-1111-111111111111")
    key = "user-123/11111111-1111-1111-1111-111111111111/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav"

    with pytest.raises(HTTPException) as exc:
        _validate_pending_storage_key(key, "user-123", project_id, "mp3")

    assert exc.value.status_code == 400
