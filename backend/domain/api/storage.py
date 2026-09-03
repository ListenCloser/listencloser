"""Storage response normalization shared by resource routes."""

from urllib.parse import urlsplit, urlunsplit

from settings import SupabaseSettings


def _public_storage_url(value: str) -> str:
    """Expose provider resources through the configured browser-visible origin."""
    public_url = SupabaseSettings.from_environment().public_url
    if not public_url:
        return value

    public = urlsplit(public_url)
    if not public.scheme or not public.netloc:
        raise ValueError("SUPABASE_PUBLIC_URL must include scheme and host")

    signed = urlsplit(value)
    return urlunsplit((public.scheme, public.netloc, signed.path, signed.query, signed.fragment))


def signed_url(storage_response) -> str:
    """Normalize the signed-URL response shape across supabase-py releases."""
    data = getattr(storage_response, "data", storage_response) or {}
    if isinstance(data, dict):
        value = data.get("signedURL") or data.get("signedUrl") or data.get("signed_url")
        if value:
            return _public_storage_url(str(value))
    raise ValueError("Storage provider did not return a signed URL")
