#!/usr/bin/env python3
"""Provider-neutral HTTP benchmark for Platform V3 compute experiments.

This intentionally uses only the Python standard library. It is designed to
compare the same listencloser API release across Oracle, Cloud Run, Azure Container
Apps, or another HTTP container host without adding a provider SDK.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProbeResult:
    path: str
    status_code: int | None
    elapsed_ms: float
    ok: bool
    error: str | None = None


def percentile(values: Iterable[float], percentile_value: float) -> float | None:
    """Return a nearest-rank percentile, or ``None`` for an empty sequence."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    rank = max(1, math.ceil((percentile_value / 100.0) * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def probe_once(base_url: str, path: str, timeout: float) -> ProbeResult:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = Request(url, headers={"User-Agent": "listencloser-platform-benchmark/1"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit benchmark URL
            status = int(response.status)
            response.read(1024)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return ProbeResult(
            path=path,
            status_code=status,
            elapsed_ms=elapsed_ms,
            ok=200 <= status < 300,
        )
    except HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return ProbeResult(
            path=path,
            status_code=int(exc.code),
            elapsed_ms=elapsed_ms,
            ok=False,
            error=f"HTTP {exc.code}",
        )
    except (URLError, TimeoutError, OSError) as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return ProbeResult(
            path=path,
            status_code=None,
            elapsed_ms=elapsed_ms,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def run_probe(
    base_url: str,
    paths: list[str],
    requests_per_path: int,
    concurrency: int,
    timeout: float,
) -> list[ProbeResult]:
    work = [path for path in paths for _ in range(requests_per_path)]
    results: list[ProbeResult] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(probe_once, base_url, path, timeout) for path in work]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def summarize_results(results: list[ProbeResult]) -> dict:
    by_path: dict[str, list[ProbeResult]] = {}
    for result in results:
        by_path.setdefault(result.path, []).append(result)

    paths: dict[str, dict] = {}
    for path, path_results in sorted(by_path.items()):
        latencies = [result.elapsed_ms for result in path_results]
        successful = [result for result in path_results if result.ok]
        status_counts: dict[str, int] = {}
        errors: dict[str, int] = {}
        for result in path_results:
            status_key = str(result.status_code) if result.status_code is not None else "none"
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            if result.error:
                errors[result.error] = errors.get(result.error, 0) + 1

        paths[path] = {
            "requests": len(path_results),
            "successes": len(successful),
            "success_rate": len(successful) / len(path_results) if path_results else 0.0,
            "latency_ms": {
                "min": min(latencies) if latencies else None,
                "mean": statistics.fmean(latencies) if latencies else None,
                "p50": percentile(latencies, 50),
                "p95": percentile(latencies, 95),
                "p99": percentile(latencies, 99),
                "max": max(latencies) if latencies else None,
            },
            "status_counts": status_counts,
            "errors": errors,
        }

    return {"paths": paths}


def build_report(args: argparse.Namespace, results: list[ProbeResult]) -> dict:
    report = {
        "schema_version": 1,
        "measured_at": datetime.now(UTC).isoformat(),
        "target": {
            "label": args.label,
            "base_url": args.base_url.rstrip("/"),
            "paths": args.path,
        },
        "configuration": {
            "requests_per_path": args.requests,
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout,
        },
    }
    report.update(summarize_results(results))
    if args.include_samples:
        report["samples"] = [asdict(result) for result in results]
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark listencloser health endpoints on any HTTP container host."
    )
    parser.add_argument("base_url", help="Base API URL, e.g. https://api.example.com")
    parser.add_argument(
        "--path",
        action="append",
        default=None,
        help="Path to probe; repeat for multiple paths (default: /health/live and /health/ready)",
    )
    parser.add_argument("--requests", type=int, default=30, help="Requests per path")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent requests")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds")
    parser.add_argument("--label", default="unlabeled", help="Human-readable host/provider label")
    parser.add_argument("--output", type=Path, help="Optional JSON report destination")
    parser.add_argument(
        "--include-samples",
        action="store_true",
        help="Include individual request samples in JSON output",
    )
    args = parser.parse_args()
    args.path = args.path or ["/health/live", "/health/ready"]
    if args.requests < 1:
        parser.error("--requests must be >= 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    return args


def main() -> int:
    args = parse_args()
    results = run_probe(
        args.base_url,
        args.path,
        requests_per_path=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )
    report = build_report(args, results)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
