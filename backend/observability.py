"""Shared logging and telemetry bootstrap for API and worker processes."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Link
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_JOB_TRACE_CONTEXT_KEY = "trace_context"
_JOB_TRACE_CONTEXT_HEADERS = ("traceparent", "tracestate")
_MAX_JOB_TRACE_CONTEXT_VALUE_LENGTH = 512
_trace_context_propagator = TraceContextTextMapPropagator()


class JsonFormatter(logging.Formatter):
    """Emit one structured JSON object per log record.

    Trace/span IDs are injected automatically when a span is active so stdout
    logs can be correlated with Grafana/Sentry traces without every call site
    having to know about OpenTelemetry.
    """

    _standard_fields = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": os.environ.get("OTEL_SERVICE_NAME", "listencloser"),
            "release": os.environ.get("RELEASE", "development"),
        }

        span = trace.get_current_span()
        context = span.get_span_context()
        if context.is_valid:
            payload["trace_id"] = format(context.trace_id, "032x")
            payload["span_id"] = format(context.span_id, "016x")

        for key, value in record.__dict__.items():
            if key not in self._standard_fields and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service_name: str) -> None:
    """Configure structured stdout logging once for a process."""

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def init_sentry(
    logger: logging.Logger,
    *,
    default_release: str = "development",
) -> bool:
    """Initialize Sentry from the shared backend environment contract.

    The pinned Sentry SDK auto-enables installed framework integrations by
    default, including FastAPI and Starlette. Keeping that responsibility in
    the SDK avoids coupling process entrypoints to integration class names.
    """

    dsn = os.environ.get("SENTRY_DSN_BACKEND") or os.environ.get("SENTRY_DSN")
    if not dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry_sdk_not_installed")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENV", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        release=os.environ.get("RELEASE", default_release),
    )
    logger.info("sentry_initialized")
    return True


def _telemetry_resource(service_name: str) -> Resource:
    return Resource.create(
        {
            "service.name": service_name,
            "service.version": os.environ.get("RELEASE", "development"),
            "deployment.environment.name": os.environ.get("SENTRY_ENV", "production"),
        }
    )


def init_telemetry(service_name: str) -> bool:
    """Initialize vendor-neutral OTLP traces and metrics when configured.

    ``OTEL_EXPORTER_OTLP_ENDPOINT`` and ``OTEL_EXPORTER_OTLP_HEADERS`` are
    standard OpenTelemetry environment variables. The same configured OTLP
    backend receives traces and metrics. When the endpoint is absent telemetry
    stays disabled, keeping local development and CI independent of Grafana.
    """

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logging.getLogger("observability").info("otel_disabled_no_endpoint")
        return False

    resource = _telemetry_resource(service_name)

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    # Instrument shared outbound HTTP calls (Supabase/httpx-based providers,
    # Ask provider calls, etc.) while leaving application-specific spans and
    # metrics to the domain code.
    HTTPXClientInstrumentor().instrument()

    logging.getLogger("observability").info(
        "otel_initialized",
        extra={"otlp_endpoint_host": endpoint.split("/", 3)[2] if "://" in endpoint else endpoint},
    )
    return True


def get_tracer(name: str):
    """Return a tracer without exposing the SDK to callers."""

    return trace.get_tracer(name)


def capture_job_trace_provenance(provenance: dict[str, Any]) -> dict[str, Any]:
    """Persist the current W3C trace carrier in immutable Job provenance.

    Only Trace Context headers are admitted. OpenTelemetry baggage is excluded
    because it can contain arbitrary application/user values and must not become
    durable Job metadata. Existing context wins so explicit retries preserve the
    original producer trace instead of being rebound to the retrying HTTP call.
    """

    result = dict(provenance)
    if _JOB_TRACE_CONTEXT_KEY in result:
        return result

    carrier: dict[str, str] = {}
    _trace_context_propagator.inject(carrier)
    traceparent = carrier.get("traceparent")
    if (
        not isinstance(traceparent, str)
        or not traceparent
        or len(traceparent) > _MAX_JOB_TRACE_CONTEXT_VALUE_LENGTH
    ):
        return result

    context = {"traceparent": traceparent}
    tracestate = carrier.get("tracestate")
    if (
        isinstance(tracestate, str)
        and tracestate
        and len(tracestate) <= _MAX_JOB_TRACE_CONTEXT_VALUE_LENGTH
    ):
        context["tracestate"] = tracestate
    result[_JOB_TRACE_CONTEXT_KEY] = context
    return result


def job_trace_links(provenance: dict[str, Any]) -> list[Link]:
    """Return one valid producer link extracted from durable Job provenance."""

    raw = provenance.get(_JOB_TRACE_CONTEXT_KEY)
    if not isinstance(raw, dict):
        return []

    carrier: dict[str, str] = {}
    for header in _JOB_TRACE_CONTEXT_HEADERS:
        value = raw.get(header)
        if (
            isinstance(value, str)
            and value
            and len(value) <= _MAX_JOB_TRACE_CONTEXT_VALUE_LENGTH
        ):
            carrier[header] = value
    if "traceparent" not in carrier:
        return []

    context = _trace_context_propagator.extract(carrier)
    span_context = trace.get_current_span(context).get_span_context()
    if not span_context.is_valid:
        return []
    return [Link(span_context)]


def http_metric_attributes(method: str, route_template: str, status_code: int) -> dict[str, str]:
    """Return the bounded dimensions used for HTTP metrics.

    Callers must pass the FastAPI route template rather than the raw request
    path. That keeps work/version/job UUIDs out of metric dimensions.
    """

    status_class = f"{max(1, min(5, status_code // 100))}xx"
    return {
        "http.request.method": method.upper(),
        "http.route": route_template or "unmatched",
        "http.response.status_class": status_class,
    }


def job_metric_attributes(capability: str, outcome: str) -> dict[str, str]:
    """Return bounded worker metric dimensions; never include job IDs."""

    return {
        "job.capability": capability or "unknown",
        "job.outcome": outcome,
    }


_http_metrics: tuple[Any, Any] | None = None
_job_metrics: tuple[Any, Any, Any] | None = None


def _get_http_metrics() -> tuple[Any, Any]:
    global _http_metrics
    if _http_metrics is None:
        meter = metrics.get_meter("listencloser-api")
        _http_metrics = (
            meter.create_counter(
                "hello_ai.http.server.requests",
                unit="{request}",
                description="Completed inbound HTTP requests.",
            ),
            meter.create_histogram(
                "hello_ai.http.server.duration",
                unit="ms",
                description="Inbound HTTP request duration.",
            ),
        )
    return _http_metrics


def record_http_request(
    method: str,
    route_template: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Record one API request using low-cardinality route dimensions."""

    counter, duration = _get_http_metrics()
    attributes = http_metric_attributes(method, route_template, status_code)
    counter.add(1, attributes)
    duration.record(max(0.0, duration_ms), attributes)


def _get_job_metrics() -> tuple[Any, Any, Any]:
    global _job_metrics
    if _job_metrics is None:
        meter = metrics.get_meter("listencloser-worker")
        _job_metrics = (
            meter.create_counter(
                "hello_ai.worker.job.executions",
                unit="{job}",
                description="Worker job handler executions by capability and outcome.",
            ),
            meter.create_histogram(
                "hello_ai.worker.job.duration",
                unit="s",
                description="Worker job handler execution duration.",
            ),
            meter.create_counter(
                "hello_ai.worker.orphans_recovered",
                unit="{job}",
                description="Expired job leases recovered by workers.",
            ),
        )
    return _job_metrics


def record_job_execution(capability: str, outcome: str, duration_seconds: float) -> None:
    """Record one completed handler attempt without user/job identifiers."""

    counter, duration, _orphans = _get_job_metrics()
    attributes = job_metric_attributes(capability, outcome)
    counter.add(1, attributes)
    duration.record(max(0.0, duration_seconds), attributes)


def record_orphans_recovered(count: int) -> None:
    """Record orphaned leases recovered by a worker."""

    if count <= 0:
        return
    _counter, _duration, orphans = _get_job_metrics()
    orphans.add(count)
