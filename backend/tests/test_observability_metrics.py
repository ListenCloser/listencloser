from __future__ import annotations

import observability


def test_http_metric_attributes_use_route_template_not_resource_id() -> None:
    resource_id = "6acdb10f-95d5-4f2f-8591-8fa1d2221504"
    attributes = observability.http_metric_attributes(
        "get",
        "/api/v1/works/{work_id}",
        200,
    )

    assert attributes == {
        "http.request.method": "GET",
        "http.route": "/api/v1/works/{work_id}",
        "http.response.status_class": "2xx",
    }
    assert resource_id not in str(attributes)


def test_http_metric_attributes_bound_error_dimensions() -> None:
    assert observability.http_metric_attributes("POST", "", 404) == {
        "http.request.method": "POST",
        "http.route": "unmatched",
        "http.response.status_class": "4xx",
    }
    assert (
        observability.http_metric_attributes("POST", "/health", 503)["http.response.status_class"]
        == "5xx"
    )


def test_job_metric_attributes_expose_only_capability_and_outcome() -> None:
    attributes = observability.job_metric_attributes("understand:1.0", "succeeded")

    assert attributes == {
        "job.capability": "understand:1.0",
        "job.outcome": "succeeded",
    }
    assert "job_id" not in attributes
    assert "work_id" not in attributes
    assert "user_id" not in attributes


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def add(self, value: float, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((value, attributes or {}))

    def record(self, value: float, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((value, attributes or {}))


def test_record_http_request_clamps_negative_duration(monkeypatch) -> None:
    counter = _Recorder()
    histogram = _Recorder()
    monkeypatch.setattr(observability, "_http_metrics", (counter, histogram))

    observability.record_http_request("GET", "/health", 200, -12.0)

    assert counter.calls == [
        (
            1,
            {
                "http.request.method": "GET",
                "http.route": "/health",
                "http.response.status_class": "2xx",
            },
        )
    ]
    assert histogram.calls == [
        (
            0.0,
            {
                "http.request.method": "GET",
                "http.route": "/health",
                "http.response.status_class": "2xx",
            },
        )
    ]


def test_record_job_execution_uses_bounded_attributes(monkeypatch) -> None:
    counter = _Recorder()
    histogram = _Recorder()
    orphans = _Recorder()
    monkeypatch.setattr(observability, "_job_metrics", (counter, histogram, orphans))

    observability.record_job_execution("transcribe:1.0", "retry", 2.5)
    observability.record_orphans_recovered(3)

    expected_attributes = {
        "job.capability": "transcribe:1.0",
        "job.outcome": "retry",
    }
    assert counter.calls == [(1, expected_attributes)]
    assert histogram.calls == [(2.5, expected_attributes)]
    assert orphans.calls == [(3, {})]
