"""Operational health endpoints for the backend service."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from api_schemas import HealthLiveResponse, HealthQueueResponse, HealthReadyResponse, HealthResponse
from auth_utils import get_supabase_client

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
    client = get_supabase_client()
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


@router.get("/health/queue", response_model=HealthQueueResponse, response_model_exclude_none=True)
def health_queue() -> HealthQueueResponse:
    client = get_supabase_client()
    if not client:
        return HealthQueueResponse(
            status="degraded",
            reason="supabase not configured",
            workers=0,
            queued=0,
            running=0,
            stale_leases=0,
        )

    now = datetime.now(UTC)
    try:
        active_jobs = (
            client.table("jobs")
            .select("stage,lease_expires_at")
            .in_("stage", ["queued", "claimed", "running"])
            .execute()
        )
        rows = active_jobs.data or []
    except Exception:
        logger.exception("queue_jobs_health_failed")
        return HealthQueueResponse(
            status="degraded",
            reason="job queue unavailable",
            workers=0,
            queued=0,
            running=0,
            stale_leases=0,
        )

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
        health_path = Path(os.environ.get("WORKER_HEALTH_FILE", "/tmp/hello-ai-worker.json"))
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

    queued = sum(row.get("stage") == "queued" for row in rows)
    running = sum(row.get("stage") in {"claimed", "running"} for row in rows)
    stale_leases = sum(
        1
        for row in rows
        if row.get("stage") in {"claimed", "running"}
        and row.get("lease_expires_at")
        and datetime.fromisoformat(str(row["lease_expires_at"]).replace("Z", "+00:00")) < now
    )
    healthy = bool(workers) and stale_leases == 0
    return HealthQueueResponse(
        status="ready" if healthy else "degraded",
        workers=len(workers),
        queued=queued,
        running=running,
        stale_leases=stale_leases,
        heartbeat_source=source,
    )
