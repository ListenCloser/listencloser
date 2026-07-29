import base64

import pytest

import auth_utils
import main
from main import MAX_UPLOAD_BYTES, _now, _sanitize_fmt, _split_storage_path


class _FakeStorage:
    def __init__(self):
        self.store = {}

    def download(self, key):
        return self.store.get(key, b"")

    def upload(self, key, data, options=None):
        self.store[key] = data if isinstance(data, bytes) else data.read()
        return {"path": key}

    def get_public_url(self, key):
        return f"https://example.com/{key}"

    def from_(self, bucket):
        self._bucket = bucket
        return self


class _FakeSB:
    def __init__(self):
        self.storage = _FakeStorage()
        self.auth = _FakeAuth()


class _FakeAuth:
    def get_user(self, token):
        return {"user": {"id": "test-user"}}


@pytest.fixture(autouse=True)
def _stub_supabase(monkeypatch):
    monkeypatch.setattr(auth_utils, "get_supabase_client", lambda: _FakeSB())


def _auth():
    return {"Authorization": "Bearer test-token"}


# --- pure guard units (no network) -----------------------------------------


def test_split_storage_path_library():
    bucket, key = _split_storage_path("library/6e177343-cf86-418d-ad55-bec73baa12b0/12345-song.wav")
    assert bucket == "library"
    assert key == "library/6e177343-cf86-418d-ad55-bec73baa12b0/12345-song.wav"


def test_split_storage_path_midi():
    bucket, key = _split_storage_path("midi/user123/track.mid")
    assert bucket == "midi"
    assert key == "user123/track.mid"


def test_split_storage_path_rejects_bad_prefix():
    with pytest.raises(main.HTTPException):
        _split_storage_path("bucket/file.wav")
    with pytest.raises(main.HTTPException):
        _split_storage_path("library")  # no key after prefix


def test_sanitize_fmt_strips_traversal():
    assert _sanitize_fmt("../../etc/passwd") == ".wav"
    assert _sanitize_fmt("WAV") == ".wav"


def test_now_returns_parseable_utc_iso():
    from datetime import datetime

    dt = datetime.fromisoformat(_now())
    assert dt.tzinfo is not None


def test_max_upload_bytes_default():
    assert MAX_UPLOAD_BYTES == 26214400


# --- endpoint-level guards (auth stubbed) -----------------------------------


def test_upload_library_rejects_oversized_payload(client):
    big = base64.b64encode(b"x" * (MAX_UPLOAD_BYTES + 1)).decode()
    r = client.post(
        "/music/library",
        headers=_auth(),
        json={"name": "big.wav", "fmt": "wav", "data_base64": big},
    )
    assert r.status_code == 413


def test_upload_library_rejects_bad_base64(client):
    r = client.post(
        "/music/library",
        headers=_auth(),
        json={"name": "x.wav", "fmt": "wav", "data_base64": "!!!notb64!!!"},
    )
    assert r.status_code == 400


def test_enhance_rejects_invalid_library_path(client):
    r = client.post(
        "/music/enhance", headers=_auth(), json={"library_path": "library/../../secret"}
    )
    assert r.status_code == 400


def test_transcribe_rejects_invalid_library_path(client):
    r = client.post("/music/transcribe", headers=_auth(), json={"library_path": "../escape"})
    assert r.status_code == 400


def test_analyze_requires_midi_base64(client):
    r = client.post("/music/analyze", headers=_auth(), json={})
    assert r.status_code == 422


def test_analyze_rejects_invalid_base64(client):
    r = client.post(
        "/music/analyze",
        headers=_auth(),
        json={"midi_base64": "!!!notb64!!!"},
    )
    assert r.status_code == 400


def test_analyze_rejects_oversize_midi(client):
    big = base64.b64encode(b"x" * (MAX_UPLOAD_BYTES + 1)).decode()
    r = client.post(
        "/music/analyze",
        headers=_auth(),
        json={"midi_base64": big},
    )
    assert r.status_code == 413


def test_analyze_rejects_invalid_library_path(client):
    r = client.post(
        "/music/analyze",
        headers=_auth(),
        json={"midi_base64": "not-valid"},
    )
    assert r.status_code == 400
