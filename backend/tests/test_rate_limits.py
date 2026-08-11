from starlette.requests import Request

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


def test_authenticated_rate_limits_do_not_collapse_users_behind_one_proxy():
    first = _rate_limit_identity(_request(token="user-a-token", host="vercel"))
    second = _rate_limit_identity(_request(token="user-b-token", host="vercel"))

    assert first.startswith("auth:")
    assert second.startswith("auth:")
    assert first != second
    assert "user-a-token" not in first


def test_unauthenticated_rate_limits_fall_back_to_remote_address():
    assert _rate_limit_identity(_request(host="203.0.113.9")) == "ip:203.0.113.9"
