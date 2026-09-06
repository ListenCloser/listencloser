"""Operational health endpoints for the backend service."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from api_schemas import HealthLiveResponse, HealthQueueResponse, HealthReadyResponse, HealthResponse
from domain.repositories import get_supabase

logger = logging.getLogger("backend.health")
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/live", response_model=HealthLiveResponse)
def health_live() -> HealthLiveResponse:
    return HealthLiveResponse(
        status="alive",
        release=os.environ.get("RELEASE", "development"),
    )


@router.get("/health/ready", response_model=HealthReadyResponse, response_model_exclude_none=True)
def health_ready() -> HealthReadyResponse:
    release = os.environ.get("RELEASE", "development")
    client = get_supabase()
    if not client:
        return HealthReadyResponse(
            status="degraded",
            supabase=False,
            database=False,
            storage=False,
            release=release,
            reason="supabase not configured",
        )
    database_ready = False
    storage_ready = False
    try:
        client.table("jobs").select("id,stage,capability_name").limit(1).execute()
        client.table("worker_heartbeats").select("worker_id").limit(1).execute()
        database_ready = True
    except Exception:
        logger.exception("readiness_database_failed")
    try:
        client.storage.from_("artifacts").list(path="", options={"limit": 1})
        storage_ready = True
    except Exception:
        logger.exception("readiness_storage_failed")
    configured = database_ready and storage_ready
    return HealthReadyResponse(
        status="ready" if configured else "degraded",
        supabase=True,
        database=database_ready,
        storage=storage_ready,
        release=release,
    )


def _queue_metric_row(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return None


@router.get("/health/queue", response_model=HealthQueueResponse, response_model_exclude_none=True)
def health_queue() -> HealthQueueResponse:
    client = get_supabase()
    if not client:
        return HealthQueueResponse(
            status="degraded",
            reason="supabase not configured",
            workers=0,
            queue_ready=False,
            queue_depth=0,
            queue_visible_depth=0,
            total_messages=0,
        )

    try:
        metrics_result = client.rpc("job_queue_metrics", {}).execute()
        metric_row = _queue_metric_row(metrics_result.data)
        if metric_row is None:
            raise RuntimeError("job_queue_metrics returned no row")
        queue_ready = bool(metric_row.get("queue_ready"))
        queue_depth = int(metric_row.get("queue_depth") or 0)
        queue_visible_depth = int(metric_row.get("queue_visible_depth") or 0)
        oldest_age = metric_row.get("oldest_age_seconds")
        oldest_age_seconds = int(oldest_age) if oldest_age is not None else None
        total_messages = int(metric_row.get("total_messages") or 0)
        sampled_at = metric_row.get("sampled_at")
    except Exception:
        logger.exception("queue_metrics_health_failed")
        return HealthQueueResponse(
            status="degraded",
            reason="job queue unavailable",
            workers=0,
            queue_ready=False,
            queue_depth=0,
            queue_visible_depth=0,
            total_messages=0,
        )

    now = datetime.now(UTC)
    workers: list[dict] = []
    source = "database"
    try:
        heartbeats = (
            client.table("worker_heartbeats")
            .select("status,heartbeat_at,capabilities")
            .gte("heartbeat_at", (now - timedelta(seconds=45)).isoformat())
            .execute()
        )
        workers = [
            row
            for row in (heartbeats.data or [])
            if row.get("status") == "running"
            and "understand:1.0" in (row.get("capabilities") or [])
        ]
    except Exception:
        source = "runtime_file"

    if not workers:
        health_path = Path(os.environ.get("WORKER_HEALTH_FILE", "/tmp/listencloser-worker.json"))
        try:
            heartbeat = json.loads(health_path.read_text(encoding="utf-8"))
            heartbeat_at = datetime.fromisoformat(
                str(heartbeat["heartbeat_at"]).replace("Z", "+00:00")
            )
            if (
                heartbeat.get("status") == "running"
                and heartbeat_at >= now - timedelta(seconds=45)
                and "understand:1.0" in (heartbeat.get("capabilities") or [])
            ):
                workers = [heartbeat]
                source = "runtime_file"
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            logger.warning("worker_runtime_heartbeat_unavailable")

    healthy = queue_ready and bool(workers)
    return HealthQueueResponse(
        status="ready" if healthy else "degraded",
        workers=len(workers),
        queue_ready=queue_ready,
        queue_depth=queue_depth,
        queue_visible_depth=queue_visible_depth,
        oldest_age_seconds=oldest_age_seconds,
        total_messages=total_messages,
        sampled_at=sampled_at,
        heartbeat_source=source,
    )
