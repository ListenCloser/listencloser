from __future__ import annotations

import pytest
from pydantic import ValidationError

from settings import SupabaseSettings, WorkerSettings


def test_worker_settings_default_to_one_process_worker():
    assert WorkerSettings.from_environment({}).concurrency == 1


def test_worker_settings_parse_positive_concurrency():
    assert WorkerSettings.from_environment({"WORKER_CONCURRENCY": "4"}).concurrency == 4


@pytest.mark.parametrize("value", ["0", "-1", "many", ""])
def test_worker_settings_reject_invalid_concurrency(value: str):
    with pytest.raises(ValidationError):
        WorkerSettings.from_environment({"WORKER_CONCURRENCY": value})


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
def test_supabase_settings_preserve_unconfigured_credentials(
    environment: dict[str, str],
):
    assert SupabaseSettings.from_environment(environment).credentials is None


def test_supabase_settings_mask_service_role_key_in_repr():
    settings = SupabaseSettings.from_environment(
        {
            "SUPABASE_URL": "https://project.supabase.invalid",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-test-key",
        }
    )

    assert settings.credentials == (
        "https://project.supabase.invalid",
        "service-role-test-key",
    )
    assert "service-role-test-key" not in repr(settings)
    assert "**********" in repr(settings)
