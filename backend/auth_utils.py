import os
import threading

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
security = HTTPBearer(auto_error=False)

_sb_client = None
_sb_lock = threading.Lock()


def get_supabase_client():
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    with _sb_lock:
        if _sb_client is not None:
            return _sb_client
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        _sb_client = create_client(url, key)
        return _sb_client


def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=500, detail="Auth not configured")
    try:
        user = sb.auth.get_user(credentials.credentials)
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from None


def verify_token_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if not credentials:
        return None
    sb = get_supabase_client()
    if not sb:
        return None
    try:
        return sb.auth.get_user(credentials.credentials)
    except Exception:
        return None
