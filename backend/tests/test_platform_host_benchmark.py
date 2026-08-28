from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).parents[2] / "scripts" / "benchmark_api_host.py"
_SPEC = importlib.util.spec_from_file_location("benchmark_api_host", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
benchmark_api_host = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark_api_host)

ProbeResult = benchmark_api_host.ProbeResult
percentile = benchmark_api_host.percentile
summarize_results = benchmark_api_host.summarize_results


def test_percentile_uses_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 50) == 20.0
    assert percentile(values, 95) == 40.0
    assert percentile([], 95) is None


def test_summary_groups_paths_and_failures() -> None:
    results = [
        ProbeResult("/health/live", 200, 10.0, True),
        ProbeResult("/health/live", 200, 20.0, True),
        ProbeResult("/health/live", 503, 30.0, False, "HTTP 503"),
        ProbeResult("/health/ready", 200, 50.0, True),
    ]

    report = summarize_results(results)

    live = report["paths"]["/health/live"]
    assert live["requests"] == 3
    assert live["successes"] == 2
    assert live["success_rate"] == 2 / 3
    assert live["latency_ms"]["p50"] == 20.0
    assert live["latency_ms"]["p95"] == 30.0
    assert live["status_counts"] == {"200": 2, "503": 1}
    assert live["errors"] == {"HTTP 503": 1}

    ready = report["paths"]["/health/ready"]
    assert ready["success_rate"] == 1.0
    assert ready["latency_ms"]["p99"] == 50.0
