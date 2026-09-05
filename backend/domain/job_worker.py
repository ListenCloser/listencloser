"""Transport-neutral durable job execution for listencloser.

The queue transport is intentionally outside this module. Production delivery is
owned by :class:`domain.pgmq_job_worker.PgmqJobWorker`; this class owns only the
product lifecycle that remains useful regardless of queue implementation:
handler dispatch, cancellation, progress, cache idempotency, retry policy, and
worker liveness.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from opentelemetry.trace import Status, StatusCode

from observability import get_tracer, record_job_execution

from .models import Capability, Job, JobLifecycle

logger = logging.getLogger("job_worker")
_tracer = get_tracer("listencloser-worker")


def _parse_datetime(val: Any) -> datetime | None:
    """Coerce a DB value into a timezone-aware ``datetime`` or ``None``."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val
    try:
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _parse_jsonb(val: Any) -> dict:
    """Ensure a JSONB column value is returned as a plain dict."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _parse_uuid_list(val: Any) -> list[UUID]:
    """Parse a Postgres ``uuid[]`` column into a list of ``UUID`` objects."""
    if val is None:
        return []
    if isinstance(val, list):
        out: list[UUID] = []
        for value in val:
            if value is None:
                continue
            try:
                out.append(UUID(str(value)))
            except (ValueError, AttributeError):
                continue
        return out
    return []


class JobWorker:
    """Execute durable Jobs delivered by a concrete queue transport.

    Subclasses provide ``_receive_next_job`` and ``_heartbeat_delivery``. The
    base class never claims Jobs, scans for abandoned queue ownership, or renews
    a Jobs-table transport lease.
    """

    def __init__(
        self,
        heartbeat_interval_sec: float = 10.0,
        poll_interval_sec: float = 1.0,
        max_workers: int = 4,
    ) -> None:
        self._worker_id = str(uuid4())
        self._started_at = datetime.now(UTC)
        self._heartbeat_interval = heartbeat_interval_sec
        self._poll_interval = poll_interval_sec
        self._max_workers = max_workers

        self._capabilities: dict[str, Callable[..., list[str]]] = {}
        self._running = False
        self._stop_event = threading.Event()

        self._client: Any = None
        self._client_lock = threading.Lock()
        self._in_flight: set[str] = set()
        self._in_flight_lock = threading.Lock()

    def _heartbeat_worker(self, status: str = "running") -> None:
        """Publish aggregate worker liveness without exposing job data."""
        heartbeat = {
            "worker_id": self._worker_id,
            "status": status,
            "capabilities": sorted(self._capabilities),
            "started_at": self._started_at.isoformat(),
            "heartbeat_at": datetime.now(UTC).isoformat(),
        }
        health_path = Path(os.environ.get("WORKER_HEALTH_FILE", "/tmp/listencloser-worker.json"))
        try:
            health_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = health_path.with_suffix(".tmp")
            temporary_path.write_text(json.dumps(heartbeat), encoding="utf-8")
            temporary_path.replace(health_path)
        except OSError:
            logger.exception("worker_health_file_failed", extra={"path": str(health_path)})

        try:
            self.client.table("worker_heartbeats").upsert(
                heartbeat,
                on_conflict="worker_id",
            ).execute()
        except Exception:
            logger.exception(
                "worker_heartbeat_failed",
                extra={"worker_id": self._worker_id, "status": status},
            )

    @property
    def client(self) -> Any:
        """Lazily create and cache the Supabase service-role client."""
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
            from supabase import create_client  # type: ignore[import-untyped]

            self._client = create_client(url, key)
            return self._client

    def register(self, name: str, version: str, handler: Callable[..., list[str]]) -> None:
        """Register a capability handler by name and version."""
        key = _capability_key(name, version)
        self._capabilities[key] = handler
        logger.info("capability_registered", extra={"capability": key})

    # ------------------------------------------------------------------
    # Queue transport hooks
    # ------------------------------------------------------------------

    def _receive_next_job(self) -> dict[str, Any] | None:
        """Return one transport-owned Job delivery, or ``None`` when empty."""
        raise NotImplementedError

    def _heartbeat_delivery(self, job_id: str) -> None:
        """Keep the concrete queue delivery alive while a handler runs."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Product lifecycle helpers
    # ------------------------------------------------------------------

    def _mark_running(self, job_id: str) -> bool:
        now = datetime.now(UTC).isoformat()
        result = (
            self.client.table("jobs")
            .update({"stage": "running", "started_at": now})
            .eq("id", job_id)
            .eq("worker_id", self._worker_id)
            .eq("stage", "claimed")
            .execute()
        )
        return bool(result.data) if result.data is not None else False

    def _mark_succeeded(self, job_id: str, output_version_ids: list[str]) -> None:
        now = datetime.now(UTC).isoformat()
        self.client.table("jobs").update(
            {
                "stage": "succeeded",
                "progress": 1.0,
                "status_message": "completed",
                "output_version_ids": output_version_ids,
                "completed_at": now,
            }
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "running").execute()

    def _requeue_job(
        self,
        job_id: str,
        retry_count: int,
        error_message: str,
        error_details: dict,
    ) -> None:
        self.client.table("jobs").update(
            {
                "stage": "queued",
                "retry_count": retry_count,
                "error_message": error_message,
                "error_details": error_details,
                "worker_id": None,
                "progress": 0.0,
                "status_message": f"retry {retry_count}",
            }
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "running").execute()

    def _mark_failed(self, job_id: str, error_message: str, error_details: dict) -> None:
        now = datetime.now(UTC).isoformat()
        self.client.table("jobs").update(
            {
                "stage": "failed",
                "error_message": error_message,
                "error_details": error_details,
                "completed_at": now,
            }
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "running").execute()

    def _check_cancelled(self, job_id: str) -> bool:
        """Return whether product policy has externally cancelled the Job."""
        try:
            result = self.client.table("jobs").select("stage").eq("id", job_id).execute()
            if result.data:
                return result.data[0].get("stage") == "cancelled"
        except Exception:
            logger.exception("cancel_check_failed", extra={"job_id": job_id})
        return False

    def _check_cache_hit(self, job_row: dict) -> bool:
        cache_key = job_row.get("cache_key")
        if not cache_key:
            return False
        try:
            result = (
                self.client.table("jobs")
                .select("id")
                .eq("cache_key", cache_key)
                .eq("stage", "succeeded")
                .execute()
            )
            return bool(result.data)
        except Exception:
            logger.exception("cache_hit_check_failed")
            return False

    def _cached_output_version_ids(self, job_row: dict) -> list[str] | None:
        cache_key = job_row.get("cache_key")
        if not cache_key:
            return None
        try:
            result = (
                self.client.table("jobs")
                .select("id,output_version_ids")
                .eq("cache_key", cache_key)
                .eq("stage", "succeeded")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            if not result.data:
                return None
            return [str(value) for value in (result.data[0].get("output_version_ids") or [])]
        except Exception:
            logger.exception("cache_output_lookup_failed")
            return None

    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Update product-visible progress for a running Job."""
        clamped = max(0.0, min(1.0, float(progress)))
        try:
            self.client.table("jobs").update({"progress": clamped, "status_message": message}).eq(
                "id", job_id
            ).eq("worker_id", self._worker_id).eq("stage", "running").execute()
        except Exception:
            logger.exception("update_progress_failed", extra={"job_id": job_id})

    def _row_to_job(self, row: dict) -> Job:
        lifecycle = JobLifecycle(
            current=row.get("stage", "queued"),
            progress=float(row.get("progress", 0.0)),
            message=row.get("status_message", ""),
            retry_count=int(row.get("retry_count", 0)),
            max_retries=int(row.get("max_retries", 3)),
            lease_expires_at=_parse_datetime(row.get("lease_expires_at")),
            started_at=_parse_datetime(row.get("started_at")),
            completed_at=_parse_datetime(row.get("completed_at")),
        )
        capability = Capability(
            name=row.get("capability_name", ""),
            version=row.get("capability_version", ""),
        )
        return Job(
            id=UUID(str(row["id"])),
            workflow_id=UUID(str(row["workflow_id"])),
            capability=capability,
            lifecycle=lifecycle,
            input_version_ids=_parse_uuid_list(row.get("input_version_ids")),
            output_version_ids=_parse_uuid_list(row.get("output_version_ids")),
            parameters=_parse_jsonb(row.get("parameters")),
            cache_key=row.get("cache_key"),
            error=row.get("error_message"),
            error_details=_parse_jsonb(row.get("error_details")),
            provenance=_parse_jsonb(row.get("provenance")),
            created_at=_parse_datetime(row.get("created_at")) or datetime.now(UTC),
            created_by=row.get("created_by"),
        )

    def _execute_job(self, job_row: dict) -> None:
        """Validate and execute one Job already owned by the queue transport."""
        job_id = str(job_row["id"])
        cap_name = job_row.get("capability_name", "")
        cap_version = job_row.get("capability_version", "")
        cap_key = _capability_key(cap_name, cap_version)

        if self._check_cancelled(job_id):
            logger.info("job_cancelled_after_receive", extra={"job_id": job_id})
            return

        if self._check_cache_hit(job_row):
            cached_output_version_ids = self._cached_output_version_ids(job_row)
            if cached_output_version_ids is not None:
                logger.info(
                    "cache_hit_skip",
                    extra={"job_id": job_id, "cache_key": job_row.get("cache_key")},
                )
                now = datetime.now(UTC).isoformat()
                self.client.table("jobs").update(
                    {
                        "stage": "succeeded",
                        "progress": 1.0,
                        "status_message": "cache hit: duplicate job skipped",
                        "output_version_ids": cached_output_version_ids,
                        "completed_at": now,
                    }
                ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "claimed").execute()
                return
            logger.warning(
                "cache_hit_output_missing",
                extra={"job_id": job_id, "cache_key": job_row.get("cache_key")},
            )

        if not self._mark_running(job_id):
            logger.info("job_state_changed_before_run", extra={"job_id": job_id})
            return

        handler = self._capabilities.get(cap_key)
        if handler is None:
            self._mark_failed(job_id, f"No handler registered for capability '{cap_key}'", {})
            logger.error("handler_not_found", extra={"job_id": job_id, "capability": cap_key})
            return

        try:
            job_obj = self._row_to_job(job_row)
        except Exception as exc:
            logger.exception("job_model_parse_failed", extra={"job_id": job_id})
            self._mark_failed(job_id, f"Failed to parse job row into Job model: {exc}", {})
            return

        heartbeat_stop = threading.Event()

        def _heartbeat_loop() -> None:
            while not heartbeat_stop.wait(self._heartbeat_interval):
                try:
                    if self._check_cancelled(job_id):
                        logger.info("cancelled_during_run", extra={"job_id": job_id})
                        heartbeat_stop.set()
                        return
                    self._heartbeat_delivery(job_id)
                except Exception:
                    logger.exception("delivery_heartbeat_failed", extra={"job_id": job_id})

        heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        heartbeat_thread.start()

        execution_started = time.perf_counter()
        with _tracer.start_as_current_span(
            "job.execute",
            attributes={
                "job_id": job_id,
                "job_kind": cap_key,
                "worker_id": self._worker_id,
                "retry_count": int(job_row.get("retry_count", 0)),
            },
        ) as execute_span:
            try:
                output_vals = handler(job_obj, self.client)
                if not isinstance(output_vals, list):
                    output_vals = list(output_vals) if output_vals else []
                output_version_ids = [str(oid) for oid in output_vals]
                if self._check_cancelled(job_id):
                    execute_span.set_attribute("job.cancelled", True)
                    logger.info("job_cancelled_before_completion", extra={"job_id": job_id})
                    return
                self._mark_succeeded(job_id, output_version_ids)
                record_job_execution(
                    cap_key,
                    "succeeded",
                    time.perf_counter() - execution_started,
                )
                execute_span.set_attribute("job.success", True)
                execute_span.set_attribute("output_version_count", len(output_version_ids))
                logger.info("job_succeeded", extra={"job_id": job_id})
            except Exception as exc:
                execute_span.set_attribute("job.success", False)
                execute_span.record_exception(exc)
                execute_span.set_status(Status(StatusCode.ERROR, str(exc)))
                logger.exception("job_handler_failed", extra={"job_id": job_id})

                error_message = "Processing could not be completed. Retry processing."
                error_details = {"exception": str(exc), "type": type(exc).__name__}
                retry_count = int(job_row.get("retry_count", 0)) + 1
                max_retries = int(job_row.get("max_retries", 3))
                cancelled = self._check_cancelled(job_id)
                outcome = (
                    "cancelled"
                    if cancelled
                    else "retry"
                    if retry_count <= max_retries
                    else "failed"
                )
                record_job_execution(
                    cap_key,
                    outcome,
                    time.perf_counter() - execution_started,
                )

                if cancelled:
                    logger.info("job_cancelled_after_handler_error", extra={"job_id": job_id})
                elif retry_count <= max_retries:
                    delay = 2**retry_count
                    logger.info(
                        "job_retry",
                        extra={
                            "job_id": job_id,
                            "retry": retry_count,
                            "max": max_retries,
                            "delay_s": delay,
                        },
                    )
                    time.sleep(delay)
                    self._requeue_job(job_id, retry_count, error_message, error_details)
                else:
                    self._mark_failed(job_id, error_message, error_details)
                    logger.info("job_exhausted_retries", extra={"job_id": job_id})
            finally:
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=5.0)

    def run(self) -> None:
        """Run the transport-backed worker until :meth:`stop` is called."""
        self._running = True
        self._heartbeat_worker()
        logger.info(
            "worker_started",
            extra={
                "worker_id": self._worker_id,
                "poll_interval_s": self._poll_interval,
                "max_workers": self._max_workers,
            },
        )

        executor = ThreadPoolExecutor(max_workers=self._max_workers)
        last_heartbeat = time.monotonic()
        try:
            while self._running:
                if self._stop_event.is_set():
                    self._running = False
                    break

                with self._in_flight_lock:
                    has_capacity = len(self._in_flight) < self._max_workers
                job_row = self._receive_next_job() if has_capacity else None
                if job_row is not None:
                    job_id = str(job_row["id"])
                    with self._in_flight_lock:
                        self._in_flight.add(job_id)
                    future = executor.submit(self._execute_job, job_row)

                    def release_slot(_future, completed_job_id=job_id) -> None:
                        with self._in_flight_lock:
                            self._in_flight.discard(completed_job_id)

                    future.add_done_callback(release_slot)

                now = time.monotonic()
                if now - last_heartbeat >= 10.0:
                    self._heartbeat_worker()
                    last_heartbeat = now

                self._stop_event.wait(self._poll_interval)

            logger.info("worker_draining", extra={"worker_id": self._worker_id})
            self._heartbeat_worker("draining")
            executor.shutdown(wait=True)
            self._heartbeat_worker("stopped")
            logger.info("worker_stopped", extra={"worker_id": self._worker_id})
        except Exception:
            logger.exception("worker_crashed", extra={"worker_id": self._worker_id})
            self._heartbeat_worker("stopped")
            executor.shutdown(wait=False)
            raise

    def stop(self) -> None:
        logger.info("worker_stop_requested", extra={"worker_id": self._worker_id})
        self._stop_event.set()


def _capability_key(name: str, version: str) -> str:
    return f"{name}:{version}"
