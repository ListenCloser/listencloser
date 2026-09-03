"""PGMQ transport for the production fenced Job worker.

PGMQ owns delivery visibility, redelivery and acknowledgement. ``public.jobs``
remains the product read model and the execution token remains the sole fence
for product-visible publication.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from .fenced_job_worker import FencedJobWorker

logger = logging.getLogger("pgmq_job_worker")


class PgmqJobWorker(FencedJobWorker):
    """Run fenced Job attempts from the durable ``job_delivery`` PGMQ queue.

    The inherited execution/lifecycle code is deliberately reused. Only the
    commodity transport boundary changes here: receive installs a fresh attempt
    token, the handler heartbeat extends PGMQ visibility, and completion either
    archives or releases the exact delivery after durable Job state changes.
    """

    def __init__(
        self,
        *,
        visibility_timeout_sec: int = 30,
        heartbeat_interval_sec: float = 10.0,
        poll_interval_sec: float = 1.0,
        max_workers: int = 4,
    ) -> None:
        if visibility_timeout_sec < 1:
            raise ValueError("visibility_timeout_sec must be at least 1")
        if heartbeat_interval_sec <= 0:
            raise ValueError("heartbeat_interval_sec must be positive")
        if heartbeat_interval_sec >= visibility_timeout_sec:
            raise ValueError(
                "heartbeat interval must be shorter than PGMQ visibility timeout"
            )

        # JobWorker still names this inherited scheduling interval "lease". The
        # production transport no longer writes or renews Job-row leases; this
        # value only keeps the inherited loop's periodic no-op cadence bounded
        # until the follow-up deletion slice removes that obsolete loop code.
        super().__init__(
            lease_duration_sec=float(visibility_timeout_sec),
            heartbeat_interval_sec=heartbeat_interval_sec,
            poll_interval_sec=poll_interval_sec,
            max_workers=max_workers,
        )
        self._visibility_timeout = int(visibility_timeout_sec)
        self._delivery_ids: dict[str, int] = {}
        self._delivery_ids_lock = threading.Lock()

    def _recover_orphans(self) -> int:
        """PGMQ visibility expiry replaces Jobs-table orphan recovery."""
        return 0

    def _remember_delivery(self, job_id: str, msg_id: int) -> None:
        with self._delivery_ids_lock:
            self._delivery_ids[job_id] = msg_id

    def _delivery_id(self, job_id: str) -> int | None:
        with self._delivery_ids_lock:
            return self._delivery_ids.get(job_id)

    def _forget_delivery(self, job_id: str, expected_msg_id: int) -> None:
        with self._delivery_ids_lock:
            if self._delivery_ids.get(job_id) == expected_msg_id:
                self._delivery_ids.pop(job_id, None)

    @staticmethod
    def _json_row(data: Any) -> dict[str, Any] | None:
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    def _claim_next_job(self) -> dict[str, Any] | None:
        """Receive one PGMQ message and install its fresh execution token."""
        with self._in_flight_lock:
            in_flight = sorted(self._in_flight)
        try:
            request = self._raw_client().rpc(
                "receive_job_delivery",
                {
                    "p_worker_id": self._worker_id,
                    "p_visibility_seconds": self._visibility_timeout,
                    "p_in_flight_job_ids": in_flight,
                },
            )
            result = request.execute()
            row = self._json_row(result.data)
            if row is None:
                return None

            job_id = str(row["id"])
            token = row.get("execution_token")
            msg_id = row.get("_queue_msg_id")
            if not token or msg_id is None:
                raise RuntimeError("PGMQ receive returned incomplete execution identity")

            self._remember_execution_token(job_id, str(token))
            self._remember_delivery(job_id, int(msg_id))
            return row
        except Exception:
            logger.exception(
                "receive_job_delivery_failed",
                extra={"worker_id": self._worker_id},
            )
            return None

    def _renew_lease(self, job_id: str) -> None:
        """Extend PGMQ visibility for the exact currently fenced attempt."""
        msg_id = self._delivery_id(job_id)
        if msg_id is None:
            logger.error("job_delivery_missing", extra={"job_id": job_id})
            return
        token = self._execution_token(job_id)
        request = self._raw_client().rpc(
            "extend_job_delivery",
            {
                "p_job_id": job_id,
                "p_execution_token": token,
                "p_msg_id": msg_id,
                "p_visibility_seconds": self._visibility_timeout,
            },
        )
        result = request.execute()
        if result.data is False:
            logger.info(
                "job_delivery_visibility_not_extended",
                extra={"job_id": job_id, "msg_id": msg_id},
            )

    def _finish_delivery(self, job_id: str, token: str, msg_id: int) -> None:
        """Acknowledge/release only if ``token`` still owns the Job attempt."""
        try:
            request = self._raw_client().rpc(
                "finish_job_delivery",
                {
                    "p_job_id": job_id,
                    "p_execution_token": token,
                    "p_msg_id": msg_id,
                    # Existing product retry backoff has already elapsed inside
                    # JobWorker before it durably returns the Job to queued.
                    "p_retry_delay_seconds": 0,
                },
            )
            result = request.execute()
            logger.info(
                "job_delivery_finished",
                extra={
                    "job_id": job_id,
                    "msg_id": msg_id,
                    "disposition": result.data,
                },
            )
        except Exception:
            # Fail safe: never acknowledge on uncertainty. PGMQ visibility
            # expiry will redeliver and the durable Job state decides what to do.
            logger.exception(
                "finish_job_delivery_failed",
                extra={"job_id": job_id, "msg_id": msg_id},
            )

    def _execute_job(self, job_row: dict, *, already_claimed: bool = False) -> None:
        job_id = str(job_row["id"])
        token_value = job_row.get("execution_token")
        msg_value = job_row.get("_queue_msg_id")

        if not already_claimed or not token_value or msg_value is None:
            # Production dispatch always supplies a received PGMQ delivery. Keep
            # direct-id execution behavior available only to inherited focused
            # tests until the subsequent legacy-transport deletion slice.
            super()._execute_job(job_row, already_claimed=already_claimed)
            return

        token = str(token_value)
        msg_id = int(msg_value)
        try:
            super()._execute_job(job_row, already_claimed=True)
        finally:
            # This RPC is execution-token guarded. If visibility expired and a
            # different worker took over while this handler was still alive, the
            # stale attempt cannot archive or release the successor's delivery.
            self._finish_delivery(job_id, token, msg_id)
            self._forget_delivery(job_id, msg_id)
