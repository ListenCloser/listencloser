"""Storage response normalization shared by resource routes."""


def signed_url(storage_response) -> str:
    """Normalize the signed-URL response shape across supabase-py releases."""
    data = getattr(storage_response, "data", storage_response) or {}
    if isinstance(data, dict):
        value = data.get("signedURL") or data.get("signedUrl") or data.get("signed_url")
        if value:
            return str(value)
    raise ValueError("Storage provider did not return a signed URL")
