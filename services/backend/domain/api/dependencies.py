"""Small request-context dependencies shared by domain API resource routers."""

from fastapi import HTTPException

from domain.repositories import get_supabase


def owner_id(auth) -> str:
    return auth.user.id


def supabase_client():
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return sb
