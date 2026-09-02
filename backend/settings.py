"""Typed runtime configuration seams for backend process composition.

Keep settings construction explicit and cheap to override in tests. Deployment still
owns effective production values; these models own parsing and validation only.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SupabaseSettings(BaseModel):
    """Shared server-side Supabase credentials parsed from process environment."""

    model_config = ConfigDict(frozen=True)

    url: str | None = None
    service_role_key: SecretStr | None = None

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> SupabaseSettings:
        source = os.environ if environ is None else environ
        return cls(
            url=source.get("SUPABASE_URL"),
            service_role_key=source.get("SUPABASE_SERVICE_ROLE_KEY"),
        )

    @property
    def credentials(self) -> tuple[str, str] | None:
        """Return usable credentials while preserving the existing unconfigured state."""
        if not self.url or self.service_role_key is None:
            return None
        key = self.service_role_key.get_secret_value()
        if not key:
            return None
        return self.url, key


class WorkerSettings(BaseModel):
    """Process-level worker settings with application-owned validation."""

    model_config = ConfigDict(frozen=True)

    concurrency: int = Field(default=1, ge=1)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> WorkerSettings:
        source = os.environ if environ is None else environ
        raw_concurrency = source.get("WORKER_CONCURRENCY")
        if raw_concurrency is None:
            return cls()
        return cls(concurrency=raw_concurrency)
