from unittest.mock import MagicMock

from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

import auth_utils
from auth_utils import _rate_limit_identity


def _request(*, token: str | None = None, host: str = "10.0.0.1") -> Request:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/workflows/understand",
            "headers": headers,
            "client": (host, 443),
        }
    )


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _verified_client(subject_by_token: dict[str, str]) -> MagicMock:
    client = MagicMock()
    client.auth.get_claims.side_effect = lambda token: {
        "claims": {"sub": subject_by_token[token], "role": "authenticated"},
        "headers": {"alg": "ES256"},
        "signature": b"verified",
    }
    return client


def test_different_valid_sessions_for_same_user_share_one_rate_limit_bucket(monkeypatch):
    client = _verified_client({"session-a": "user-123", "session-b": "user-123"})
    monkeypatch.setattr(auth_utils, "get_supabase", lambda: client)
    first_request = _request(token="session-a", host="vercel")
    second_request = _request(token="session-b", host="vercel")

    auth_utils.verify_token(first_request, _credentials("session-a"))
    auth_utils.verify_token(second_request, _credentials("session-b"))

    assert _rate_limit_identity(first_request) == "user:user-123"
    assert _rate_limit_identity(second_request) == "user:user-123"


def test_verified_users_do_not_collapse_behind_one_proxy(monkeypatch):
    client = _verified_client({"session-a": "user-a", "session-b": "user-b"})
    monkeypatch.setattr(auth_utils, "get_supabase", lambda: client)
    first_request = _request(token="session-a", host="vercel")
    second_request = _request(token="session-b", host="vercel")

    auth_utils.verify_token(first_request, _credentials("session-a"))
    auth_utils.verify_token(second_request, _credentials("session-b"))

    assert _rate_limit_identity(first_request) == "user:user-a"
    assert _rate_limit_identity(second_request) == "user:user-b"


def test_unverified_bearer_values_cannot_select_fresh_rate_limit_buckets():
    first = _rate_limit_identity(_request(token="unverified-a", host="203.0.113.9"))
    second = _rate_limit_identity(_request(token="unverified-b", host="203.0.113.9"))

    assert first == "ip:203.0.113.9"
    assert second == first
    assert "unverified" not in first


def test_unauthenticated_rate_limits_fall_back_to_remote_address():
    assert _rate_limit_identity(_request(host="203.0.113.9")) == "ip:203.0.113.9"
