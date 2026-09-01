import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from httpx import RequestError
from slowapi import Limiter
from slowapi.util import get_remote_address
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthInvalidJwtError,
    AuthRetryableError,
    AuthSessionMissingError,
    AuthUnknownError,
)

from domain.repositories import get_supabase

logger = logging.getLogger("auth")


@dataclass(frozen=True, slots=True)
class AuthUser:
    """Minimal authenticated user identity exposed to API handlers."""

    id: str


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    """Provider-neutral authenticated identity for authorization checks."""

    user: AuthUser
    claims: Mapping[str, Any]


def _rate_limit_identity(request: Request) -> str:
    """Isolate authenticated quotas even when requests share a proxy address."""
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip().encode("utf-8")
        if token:
            return f"auth:{hashlib.sha256(token).hexdigest()}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_limit_identity, default_limits=["60/minute"])
security = HTTPBearer(auto_error=False)


def _provider_unavailable(exc: Exception) -> bool:
    if isinstance(exc, AuthRetryableError | AuthUnknownError | RequestError):
        return True
    return isinstance(exc, AuthApiError) and (exc.status == 429 or exc.status >= 500)


def _invalid_auth_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        AuthInvalidCredentialsError | AuthInvalidJwtError | AuthSessionMissingError,
    ):
        return True
    return isinstance(exc, AuthApiError) and not _provider_unavailable(exc)


def _invalid_credentials(*, optional: bool) -> None:
    if optional:
        return None
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    ) from None


def _principal_from_claims(response, *, optional: bool) -> AuthPrincipal | None:
    claims = response.get("claims") if isinstance(response, dict) else None
    subject = claims.get("sub") if isinstance(claims, dict) else None
    if not isinstance(subject, str) or not subject:
        return _invalid_credentials(optional=optional)
    return AuthPrincipal(user=AuthUser(id=subject), claims=claims)


def _verify_supabase_token(sb, token: str, *, optional: bool) -> AuthPrincipal | None:
    try:
        # get_claims verifies the JWT against Supabase signing keys. With
        # asymmetric keys the SDK can use cached JWKS instead of making an Auth
        # API request for every application request. Symmetric/legacy signing
        # is handled by the SDK's server-validation fallback.
        response = sb.auth.get_claims(token)
    except Exception as exc:
        if _provider_unavailable(exc):
            logger.warning(
                "Authentication provider unavailable during token verification: %s",
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from None
        if _invalid_auth_error(exc):
            return _invalid_credentials(optional=optional)

        logger.error(
            "Unexpected authentication verification failure: %s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication verification failed",
        ) from None

    return _principal_from_claims(response, optional=optional)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthPrincipal:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=500, detail="Auth not configured")
    principal = _verify_supabase_token(sb, credentials.credentials, optional=False)
    if principal is None:  # pragma: no cover - required auth never returns None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return principal


def verify_token_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthPrincipal | None:
    if not credentials:
        return None
    sb = get_supabase()
    if not sb:
        return None
    return _verify_supabase_token(sb, credentials.credentials, optional=True)
