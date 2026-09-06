"""Typed runtime configuration seams for backend process composition.

Deployment owns effective production values. These small settings groups own only
application parsing, validation, defaults, and secret-safe representation.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class _RuntimeSettings(BaseSettings):
    """Shared BaseSettings policy without creating a process-global singleton."""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=None,
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )


class SupabaseSettings(_RuntimeSettings):
    """Shared server-side Supabase credentials."""

    url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    public_url: str | None = Field(default=None, validation_alias="SUPABASE_PUBLIC_URL")
    service_role_key: SecretStr | None = Field(
        default=None,
        validation_alias="SUPABASE_SERVICE_ROLE_KEY",
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


class WorkerSettings(_RuntimeSettings):
    """Process-level worker settings with application-owned validation."""

    concurrency: int = Field(default=1, ge=1, validation_alias="WORKER_CONCURRENCY")


class ObservabilitySettings(_RuntimeSettings):
    """Shared API/worker observability values; exporters remain optional."""

    sentry_dsn: SecretStr | None = Field(default=None, validation_alias="SENTRY_DSN_BACKEND")
    environment: str = Field(default="production", validation_alias="SENTRY_ENV")
    traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        validation_alias="SENTRY_TRACES_SAMPLE_RATE",
    )
    release: str | None = Field(default=None, validation_alias="RELEASE")
    otel_service_name: str | None = Field(default=None, validation_alias="OTEL_SERVICE_NAME")
    otlp_endpoint: str | None = Field(
        default=None,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    def release_or(self, default: str) -> str:
        return self.release or default

    def service_name_or(self, default: str) -> str:
        return self.otel_service_name or default


class EngineSettings(_RuntimeSettings):
    """Default engine selections; explicit per-request selections still win."""

    transcription: str = Field(
        default="basic_pitch",
        validation_alias="TRANSCRIPTION_ENGINE",
    )
    beat: str = Field(default="beat_this", validation_alias="BEAT_ENGINE")
    notation: str = Field(default="musescore", validation_alias="NOTATION_ENGINE")
    harmony: str = Field(default="music21", validation_alias="HARMONY_ENGINE")
    melody: str = Field(default="lstom", validation_alias="MELODY_ENGINE")
    theory: str = Field(default="theory_interpreter", validation_alias="THEORY_ENGINE")
