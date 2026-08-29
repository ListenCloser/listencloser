from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace

import pytest

from domain import performance_instrumentation as perf


class _Histogram:
    def __init__(self) -> None:
        self.records: list[tuple[float, dict[str, str]]] = []

    def record(self, value: float, attributes: dict[str, str]) -> None:
        self.records.append((value, attributes))


def _fake_capabilities(*, fail_stage: str | None = None) -> tuple[ModuleType, list[str]]:
    module = ModuleType("fake_capabilities")
    calls: list[str] = []

    def child(stage: str):
        def handler(_job, _client):
            calls.append(stage)
            if fail_stage == stage:
                raise RuntimeError(f"{stage} failed")
            return [stage]

        return handler

    module.handle_transcribe = child("transcribe")
    module.handle_audio_structure = child("audio_structure")
    module.handle_analyze = child("analyze")
    module.handle_score = child("score")

    def handle_understand(job, client):
        output: list[str] = []
        output.extend(module.handle_transcribe(job, client))
        output.extend(module.handle_audio_structure(job, client))
        output.extend(module.handle_analyze(job, client))
        output.extend(module.handle_score(job, client))
        return output

    module.handle_understand = handle_understand
    return module, calls


def _job():
    return SimpleNamespace(
        capability=SimpleNamespace(name="understand", version="1.0"),
        created_at=datetime.now(UTC) - timedelta(milliseconds=50),
    )


def test_metric_attributes_are_bounded() -> None:
    assert perf.queue_wait_metric_attributes("understand:1.0") == {
        "job.capability": "understand:1.0"
    }
    assert perf.understand_stage_metric_attributes("analyze", "succeeded") == {
        "understand.stage": "analyze",
        "job.outcome": "succeeded",
    }

    with pytest.raises(ValueError, match="unknown understand stage"):
        perf.understand_stage_metric_attributes("user-controlled-stage", "succeeded")
    with pytest.raises(ValueError, match="unknown understand stage outcome"):
        perf.understand_stage_metric_attributes("score", "retry-17")


def test_understand_records_queue_and_each_child_but_standalone_does_not(monkeypatch) -> None:
    queue_histogram = _Histogram()
    stage_histogram = _Histogram()
    monkeypatch.setattr(perf, "_worker_performance_metrics", (queue_histogram, stage_histogram))

    module, calls = _fake_capabilities()
    perf.install_understand_instrumentation(module)
    perf.install_understand_instrumentation(module)  # idempotent

    result = module.handle_understand(_job(), object())

    assert result == ["transcribe", "audio_structure", "analyze", "score"]
    assert calls == ["transcribe", "audio_structure", "analyze", "score"]
    assert len(queue_histogram.records) == 1
    queue_seconds, queue_attributes = queue_histogram.records[0]
    assert queue_seconds >= 0.0
    assert queue_attributes == {"job.capability": "understand:1.0"}

    assert [attrs["understand.stage"] for _duration, attrs in stage_histogram.records] == [
        "transcribe",
        "audio_structure",
        "analyze",
        "score",
    ]
    assert all(attrs["job.outcome"] == "succeeded" for _duration, attrs in stage_histogram.records)
    assert all(duration >= 0.0 for duration, _attrs in stage_histogram.records)

    before = len(stage_histogram.records)
    module.handle_analyze(_job(), object())
    assert len(stage_histogram.records) == before


def test_failed_child_records_failure_and_preserves_exception(monkeypatch) -> None:
    queue_histogram = _Histogram()
    stage_histogram = _Histogram()
    monkeypatch.setattr(perf, "_worker_performance_metrics", (queue_histogram, stage_histogram))

    module, calls = _fake_capabilities(fail_stage="analyze")
    perf.install_understand_instrumentation(module)

    with pytest.raises(RuntimeError, match="analyze failed"):
        module.handle_understand(_job(), object())

    assert calls == ["transcribe", "audio_structure", "analyze"]
    assert [attrs for _duration, attrs in stage_histogram.records] == [
        {"understand.stage": "transcribe", "job.outcome": "succeeded"},
        {"understand.stage": "audio_structure", "job.outcome": "succeeded"},
        {"understand.stage": "analyze", "job.outcome": "failed"},
    ]
