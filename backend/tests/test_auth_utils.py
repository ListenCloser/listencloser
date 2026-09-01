from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError, AuthRetryableError

import auth_utils


def _credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")


def _claims_result(subject: str = "user-123") -> dict:
    return {
        "claims": {"sub": subject, "role": "authenticated"},
        "headers": {"alg": "ES256"},
        "signature": b"verified",
    }


def _client_with_result(result=None, error: Exception | None = None):
    client = MagicMock()
    if error is not None:
        client.auth.get_claims.side_effect = error
    else:
        client.auth.get_claims.return_value = result
    return client


def _install_client(monkeypatch, client) -> None:
    monkeypatch.setattr(auth_utils, "get_supabase", lambda: client)


def test_verify_token_requires_credentials():
    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


def test_verify_token_returns_minimal_principal_from_verified_claims(monkeypatch):
    client = _client_with_result(_claims_result())
    _install_client(monkeypatch, client)

    principal = auth_utils.verify_token(_credentials())

    assert principal.user.id == "user-123"
    assert principal.claims["role"] == "authenticated"
    client.auth.get_claims.assert_called_once_with("test-token")
    client.auth.get_user.assert_not_called()


def test_verify_token_rejects_verified_claims_without_subject(monkeypatch):
    client = _client_with_result(
        {
            "claims": {"role": "authenticated"},
            "headers": {"alg": "ES256"},
            "signature": b"verified",
        }
    )
    _install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token(_credentials())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication credentials"


def test_verify_token_maps_invalid_auth_api_error_to_401(monkeypatch):
    client = _client_with_result(
        error=AuthApiError("provider detail must not leak", 401, "bad_jwt")
    )
    _install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token(_credentials())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication credentials"


@pytest.mark.parametrize(
    "error",
    [
        AuthRetryableError("upstream unavailable", 503),
        AuthApiError("rate limited", 429, "over_request_rate_limit"),
        AuthApiError("upstream failed", 503, "unexpected_failure"),
        httpx.ConnectError(
            "connection failed",
            request=httpx.Request("GET", "https://example.invalid/auth/v1/user"),
        ),
    ],
)
def test_verify_token_surfaces_provider_failures_as_503(monkeypatch, error):
    client = _client_with_result(error=error)
    _install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token(_credentials())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Authentication service unavailable"
    assert "upstream" not in exc_info.value.detail


def test_verify_token_surfaces_unexpected_failure_as_generic_500(monkeypatch):
    client = _client_with_result(error=ValueError("sensitive internal detail"))
    _install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token(_credentials())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Authentication verification failed"
    assert "sensitive" not in exc_info.value.detail


def test_optional_auth_without_credentials_is_anonymous():
    assert auth_utils.verify_token_optional(None) is None


def test_optional_auth_keeps_invalid_token_compatible_with_anonymous(monkeypatch):
    client = _client_with_result(error=AuthApiError("invalid token", 401, "bad_jwt"))
    _install_client(monkeypatch, client)

    assert auth_utils.verify_token_optional(_credentials()) is None


def test_optional_auth_without_subject_is_anonymous(monkeypatch):
    client = _client_with_result(
        {
            "claims": {"role": "authenticated"},
            "headers": {"alg": "ES256"},
            "signature": b"verified",
        }
    )
    _install_client(monkeypatch, client)

    assert auth_utils.verify_token_optional(_credentials()) is None


def test_optional_auth_does_not_hide_provider_failure(monkeypatch):
    client = _client_with_result(error=AuthRetryableError("provider unavailable", 503))
    _install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token_optional(_credentials())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Authentication service unavailable"


def test_optional_auth_surfaces_unexpected_failure_as_generic_500(monkeypatch):
    client = _client_with_result(error=RuntimeError("unexpected local failure"))
    _install_client(monkeypatch, client)

    with pytest.raises(HTTPException) as exc_info:
        auth_utils.verify_token_optional(_credentials())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Authentication verification failed"
