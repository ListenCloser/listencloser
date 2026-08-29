from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import auth_utils
import domain.repositories as repositories


def test_auth_and_repositories_return_the_same_process_client(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(repositories, "_sb_client", sentinel)

    assert repositories.get_supabase() is sentinel
    assert auth_utils.get_supabase_client() is sentinel


def test_shared_client_is_constructed_once_under_concurrent_first_access(monkeypatch):
    sentinel = object()
    constructed: list[tuple[str, str]] = []

    def fake_create_client(url: str, key: str):
        # Give competing callers a chance to reach the lock while the first
        # construction is in progress.
        time.sleep(0.02)
        constructed.append((url, key))
        return sentinel

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    monkeypatch.setattr(repositories, "_sb_client", None)
    monkeypatch.setattr(repositories, "create_client", fake_create_client)

    with ThreadPoolExecutor(max_workers=8) as pool:
        clients = list(pool.map(lambda _: repositories.get_supabase(), range(16)))

    assert clients == [sentinel] * 16
    assert constructed == [
        ("https://project.supabase.invalid", "service-role-test-key")
    ]
    assert auth_utils.get_supabase_client() is sentinel


def test_missing_service_role_configuration_stays_unconfigured(monkeypatch):
    create_client = Mock()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(repositories, "_sb_client", None)
    monkeypatch.setattr(repositories, "create_client", create_client)

    assert repositories.get_supabase() is None
    assert auth_utils.get_supabase_client() is None
    create_client.assert_not_called()
