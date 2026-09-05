from __future__ import annotations

import pytest
from pydantic import ValidationError

from settings import EngineSettings, ObservabilitySettings, SupabaseSettings, WorkerSettings

_RUNTIME_ENV = (
    "SUPABASE_URL",
    "SUPABASE_PUBLIC_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "WORKER_CONCURRENCY",
    "SENTRY_DSN_BACKEND",
    "SENTRY_DSN",
    "SENTRY_ENV",
    "SENTRY_TRACES_SAMPLE_RATE",
    "RELEASE",
    "OTEL_SERVICE_NAME",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "TRANSCRIPTION_ENGINE",
    "BEAT_ENGINE",
    "NOTATION_ENGINE",
    "HARMONY_ENGINE",
    "MELODY_ENGINE",
    "THEORY_ENGINE",
)


@pytest.fixture(autouse=True)
def clear_runtime_environment(monkeypatch):
    for name in _RUNTIME_ENV:
        monkeypatch.delenv(name, raising=False)


def test_worker_settings_default_to_one_process_worker():
    assert WorkerSettings().concurrency == 1


def test_worker_settings_parse_positive_concurrency(monkeypatch):
    monkeypatch.setenv("WORKER_CONCURRENCY", "4")
    assert WorkerSettings().concurrency == 4


@pytest.mark.parametrize("value", ["0", "-1", "many", ""])
def test_worker_settings_reject_invalid_concurrency(monkeypatch, value: str):
    monkeypatch.setenv("WORKER_CONCURRENCY", value)
    with pytest.raises(ValidationError):
        WorkerSettings()


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"SUPABASE_URL": "https://project.supabase.invalid"},
        {"SUPABASE_SERVICE_ROLE_KEY": "service-role-test-key"},
        {
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-test-key",
        },
        {
            "SUPABASE_URL": "https://project.supabase.invalid",
            "SUPABASE_SERVICE_ROLE_KEY": "",
        },
    ],
)
def test_supabase_settings_preserve_unconfigured_credentials(monkeypatch, environment: dict[str, str]):
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    assert SupabaseSettings().credentials is None


def test_supabase_settings_mask_service_role_key_in_repr(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")

    settings = SupabaseSettings()

    assert settings.credentials == (
        "https://project.supabase.invalid",
        "service-role-test-key",
    )
    assert "service-role-test-key" not in repr(settings)
    assert "**********" in repr(settings)


def test_observability_settings_keep_optional_providers_disabled_by_default():
    settings = ObservabilitySettings()

    assert settings.sentry_dsn is None
    assert settings.otlp_endpoint is None
    assert settings.environment == "production"
    assert settings.traces_sample_rate == 0.1
    assert settings.release is None


def test_observability_settings_use_canonical_backend_sentry_alias(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://legacy@example.invalid/1")
    assert ObservabilitySettings().sentry_dsn is None

    monkeypatch.setenv("SENTRY_DSN_BACKEND", "https://backend@example.invalid/2")
    settings = ObservabilitySettings()

    assert settings.sentry_dsn is not None
    assert settings.sentry_dsn.get_secret_value() == "https://backend@example.invalid/2"
    assert "https://backend@example.invalid/2" not in repr(settings)


@pytest.mark.parametrize("value", ["-0.1", "1.1", "many", ""])
def test_observability_settings_reject_invalid_trace_sample_rate(monkeypatch, value: str):
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", value)
    with pytest.raises(ValidationError):
        ObservabilitySettings()


def test_engine_settings_preserve_current_defaults():
    settings = EngineSettings()

    assert settings.transcription == "basic_pitch"
    assert settings.beat == "beat_this"
    assert settings.notation == "musescore"
    assert settings.harmony == "music21"
    assert settings.melody == "lstom"
    assert settings.theory == "theory_interpreter"


def test_engine_settings_read_deployment_overrides(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTION_ENGINE", "transkun")
    monkeypatch.setenv("BEAT_ENGINE", "librosa")
    monkeypatch.setenv("NOTATION_ENGINE", "pm2s")
    monkeypatch.setenv("HARMONY_ENGINE", "lv_chordia")
    monkeypatch.setenv("MELODY_ENGINE", "skyline")
    monkeypatch.setenv("THEORY_ENGINE", "custom_theory")

    settings = EngineSettings()

    assert settings.transcription == "transkun"
    assert settings.beat == "librosa"
    assert settings.notation == "pm2s"
    assert settings.harmony == "lv_chordia"
    assert settings.melody == "skyline"
    assert settings.theory == "custom_theory"
