"""Run a production-image PGMQ worker saturation matrix without changing runtime policy."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_TERMINAL = {"succeeded", "failed", "cancelled"}
_CONTAINER = "listencloser-saturation-worker"


def _run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, check=check, capture_output=True, text=True)
    return result.stdout.strip()


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _parse_bytes(value: str) -> float:
    token = value.strip().split()[0]
    units = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "KiB": 1024,
        "MB": 1000**2,
        "MiB": 1024**2,
        "GB": 1000**3,
        "GiB": 1024**3,
    }
    for unit in sorted(units, key=len, reverse=True):
        if token.endswith(unit):
            return float(token[: -len(unit)]) * units[unit]
    return float(token)


def _rest_jobs(job_ids: list[str]) -> list[dict[str, Any]]:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    ids = ",".join(job_ids)
    query = urllib.parse.urlencode(
        {
            "select": "id,stage,created_at,started_at,completed_at,retry_count,error_message",
            "id": f"in.({ids})",
        }
    )
    request = urllib.request.Request(
        f"{base}/rest/v1/jobs?{query}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def _worker_ready() -> bool:
    try:
        payload = json.loads(
            _run("docker", "exec", _CONTAINER, "cat", "/tmp/listencloser-worker.json")
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False
    return (
        payload.get("status") == "running"
        and "understand:1.0" in (payload.get("capabilities") or [])
    )


def _container_state() -> dict[str, Any]:
    raw = _run(
        "docker",
        "inspect",
        "--format",
        "{{json .State}}",
        _CONTAINER,
        check=False,
    )
    if not raw:
        return {"exists": False}
    state = json.loads(raw)
    return {
        "exists": True,
        "running": bool(state.get("Running")),
        "exit_code": state.get("ExitCode"),
        "oom_killed": bool(state.get("OOMKilled")),
    }


def _resource_sample() -> dict[str, float] | None:
    raw = _run(
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{json .}}",
        _CONTAINER,
        check=False,
    )
    if not raw:
        return None
    record = json.loads(raw)
    memory = str(record.get("MemUsage", "0 B")).split("/", 1)[0].strip()
    return {
        "cpu_percent": float(str(record.get("CPUPerc", "0")).rstrip("%") or 0),
        "rss_bytes": _parse_bytes(memory),
    }


def _runtime_identity() -> dict[str, Any]:
    code = (
        "import importlib.metadata as m,json,platform,sys;"
        "from engines.registry import get_beat_engine,get_harmony_engine;"
        "defv=lambda n: m.version(n) if any(d.metadata.get('Name')==n for d in m.distributions()) else None;"
        "print(json.dumps({"
        "'python':sys.version.split()[0],"
        "'platform':platform.platform(),"
        "'beat_engine':get_beat_engine().provenance.to_dict(),"
        "'harmony_engine':get_harmony_engine().provenance.to_dict(),"
        "'tensorflow':defv('tensorflow-cpu'),"
        "'torch':defv('torch')"
        "},sort_keys=True))"
    )
    try:
        return json.loads(_run("docker", "exec", _CONTAINER, "python", "-c", code).splitlines()[-1])
    except Exception as exc:
        return {"identity_error": repr(exc)}


def _fixture_duration_seconds(path_in_container: str) -> float:
    raw = _run(
        "docker",
        "exec",
        _CONTAINER,
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path_in_container,
    )
    return float(raw)


def _start_worker(image: str, fixture: Path, concurrency: int) -> None:
    _run("docker", "rm", "-f", _CONTAINER, check=False)
    args = [
        "docker",
        "run",
        "-d",
        "--name",
        _CONTAINER,
        "--network",
        "host",
        "-e",
        "SUPABASE_URL",
        "-e",
        "SUPABASE_SERVICE_ROLE_KEY",
        "-e",
        "HARMONY_ENGINE",
        "-e",
        f"WORKER_CONCURRENCY={concurrency}",
        "-v",
        f"{fixture.resolve()}:/tmp/worker-saturation.m4a:ro",
        "--entrypoint",
        "python",
        image,
        "worker.py",
    ]
    _run(*args)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        state = _container_state()
        if state.get("exists") and not state.get("running"):
            raise RuntimeError(f"worker exited during startup: {state}")
        if _worker_ready():
            return
        time.sleep(2)
    raise TimeoutError("worker did not publish a ready heartbeat")


def _seed_jobs(jobs: int) -> list[str]:
    raw = _run(
        "docker",
        "exec",
        _CONTAINER,
        "python",
        "evaluation/worker_saturation_seed.py",
        "--fixture",
        "/tmp/worker-saturation.m4a",
        "--jobs",
        str(jobs),
    )
    payload = json.loads(raw.splitlines()[-1])
    return [str(value) for value in payload["job_ids"]]


def _measure_point(
    *,
    image: str,
    fixture: Path,
    concurrency: int,
    jobs: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    _start_worker(image, fixture, concurrency)
    identity = _runtime_identity()
    fixture_seconds = _fixture_duration_seconds("/tmp/worker-saturation.m4a")
    batch_started_at = datetime.now(UTC)
    batch_started = time.monotonic()
    job_ids = _seed_jobs(jobs)
    samples: list[dict[str, Any]] = []
    latest_rows: list[dict[str, Any]] = []

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        state = _container_state()
        latest_rows = _rest_jobs(job_ids)
        now = datetime.now(UTC)
        queued_ages = [
            (now - created).total_seconds()
            for row in latest_rows
            if row.get("stage") == "queued"
            if (created := _iso(row.get("created_at"))) is not None
        ]
        resource = _resource_sample()
        samples.append(
            {
                "elapsed_seconds": time.monotonic() - batch_started,
                "queued": sum(row.get("stage") == "queued" for row in latest_rows),
                "running": sum(
                    row.get("stage") in {"claimed", "running"} for row in latest_rows
                ),
                "terminal": sum(row.get("stage") in _TERMINAL for row in latest_rows),
                "oldest_queued_age_seconds": max(queued_ages, default=0.0),
                **(resource or {}),
            }
        )
        if len(latest_rows) == len(job_ids) and all(
            row.get("stage") in _TERMINAL for row in latest_rows
        ):
            break
        if state.get("exists") and not state.get("running"):
            break
        time.sleep(2)

    elapsed = time.monotonic() - batch_started
    final_state = _container_state()
    if latest_rows and not all(row.get("stage") in _TERMINAL for row in latest_rows):
        latest_rows = _rest_jobs(job_ids)

    durations = []
    queue_waits = []
    for row in latest_rows:
        created = _iso(row.get("created_at"))
        started = _iso(row.get("started_at"))
        completed = _iso(row.get("completed_at"))
        if started and completed:
            durations.append((completed - started).total_seconds())
        if created and started:
            queue_waits.append((started - created).total_seconds())

    succeeded = sum(row.get("stage") == "succeeded" for row in latest_rows)
    failed = sum(row.get("stage") == "failed" for row in latest_rows)
    cancelled = sum(row.get("stage") == "cancelled" for row in latest_rows)
    retries = sum(int(row.get("retry_count") or 0) for row in latest_rows)
    cpu = [float(sample["cpu_percent"]) for sample in samples if "cpu_percent" in sample]
    rss = [float(sample["rss_bytes"]) for sample in samples if "rss_bytes" in sample]
    steady_rss = statistics.median(rss[-3:]) if rss else None
    audio_minutes = succeeded * fixture_seconds / 60.0

    log_path = Path(f"performance-results/worker-saturation-c{concurrency}.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logs = subprocess.run(
        ["docker", "logs", _CONTAINER],
        capture_output=True,
        text=True,
    )
    log_path.write_text(logs.stdout + logs.stderr, encoding="utf-8")
    _run("docker", "rm", "-f", _CONTAINER, check=False)

    return {
        "concurrency": concurrency,
        "jobs_attempted": jobs,
        "jobs_succeeded": succeeded,
        "jobs_failed": failed,
        "jobs_cancelled": cancelled,
        "retry_count": retries,
        "batch_started_at": batch_started_at.isoformat(),
        "wall_seconds": elapsed,
        "fixture_duration_seconds": fixture_seconds,
        "audio_minutes_succeeded": audio_minutes,
        "audio_minutes_per_wall_minute": audio_minutes / (elapsed / 60.0) if elapsed else None,
        "jobs_per_hour": succeeded / (elapsed / 3600.0) if elapsed else None,
        "job_duration_seconds": {
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "samples": len(durations),
        },
        "queue_wait_seconds": {
            "p50": _percentile(queue_waits, 0.50),
            "p95": _percentile(queue_waits, 0.95),
            "samples": len(queue_waits),
        },
        "oldest_queued_age_seconds_peak": max(
            (float(sample["oldest_queued_age_seconds"]) for sample in samples),
            default=0.0,
        ),
        "cpu_percent": {
            "mean": statistics.fmean(cpu) if cpu else None,
            "p95": _percentile(cpu, 0.95),
            "peak": max(cpu) if cpu else None,
        },
        "rss_bytes": {
            "peak": max(rss) if rss else None,
            "steady": steady_rss,
        },
        "worker_running_at_measurement_end": final_state.get("running", False),
        "worker_exit_code": final_state.get("exit_code"),
        "worker_oom_killed": final_state.get("oom_killed", False),
        "runtime_identity": identity,
        "samples": samples,
        "jobs": latest_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="listencloser-worker-saturation")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--jobs-per-point", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=int, default=420)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4])
    args = parser.parse_args()

    required = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "HARMONY_ENGINE"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"missing required environment: {', '.join(missing)}")

    results = []
    try:
        for concurrency in args.concurrency:
            results.append(
                _measure_point(
                    image=args.image,
                    fixture=args.fixture,
                    concurrency=concurrency,
                    jobs=args.jobs_per_point,
                    timeout_seconds=args.timeout_seconds,
                )
            )
    finally:
        _run("docker", "rm", "-f", _CONTAINER, check=False)

    report = {
        "schema_version": 1,
        "scenario": "pgmq_understand_worker_saturation",
        "release_sha": os.environ.get("GITHUB_SHA"),
        "fixture": args.fixture.name,
        "jobs_per_point": args.jobs_per_point,
        "concurrency_points": args.concurrency,
        "thresholds_enforced": False,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
