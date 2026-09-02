from __future__ import annotations

import pytest
from pydantic import ValidationError

from settings import SupabaseSettings, WorkerSettings


def test_supabase_settings_preserve_unconfigured_behavior_for_missing_or_partial_env():
    assert SupabaseSettings.from_environment({}) is None
    assert SupabaseSettings.from_environment({"SUPABASE_URL": "https://project.invalid"}) is None
    assert (
        SupabaseSettings.from_environment({"SUPABASE_SERVICE_ROLE_KEY": "service-role-secret"})
        is None
    )
    assert (
        SupabaseSettings.from_environment(
            {
                "SUPABASE_URL": "",
                "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
            }
        )
        is None
    )


def test_supabase_service_role_key_is_secret_safe_in_repr():
    settings = SupabaseSettings.from_environment(
        {
            "SUPABASE_URL": "https://project.invalid",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
        }
    )

    assert settings is not None
    assert settings.url == "https://project.invalid"
    assert settings.service_role_key.get_secret_value() == "service-role-secret"
    assert "service-role-secret" not in repr(settings)


def test_worker_settings_default_to_one_process_worker():
    assert WorkerSettings.from_environment({}).concurrency == 1


def test_worker_settings_parse_positive_concurrency():
    assert WorkerSettings.from_environment({"WORKER_CONCURRENCY": "4"}).concurrency == 4


@pytest.mark.parametrize("value", ["0", "-1", "many", ""])
def test_worker_settings_reject_invalid_concurrency(value: str):
    with pytest.raises(ValidationError):
        WorkerSettings.from_environment({"WORKER_CONCURRENCY": value})
