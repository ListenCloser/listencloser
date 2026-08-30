"""Ask provider failures emit bounded, request-correlated operational logs."""

from __future__ import annotations

import logging
import time

from fastapi import Request

from ask.api import _log_ask_failure
from ask.config import LLMSettings


def test_ask_failure_log_carries_request_id_and_failure_class(caplog) -> None:
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-request-id", b"ask-req-123")],
        }
    )
    settings = LLMSettings(
        base_url="https://example.com/v1",
        api_key="secret",
        model="model-x",
    )

    with caplog.at_level(logging.WARNING, logger="ask.api"):
        _log_ask_failure(
            request,
            settings,
            time.perf_counter(),
            kind="timeout",
            status=504,
        )

    record = caplog.records[-1]
    assert record.message == "ask_failed"
    assert record.req_id == "ask-req-123"
    assert record.failure_kind == "timeout"
    assert record.status == 504
    assert record.model == "model-x"
    assert record.duration_ms >= 0
