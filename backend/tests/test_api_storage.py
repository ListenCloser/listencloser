from __future__ import annotations

import pytest

from domain.api.storage import signed_url


def test_signed_url_preserves_provider_origin_without_public_override(monkeypatch):
    monkeypatch.delenv("SUPABASE_PUBLIC_URL", raising=False)
    value = "http://supabase_kong_realstack:8000/storage/v1/object/sign/artifacts/file?token=abc"

    assert signed_url({"signedURL": value}) == value


def test_signed_url_uses_browser_visible_supabase_origin(monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "http://127.0.0.1:54321")
    path = "/storage/v1/object/sign/artifacts/file.musicxml?token=abc"
    provider_url = f"http://supabase_kong_realstack:8000{path}"
    expected_url = f"http://127.0.0.1:54321{path}"

    assert signed_url({"signedURL": provider_url}) == expected_url


def test_signed_url_rejects_invalid_public_origin(monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLIC_URL", "not-an-origin")

    with pytest.raises(ValueError, match="SUPABASE_PUBLIC_URL must include scheme and host"):
        signed_url({"signedURL": "http://supabase_kong_realstack:8000/storage/v1/object/sign/a"})
