"""
Postgres-backed durable job worker loop for hello-ai.

Uses the Supabase ``jobs`` table as the backing store with an atomic
lease mechanism to ensure exactly-once processing across multiple worker
instances.  No Redis, no Celery — just Postgres, threads, and polling.

Lifecycle::

    queued → claimed → running → succeeded
       │        │                    │
       │        └─ (expired) → queued (orphan recovery)
       │                             │
       └─ failed → queued (retry w/ exponential backoff)
                     │
                     └─ failed (retries exhausted)

Usage::

    worker = JobWorker()
    worker.register("transcribe", "1.0", handle_transcribe)
    worker.run()   # blocks until stop()
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .models import Capability, Job, JobLifecycle

logger = logging.getLogger("job_worker")


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
        for v in val:
            if v is None:
                continue
            try:
                out.append(UUID(str(v)))
            except (ValueError, AttributeError):
                continue
        return out
    return []


class JobWorker:
    """Durable Postgres-backed job worker.

    Polls the ``jobs`` table for ``queued`` rows, atomically claims them
    via an ``UPDATE … WHERE stage='queued'`` lease, and executes the
    matching capability handler in a thread pool.

    Parameters
    ----------
    lease_duration_sec:
        How long a claimed lease lives before it is considered stale.
    heartbeat_interval_sec:
        How often the lease is renewed for a running job.
    poll_interval_sec:
        How long to sleep between queue polls.
    max_workers:
        Maximum number of concurrent handler threads.
    """

    def __init__(
        self,
        lease_duration_sec: float = 30.0,
        heartbeat_interval_sec: float = 10.0,
        poll_interval_sec: float = 1.0,
        max_workers: int = 4,
    ) -> None:
        self._worker_id = str(uuid4())
        self._started_at = datetime.now(UTC)
        self._lease_duration = lease_duration_sec
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
        health_path = Path(os.environ.get("WORKER_HEALTH_FILE", "/tmp/hello-ai-worker.json"))
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

    # ------------------------------------------------------------------
    # Supabase client (lazy, threadsafe)
    # ------------------------------------------------------------------

    @property
    def client(self) -> Any:
        """Lazily create and cache the Supabase client (service-role key).

        Reads ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` from the
        environment, matching the pattern used in ``backend/main.py``.
        """
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

    # ------------------------------------------------------------------
    # Capability registry
    # ------------------------------------------------------------------

    def register(self, name: str, version: str, handler: Callable[..., list[str]]) -> None:
        """Register a handler for a capability (name + version).

        ``handler(job: Job, client) -> list[str]``
            Receives the domain ``Job`` and the Supabase client.
            Must return a list of output version UUID strings.
        """
        key = _capability_key(name, version)
        self._capabilities[key] = handler
        logger.info("capability_registered", extra={"capability": key})

    # ------------------------------------------------------------------
    # Orphan recovery
    # ------------------------------------------------------------------

    def _recover_orphans(self) -> int:
        """Reset expired claimed/running jobs back to ``queued``.

        Finds every job whose ``lease_expires_at`` is in the past and
        whose stage is ``claimed`` or ``running``, then clears the lease
        and worker assignment so the job will be picked up again.
        """
        now = datetime.now(UTC).isoformat()
        try:
            result = (
                self.client.table("jobs")
                .update(
                    {
                        "stage": "queued",
                        "worker_id": None,
                        "lease_expires_at": None,
                        "status_message": "recovered from orphaned worker",
                    }
                )
                .lt("lease_expires_at", now)
                .in_("stage", ["claimed", "running"])
                .execute()
            )
            count = len(result.data) if result.data else 0
            if count:
                logger.warning("orphan_recovery", extra={"count": count})
            return count
        except Exception:
            logger.exception("orphan_recovery_failed")
            return 0

    # ------------------------------------------------------------------
    # Lease & lifecycle helpers
    # ------------------------------------------------------------------

    def _claim_job(self, job_id: str) -> bool:
        """Atomically claim a job with ``UPDATE … WHERE stage='queued'``.

        Returns ``True`` if exactly one row was updated (meaning this
        worker won the race for the job).
        """
        expires = (datetime.now(UTC) + timedelta(seconds=self._lease_duration)).isoformat()
        result = (
            self.client.table("jobs")
            .update(
                {
                    "stage": "claimed",
                    "worker_id": self._worker_id,
                    "lease_expires_at": expires,
                }
            )
            .eq("id", job_id)
            .eq("stage", "queued")
            .execute()
        )
        return bool(result.data) if result.data is not None else False

    def _mark_running(self, job_id: str) -> bool:
        """Transition a claimed job into ``running`` state."""
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

    def _renew_lease(self, job_id: str) -> None:
        """Extend the lease on a running job (heartbeat)."""
        expires = (datetime.now(UTC) + timedelta(seconds=self._lease_duration)).isoformat()
        self.client.table("jobs").update({"lease_expires_at": expires}).eq("id", job_id).eq(
            "worker_id", self._worker_id
        ).eq("stage", "running").execute()

    def _mark_succeeded(self, job_id: str, output_version_ids: list[str]) -> None:
        """Mark a job as successfully completed."""
        now = datetime.now(UTC).isoformat()
        self.client.table("jobs").update(
            {
                "stage": "succeeded",
                "progress": 1.0,
                "status_message": "completed",
                "output_version_ids": output_version_ids,
                "completed_at": now,
                "lease_expires_at": None,
            }
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "running").execute()

    def _requeue_job(
        self,
        job_id: str,
        retry_count: int,
        error_message: str,
        error_details: dict,
    ) -> None:
        """Send a failed job back to ``queued`` for retry."""
        self.client.table("jobs").update(
            {
                "stage": "queued",
                "retry_count": retry_count,
                "error_message": error_message,
                "error_details": error_details,
                "worker_id": None,
                "lease_expires_at": None,
                "progress": 0.0,
                "status_message": f"retry {retry_count}",
            }
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "running").execute()

    def _mark_failed(self, job_id: str, error_message: str, error_details: dict) -> None:
        """Mark a job as permanently failed (retries exhausted)."""
        now = datetime.now(UTC).isoformat()
        self.client.table("jobs").update(
            {
                "stage": "failed",
                "error_message": error_message,
                "error_details": error_details,
                "completed_at": now,
                "lease_expires_at": None,
            }
        ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "running").execute()

    # ------------------------------------------------------------------
    # Cancellation check
    # ------------------------------------------------------------------

    def _check_cancelled(self, job_id: str) -> bool:
        """Return ``True`` if the job has been externally set to ``cancelled``."""
        try:
            result = self.client.table("jobs").select("stage").eq("id", job_id).execute()
            if result.data:
                return result.data[0].get("stage") == "cancelled"
        except Exception:
            logger.exception("cancel_check_failed", extra={"job_id": job_id})
        return False

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def _check_cache_hit(self, job_row: dict) -> bool:
        """Return ``True`` if a ``succeeded`` job with the same ``cache_key``
        already exists."""
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

    # ------------------------------------------------------------------
    # Progress updates (public — called by handlers)
    # ------------------------------------------------------------------

    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Update the progress and status message of a running job.

        Safe to call from capability handlers during long-running work.
        ``progress`` is clamped to **[0.0, 1.0]**.
        """
        clamped = max(0.0, min(1.0, float(progress)))
        try:
            self.client.table("jobs").update({"progress": clamped, "status_message": message}).eq(
                "id", job_id
            ).eq("worker_id", self._worker_id).eq("stage", "running").execute()
        except Exception:
            logger.exception("update_progress_failed", extra={"job_id": job_id})

    # ------------------------------------------------------------------
    # DB row → domain model
    # ------------------------------------------------------------------

    def _row_to_job(self, row: dict) -> Job:
        """Map a raw ``jobs`` table row dict to a ``Job`` domain model."""
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

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll_jobs(self) -> dict | None:
        """Return the oldest ``queued`` job row, or ``None`` if the queue
        is empty."""
        try:
            result = (
                self.client.table("jobs")
                .select("*")
                .eq("stage", "queued")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
        except Exception:
            logger.exception("poll_failed")
        return None

    # ------------------------------------------------------------------
    # Single-job execution (runs in a thread-pool worker)
    # ------------------------------------------------------------------

    def _execute_job(self, job_row: dict, *, already_claimed: bool = False) -> None:
        """Claim, validate, and run a single job inside the current thread."""
        job_id: str = str(job_row["id"])

        # --- Atomic claim ---
        if not already_claimed and not self._claim_job(job_id):
            logger.debug("claim_lost", extra={"job_id": job_id})
            return

        # --- Defensive cancellation check ---
        if self._check_cancelled(job_id):
            logger.info("job_cancelled_after_claim", extra={"job_id": job_id})
            return

        # --- Idempotency check (only after this worker owns the lease) ---
        if self._check_cache_hit(job_row):
            logger.info(
                "cache_hit_skip",
                extra={
                    "job_id": job_id,
                    "cache_key": job_row.get("cache_key"),
                },
            )
            now = datetime.now(UTC).isoformat()
            self.client.table("jobs").update(
                {
                    "stage": "succeeded",
                    "progress": 1.0,
                    "status_message": "cache hit: duplicate job skipped",
                    "completed_at": now,
                    "lease_expires_at": None,
                }
            ).eq("id", job_id).eq("worker_id", self._worker_id).eq("stage", "claimed").execute()
            return

        # --- Transition to running ---
        if not self._mark_running(job_id):
            logger.info(
                "job_state_changed_before_run",
                extra={"job_id": job_id},
            )
            return

        # --- Resolve handler ---
        cap_name = job_row.get("capability_name", "")
        cap_version = job_row.get("capability_version", "")
        cap_key = _capability_key(cap_name, cap_version)
        handler = self._capabilities.get(cap_key)

        if handler is None:
            self._mark_failed(
                job_id,
                f"No handler registered for capability '{cap_key}'",
                {},
            )
            logger.error(
                "handler_not_found",
                extra={"job_id": job_id, "capability": cap_key},
            )
            return

        # --- Build domain Job object ---
        try:
            job_obj = self._row_to_job(job_row)
        except Exception as exc:
            logger.exception("job_model_parse_failed", extra={"job_id": job_id})
            self._mark_failed(job_id, f"Failed to parse job row into Job model: {exc}", {})
            return

        # --- Heartbeat thread ---
        heartbeat_stop = threading.Event()

        def _heartbeat_loop() -> None:
            while not heartbeat_stop.wait(self._heartbeat_interval):
                try:
                    if self._check_cancelled(job_id):
                        logger.info("cancelled_during_run", extra={"job_id": job_id})
                        heartbeat_stop.set()
                        return
                    self._renew_lease(job_id)
                except Exception:
                    logger.exception("heartbeat_failed", extra={"job_id": job_id})

        heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        heartbeat_thread.start()

        # --- Execute handler ---
        try:
            output_vals = handler(job_obj, self.client)

            if not isinstance(output_vals, list):
                output_vals = list(output_vals) if output_vals else []

            output_version_ids = [str(oid) for oid in output_vals]
            if self._check_cancelled(job_id):
                logger.info(
                    "job_cancelled_before_completion",
                    extra={"job_id": job_id},
                )
                return
            self._mark_succeeded(job_id, output_version_ids)
            logger.info("job_succeeded", extra={"job_id": job_id})

        except Exception as exc:
            logger.exception("job_handler_failed", extra={"job_id": job_id})

            # User-facing error text must never leak raw database exceptions
            # (e.g. Postgres constraint details). The full traceback is already
            # in the logs and the raw exception is preserved in error_details
            # for diagnostics.
            error_message = "Processing could not be completed. Retry processing."
            error_details = {
                "exception": str(exc),
                "type": type(exc).__name__,
            }

            retry_count = int(job_row.get("retry_count", 0)) + 1
            max_retries = int(job_row.get("max_retries", 3))

            if self._check_cancelled(job_id):
                logger.info(
                    "job_cancelled_after_handler_error",
                    extra={"job_id": job_id},
                )
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

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the worker loop.  Blocks until :meth:`stop` is called.

        Performs orphan recovery on startup, then polls for queued jobs
        every ``poll_interval_sec`` and dispatches them to a thread pool.
        Drains in-flight jobs on shutdown.

        Raises
        ------
        RuntimeError
            If ``SUPABASE_URL`` or ``SUPABASE_SERVICE_ROLE_KEY`` are not set.
        """
        self._recover_orphans()
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
                job_row = self._poll_jobs() if has_capacity else None
                if job_row is not None:
                    job_id = str(job_row["id"])
                    if self._claim_job(job_id):
                        with self._in_flight_lock:
                            self._in_flight.add(job_id)
                        future = executor.submit(self._execute_job, job_row, already_claimed=True)

                        def release_slot(_future, completed_job_id=job_id) -> None:
                            with self._in_flight_lock:
                                self._in_flight.discard(completed_job_id)

                        future.add_done_callback(release_slot)

                if time.monotonic() - last_heartbeat >= 10.0:
                    self._heartbeat_worker()
                    last_heartbeat = time.monotonic()

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
        """Signal the worker to finish the current job and exit gracefully.

        Safe to call from any thread.  The main loop will complete the
        in-progress job, drain the thread pool, and return.
        """
        logger.info("worker_stop_requested", extra={"worker_id": self._worker_id})
        self._stop_event.set()


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _capability_key(name: str, version: str) -> str:
    """Build the registry key for a capability name + version pair."""
    return f"{name}:{version}"
