"""Low-cardinality timing instrumentation for the composite understand workflow.

The product-level import benchmark measures user-visible readiness. This module
adds worker-side decomposition without changing capability behavior: queue wait,
the three sequential child stages that currently make up ``understand``, and a
small allowlist of expensive operations inside those stages.

Instrumentation is installed once at worker startup. Child capability wrappers
record timing only while invoked from ``handle_understand``; independently
queued transcribe/analyze/score jobs keep their existing metrics only.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from opentelemetry import metrics

logger = logging.getLogger("performance")

_UNDERSTAND_STAGES = ("transcribe", "analyze", "score")
_UNDERSTAND_OPERATIONS = (
    "transcribe.pipeline",
    "transcribe.playback_synthesis",
    "analyze.beat_tracking",
    "analyze.music_analysis",
    "score.beat_tracking",
    "score.notation",
    "score.playback_synthesis",
)
_ALLOWED_OUTCOMES = ("succeeded", "failed")
_understand_active: ContextVar[bool] = ContextVar("understand_active", default=False)
_understand_stage: ContextVar[str | None] = ContextVar("understand_stage", default=None)
_worker_performance_metrics: tuple[Any, Any, Any] | None = None


def understand_stage_metric_attributes(stage: str, outcome: str) -> dict[str, str]:
    """Return bounded dimensions for composite-stage timing metrics."""

    if stage not in _UNDERSTAND_STAGES:
        raise ValueError(f"unknown understand stage: {stage}")
    if outcome not in _ALLOWED_OUTCOMES:
        raise ValueError(f"unknown understand stage outcome: {outcome}")
    return {"understand.stage": stage, "job.outcome": outcome}


def understand_operation_metric_attributes(operation: str, outcome: str) -> dict[str, str]:
    """Return bounded dimensions for expensive operations inside understand."""

    if operation not in _UNDERSTAND_OPERATIONS:
        raise ValueError(f"unknown understand operation: {operation}")
    if outcome not in _ALLOWED_OUTCOMES:
        raise ValueError(f"unknown understand operation outcome: {outcome}")
    return {"understand.operation": operation, "job.outcome": outcome}


def queue_wait_metric_attributes(capability: str) -> dict[str, str]:
    """Return bounded queue-wait dimensions; never include job identifiers."""

    return {"job.capability": capability or "unknown"}


def _get_metrics() -> tuple[Any, Any, Any]:
    global _worker_performance_metrics
    if _worker_performance_metrics is None:
        meter = metrics.get_meter("listencloser-worker")
        _worker_performance_metrics = (
            meter.create_histogram(
                "hello_ai.worker.queue_wait",
                unit="s",
                description="Time from durable job creation until handler execution begins.",
            ),
            meter.create_histogram(
                "hello_ai.worker.understand.stage.duration",
                unit="s",
                description="Duration of bounded child stages inside the understand workflow.",
            ),
            meter.create_histogram(
                "hello_ai.worker.understand.operation.duration",
                unit="s",
                description="Duration of bounded expensive operations inside understand stages.",
            ),
        )
    return _worker_performance_metrics


def _record_queue_wait(capability: str, duration_seconds: float) -> None:
    queue_wait, _stage_duration, _operation_duration = _get_metrics()
    duration = max(0.0, float(duration_seconds))
    queue_wait.record(duration, queue_wait_metric_attributes(capability))
    logger.info(
        "worker_queue_wait",
        extra={
            "capability": capability or "unknown",
            "duration_seconds": round(duration, 6),
        },
    )


def _record_stage(stage: str, outcome: str, duration_seconds: float) -> None:
    _queue_wait, stage_duration, _operation_duration = _get_metrics()
    duration = max(0.0, float(duration_seconds))
    stage_duration.record(duration, understand_stage_metric_attributes(stage, outcome))
    logger.info(
        "understand_stage_timing",
        extra={
            "stage": stage,
            "outcome": outcome,
            "duration_seconds": round(duration, 6),
        },
    )


def _record_operation(operation: str, outcome: str, duration_seconds: float) -> None:
    _queue_wait, _stage_duration, operation_duration = _get_metrics()
    duration = max(0.0, float(duration_seconds))
    operation_duration.record(duration, understand_operation_metric_attributes(operation, outcome))
    logger.info(
        "understand_operation_timing",
        extra={
            "operation": operation,
            "outcome": outcome,
            "duration_seconds": round(duration, 6),
        },
    )


def _queue_wait_seconds(job: Any) -> float:
    created_at = getattr(job, "created_at", None)
    if created_at is None:
        return 0.0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - created_at).total_seconds())


def _wrap_child(stage: str, handler: Callable[..., list[str]]) -> Callable[..., list[str]]:
    @functools.wraps(handler)
    def wrapped(job: Any, client: Any) -> list[str]:
        if not _understand_active.get():
            return handler(job, client)

        started = time.perf_counter()
        outcome = "succeeded"
        stage_token = _understand_stage.set(stage)
        try:
            return handler(job, client)
        except Exception:
            outcome = "failed"
            raise
        finally:
            _understand_stage.reset(stage_token)
            _record_stage(stage, outcome, time.perf_counter() - started)

    return wrapped


def _wrap_operation(
    handler: Callable[..., Any],
    operation_by_stage: dict[str, str],
) -> Callable[..., Any]:
    """Time one existing function only in the relevant understand child stage."""

    @functools.wraps(handler)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        operation = operation_by_stage.get(_understand_stage.get() or "")
        if operation is None:
            return handler(*args, **kwargs)

        started = time.perf_counter()
        outcome = "succeeded"
        try:
            return handler(*args, **kwargs)
        except Exception:
            outcome = "failed"
            raise
        finally:
            _record_operation(operation, outcome, time.perf_counter() - started)

    return wrapped


def _install_operation_instrumentation(capabilities: ModuleType) -> None:
    """Wrap existing expensive seams without importing heavyweight ML modules."""

    music_features = getattr(capabilities, "music_features", None)
    if music_features is not None:
        music_features.transcribe_audio = _wrap_operation(
            music_features.transcribe_audio,
            {"transcribe": "transcribe.pipeline"},
        )
        music_features.estimate_beats_with_engine = _wrap_operation(
            music_features.estimate_beats_with_engine,
            {
                "analyze": "analyze.beat_tracking",
                "score": "score.beat_tracking",
            },
        )
        music_features.notation_with_engine = _wrap_operation(
            music_features.notation_with_engine,
            {"score": "score.notation"},
        )
        music_features.midi_to_wav = _wrap_operation(
            music_features.midi_to_wav,
            {
                "transcribe": "transcribe.playback_synthesis",
                "score": "score.playback_synthesis",
            },
        )

    analysis_module = getattr(capabilities, "analyze", None)
    if analysis_module is not None:
        analysis_module.analyze_midi = _wrap_operation(
            analysis_module.analyze_midi,
            {"analyze": "analyze.music_analysis"},
        )


def install_understand_instrumentation(capabilities: ModuleType) -> None:
    """Instrument one capabilities module in place, exactly once.

    ``handle_understand`` resolves its child handlers through module globals at
    call time. Wrapping those globals lets us decompose the existing workflow
    without changing its orchestration, persistence, retry, or progress logic.
    A ContextVar scopes stage and operation recording to understand calls, so
    the same wrapped functions remain safe for standalone capabilities.
    """

    if getattr(capabilities, "_listencloser_understand_instrumented", False):
        return

    _install_operation_instrumentation(capabilities)

    for stage in _UNDERSTAND_STAGES:
        attr = f"handle_{stage}"
        handler = getattr(capabilities, attr)
        setattr(capabilities, attr, _wrap_child(stage, handler))

    original_understand = capabilities.handle_understand

    @functools.wraps(original_understand)
    def instrumented_understand(job: Any, client: Any) -> list[str]:
        capability = f"{job.capability.name}:{job.capability.version}"
        _record_queue_wait(capability, _queue_wait_seconds(job))
        token = _understand_active.set(True)
        try:
            return original_understand(job, client)
        finally:
            _understand_active.reset(token)

    capabilities.handle_understand = instrumented_understand
    capabilities._listencloser_understand_instrumented = True
