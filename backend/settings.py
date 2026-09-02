"""Typed runtime configuration seams for backend process composition.

Keep settings construction explicit and cheap to override in tests. Deployment still
owns effective production values; these models own parsing and validation only.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class _RuntimeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)


class SupabaseSettings(_RuntimeSettings):
    """Server-authority credentials used to construct the shared Supabase client."""

    url: str
    service_role_key: SecretStr

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> SupabaseSettings | None:
        source = os.environ if environ is None else environ
        url = source.get("SUPABASE_URL")
        service_role_key = source.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class WorkerSettings(_RuntimeSettings):
    """Process-level worker settings with application-owned validation."""

    concurrency: int = Field(default=1, ge=1)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> WorkerSettings:
        source = os.environ if environ is None else environ
        raw_concurrency = source.get("WORKER_CONCURRENCY")
        if raw_concurrency is None:
            return cls()
        return cls(concurrency=raw_concurrency)
