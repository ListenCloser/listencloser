"""Process-local service-role Supabase client ownership.

The API and repository layers use the same backend service-role credentials.
Keep construction lazy so import-only tooling/tests do not require runtime
configuration, but own the singleton in one module so auth/storage/repository
callers cannot silently drift onto separate client instances or configuration.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

_service_role_client: Client | None = None
_service_role_lock = threading.Lock()


def _build_service_role_client(url: str, key: str) -> Client:
    # Keep the relatively heavy Supabase import lazy, matching the previous
    # auth-utils behavior for import-only tools and tests.
    from supabase import create_client

    return create_client(url, key)


def get_service_role_client() -> Client | None:
    """Return the one lazy service-role client for this process, if configured."""
    global _service_role_client

    if _service_role_client is not None:
        return _service_role_client

    with _service_role_lock:
        if _service_role_client is not None:
            return _service_role_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None

        _service_role_client = _build_service_role_client(url, key)
        return _service_role_client
