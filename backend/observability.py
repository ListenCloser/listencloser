"""Shared logging and OpenTelemetry bootstrap for API and worker processes."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


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
            "service": os.environ.get("OTEL_SERVICE_NAME", "hello-ai"),
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


def _parse_otlp_headers(raw: str) -> list[tuple[str, str]]:
    """Parse OTEL_EXPORTER_OTLP_HEADERS into a list of (key, value) tuples.

    The OTel SDK requires values to be URL-encoded, but Grafana Cloud
    credentials often contain ``+`` and ``=`` characters that are not
    encoded in practice.  This parser accepts both encoded and raw values
    and URL-decodes them, matching the behaviour users expect.
    """
    from urllib.parse import unquote

    headers: list[tuple[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        headers.append((key.strip(), unquote(value.strip())))
    return headers


def init_telemetry(service_name: str) -> bool:
    """Initialize vendor-neutral OTLP tracing when an endpoint is configured.

    `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` are standard
    OpenTelemetry environment variables. When the endpoint is absent telemetry
    stays disabled, which keeps local development and CI independent of Grafana.
    """

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logging.getLogger("observability").info("otel_disabled_no_endpoint")
        return False

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.environ.get("RELEASE", "development"),
            "deployment.environment.name": os.environ.get("SENTRY_ENV", "production"),
        }
    )

    # Parse headers ourselves to avoid the SDK's strict URL-encoding
    # requirement which rejects raw Base64 tokens containing +/=.
    raw_headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers = _parse_otlp_headers(raw_headers) if raw_headers else None

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(headers=headers)))
    trace.set_tracer_provider(provider)

    # Instrument shared outbound HTTP calls (Supabase/httpx-based providers,
    # Ask provider calls, etc.) while leaving application-specific spans to the
    # domain code.
    HTTPXClientInstrumentor().instrument()

    logging.getLogger("observability").info(
        "otel_initialized",
        extra={"otlp_endpoint_host": endpoint.split("/", 3)[2] if "://" in endpoint else endpoint},
    )
    return True


def get_tracer(name: str):
    """Return a tracer without exposing the SDK to callers."""

    return trace.get_tracer(name)
