"""FastAPI entrypoint for the durable music-understanding service."""

import contextvars
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from ask.api import router as ask_router
from auth_utils import get_supabase_client, limiter
from domain.api import router as domain_router
from observability import configure_logging, init_telemetry

configure_logging("hello-ai-api")
init_telemetry("hello-ai-api")
logger = logging.getLogger("backend")
_request_id_ctx = contextvars.ContextVar("request_id", default="none")

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastAPIIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    _sentry_dsn = os.environ.get("SENTRY_DSN_BACKEND") or os.environ.get("SENTRY_DSN")
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.environ.get("SENTRY_ENV", "production"),
            integrations=[StarletteIntegration(), FastAPIIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            release=os.environ.get("RELEASE", "backend@2.0.0"),
        )
        logger.info("sentry_initialized")
except ImportError:
    logger.warning("sentry_sdk_not_installed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = httpx.Timeout(30.0, connect=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    app.state.http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
    logger.info("http_client_created")
    yield
    await app.state.http_client.aclose()
    logger.info("http_client_closed")


app = FastAPI(
    title="hello-ai music understanding API",
    version="2.0.0",
    description=(
        "Persistent projects, immutable music artifacts, asynchronous jobs, "
        "and evidence-backed analysis."
    ),
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(domain_router)
app.include_router(ask_router)

# Instrument after routes are registered so request spans include FastAPI route
# names. Export remains a no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset.
FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    token = _request_id_ctx.set(req_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"req_id": req_id})
        raise
    finally:
        _request_id_ctx.reset(token)

    response.headers["x-request-id"] = req_id
    logger.info(
        "request_handled",
        extra={
            "req_id": req_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/live")
def health_live():
    return {"status": "alive", "release": os.environ.get("RELEASE", "development")}


@app.get("/health/ready")
def health_ready():
    release = os.environ.get("RELEASE", "development")
    client = get_supabase_client()
    if not client:
        return {
            "status": "degraded",
            "supabase": False,
            "database": False,
            "storage": False,
            "release": release,
            "reason": "supabase not configured",
        }
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
    return {
        "status": "ready" if configured else "degraded",
        "supabase": True,
        "database": database_ready,
        "storage": storage_ready,
        "release": release,
    }


@app.get("/health/queue")
def health_queue():
    client = get_supabase_client()
    if not client:
        return {
            "status": "degraded",
            "reason": "supabase not configured",
            "workers": 0,
            "queued": 0,
            "running": 0,
            "stale_leases": 0,
        }

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
        return {
            "status": "degraded",
            "reason": "job queue unavailable",
            "workers": 0,
            "queued": 0,
            "running": 0,
            "stale_leases": 0,
        }

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
    return {
        "status": "ready" if healthy else "degraded",
        "workers": len(workers),
        "queued": queued,
        "running": running,
        "stale_leases": stale_leases,
        "heartbeat_source": source,
    }
