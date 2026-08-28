import builtins
import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastAPIIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from observability import init_sentry


def _clear_sentry_env(monkeypatch):
    for name in (
        "SENTRY_DSN_BACKEND",
        "SENTRY_DSN",
        "SENTRY_ENV",
        "SENTRY_TRACES_SAMPLE_RATE",
        "RELEASE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_init_sentry_is_disabled_without_dsn(monkeypatch):
    _clear_sentry_env(monkeypatch)
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    assert init_sentry(logging.getLogger("test")) is False
    assert calls == []


def test_init_sentry_uses_shared_worker_environment_contract(monkeypatch):
    _clear_sentry_env(monkeypatch)
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setenv("SENTRY_ENV", "staging")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("RELEASE", "worker@abc123")
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    assert init_sentry(logging.getLogger("test")) is True
    assert calls == [
        {
            "dsn": "https://public@example.invalid/1",
            "environment": "staging",
            "integrations": None,
            "traces_sample_rate": 0.25,
            "send_default_pii": False,
            "release": "worker@abc123",
        }
    ]


def test_worker_sentry_does_not_import_api_framework_integrations(monkeypatch):
    _clear_sentry_env(monkeypatch)
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setattr(sentry_sdk, "init", lambda **_kwargs: None)

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {
            "sentry_sdk.integrations.fastapi",
            "sentry_sdk.integrations.starlette",
        }:
            raise AssertionError(f"worker unexpectedly imported {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert init_sentry(logging.getLogger("test")) is True


def test_init_sentry_preserves_api_integrations_and_default_release(monkeypatch):
    _clear_sentry_env(monkeypatch)
    monkeypatch.setenv("SENTRY_DSN_BACKEND", "https://backend@example.invalid/2")
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    assert init_sentry(
        logging.getLogger("test"),
        default_release="backend@2.0.0",
        include_fastapi_integrations=True,
    ) is True

    kwargs = calls[0]
    assert kwargs["dsn"] == "https://backend@example.invalid/2"
    assert kwargs["environment"] == "production"
    assert kwargs["traces_sample_rate"] == 0.1
    assert kwargs["send_default_pii"] is False
    assert kwargs["release"] == "backend@2.0.0"
    assert any(isinstance(item, StarletteIntegration) for item in kwargs["integrations"])
    assert any(isinstance(item, FastAPIIntegration) for item in kwargs["integrations"])
