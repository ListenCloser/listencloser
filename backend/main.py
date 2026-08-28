"""FastAPI entrypoint for the durable music-understanding service."""

import contextvars
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from ask.api import router as ask_router
from auth_utils import limiter
from domain.api import router as domain_router
from domain.upload_api import router as upload_router
from health_api import router as health_router
from observability import configure_logging, init_telemetry, record_http_request

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
app.include_router(upload_router)
app.include_router(ask_router)
app.include_router(health_router)

# Instrument after routes are registered so request spans include FastAPI route
# names. Export remains a no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset.
FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    token = _request_id_ctx.set(req_id)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        logger.exception("request_failed", extra={"req_id": req_id})
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        route = request.scope.get("route")
        route_template = getattr(route, "path", None) or "unmatched"
        record_http_request(request.method, route_template, status_code, duration_ms)
        _request_id_ctx.reset(token)

    response.headers["x-request-id"] = req_id
    logger.info(
        "request_handled",
        extra={
            "req_id": req_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response
