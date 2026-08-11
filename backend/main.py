"""FastAPI entrypoint for the durable music-understanding service."""

import contextvars
import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from auth_utils import get_supabase_client, limiter
from domain.api import router as domain_router

_request_id_ctx = contextvars.ContextVar("request_id", default="none")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "req_id": getattr(record, "req_id", "none"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_json_handler = logging.StreamHandler()
_json_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_json_handler], force=True)
logger = logging.getLogger("backend")

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


app = FastAPI(
    title="hello-ai music understanding API",
    version="2.0.0",
    description=(
        "Persistent projects, immutable music artifacts, asynchronous jobs, "
        "and evidence-backed analysis."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(domain_router)


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
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready():
    configured = get_supabase_client() is not None
    return {
        "status": "ready" if configured else "degraded",
        "supabase": configured,
    }
