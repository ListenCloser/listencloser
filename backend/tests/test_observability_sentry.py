import logging

import sentry_sdk

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
            "traces_sample_rate": 0.25,
            "send_default_pii": False,
            "release": "worker@abc123",
        }
    ]


def test_init_sentry_preserves_api_default_release(monkeypatch):
    _clear_sentry_env(monkeypatch)
    monkeypatch.setenv("SENTRY_DSN_BACKEND", "https://backend@example.invalid/2")
    calls = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    initialized = init_sentry(
        logging.getLogger("test"),
        default_release="backend@2.0.0",
    )

    assert initialized is True
    assert calls == [
        {
            "dsn": "https://backend@example.invalid/2",
            "environment": "production",
            "traces_sample_rate": 0.1,
            "send_default_pii": False,
            "release": "backend@2.0.0",
        }
    ]
