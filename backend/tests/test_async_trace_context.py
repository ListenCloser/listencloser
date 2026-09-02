from __future__ import annotations

from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
from uuid import uuid4

from opentelemetry import context, trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState

import domain.fenced_job_worker as fenced_job_worker
from domain.fenced_job_worker import FencedJobWorker
from domain.models import Capability, Job
from domain.repositories import JobRepo
from observability import capture_job_trace_provenance, job_trace_links

_TRACE_ID = int("1234567890abcdef1234567890abcdef", 16)
_SPAN_ID = int("1234567890abcdef", 16)
_OTHER_TRACE_ID = int("fedcba0987654321fedcba0987654321", 16)
_OTHER_SPAN_ID = int("fedcba0987654321", 16)


@contextmanager
def _current_span(trace_id: int, span_id: int):
    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    token = context.attach(trace.set_span_in_context(NonRecordingSpan(span_context)))
    try:
        yield
    finally:
        context.detach(token)


def test_job_repository_persists_only_bounded_w3c_trace_context() -> None:
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="analyze", version="1.0"),
        provenance={"source": "api"},
    )

    with _current_span(_TRACE_ID, _SPAN_ID):
        row = JobRepo(SimpleNamespace())._job_to_row(job)

    assert row["provenance"] == {
        "source": "api",
        "trace_context": {
            "traceparent": "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
        },
    }
    assert set(row["provenance"]["trace_context"]) <= {"traceparent", "tracestate"}


def test_existing_job_trace_context_survives_retrying_request_context() -> None:
    with _current_span(_TRACE_ID, _SPAN_ID):
        first = capture_job_trace_provenance({"source": "api"})

    with _current_span(_OTHER_TRACE_ID, _OTHER_SPAN_ID):
        retry = capture_job_trace_provenance({**first, "retry_of_job_id": "job-1"})

    assert retry["trace_context"] == first["trace_context"]
    assert retry["retry_of_job_id"] == "job-1"


def test_job_trace_links_fail_closed_for_malformed_or_oversized_context() -> None:
    assert job_trace_links({}) == []
    assert job_trace_links({"trace_context": "not-a-carrier"}) == []
    assert job_trace_links({"trace_context": {"traceparent": "not-w3c"}}) == []
    assert job_trace_links({"trace_context": {"traceparent": "x" * 513}}) == []


class _RecordingTracer:
    def __init__(self) -> None:
        self.name: str | None = None
        self.kwargs: dict = {}

    def start_as_current_span(self, name: str, **kwargs):
        self.name = name
        self.kwargs = kwargs
        return nullcontext()


def test_fenced_worker_links_each_attempt_to_durable_producer_context(monkeypatch) -> None:
    with _current_span(_TRACE_ID, _SPAN_ID):
        provenance = capture_job_trace_provenance({"source": "api"})

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="test", version="1.0"),
        provenance=provenance,
    )
    raw_client = SimpleNamespace(storage=SimpleNamespace())
    worker = FencedJobWorker()
    worker._client = raw_client
    worker._remember_execution_token(str(job.id), "attempt-token")

    tracer = _RecordingTracer()
    monkeypatch.setattr(fenced_job_worker, "_tracer", tracer)
    handled: list[str] = []
    worker.register("test", "1.0", lambda _job, _client: handled.append("yes") or [])

    worker._capabilities["test:1.0"](job, raw_client)

    assert handled == ["yes"]
    assert tracer.name == "job.execution_attempt"
    assert tracer.kwargs["attributes"]["execution_token"] == "attempt-token"
    links = tracer.kwargs["links"]
    assert len(links) == 1
    assert links[0].context.trace_id == _TRACE_ID
    assert links[0].context.span_id == _SPAN_ID
