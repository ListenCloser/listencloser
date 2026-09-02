from __future__ import annotations

import pytest
from pydantic import ValidationError

from settings import WorkerSettings


def test_worker_settings_default_to_one_process_worker():
    assert WorkerSettings.from_environment({}).concurrency == 1


def test_worker_settings_parse_positive_concurrency():
    assert WorkerSettings.from_environment({"WORKER_CONCURRENCY": "4"}).concurrency == 4


@pytest.mark.parametrize("value", ["0", "-1", "many", ""])
def test_worker_settings_reject_invalid_concurrency(value: str):
    with pytest.raises(ValidationError):
        WorkerSettings.from_environment({"WORKER_CONCURRENCY": value})
