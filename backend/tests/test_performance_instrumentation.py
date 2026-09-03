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

    module.music_features = SimpleNamespace(
        transcribe_audio=lambda *_args, **_kwargs: calls.append("transcribe.pipeline"),
        estimate_beats_with_engine=lambda *_args, **_kwargs: calls.append("beat_tracking"),
        notation_with_engine=lambda *_args, **_kwargs: calls.append("score.notation"),
        midi_to_wav=lambda *_args, **_kwargs: calls.append("playback_synthesis"),
    )
    module.analyze = SimpleNamespace(
        analyze_midi=lambda *_args, **_kwargs: calls.append("analyze.music_analysis")
    )

    def child(stage: str):
        def handler(_job, _client):
            calls.append(stage)
            if stage == "transcribe":
                module.music_features.transcribe_audio(b"audio")
                module.music_features.midi_to_wav(b"midi")
            elif stage == "analyze":
                module.music_features.estimate_beats_with_engine(b"audio")
                module.analyze.analyze_midi("input.mid")
            elif stage == "score":
                module.music_features.estimate_beats_with_engine(b"audio")
                module.music_features.notation_with_engine(b"midi", [])
                module.music_features.midi_to_wav(b"midi")
            if fail_stage == stage:
                raise RuntimeError(f"{stage} failed")
            return [stage]

        return handler

    module.handle_transcribe = child("transcribe")
    module.handle_analyze = child("analyze")
    module.handle_score = child("score")

    def handle_understand(job, client):
        output: list[str] = []
        output.extend(module.handle_transcribe(job, client))
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
    assert perf.understand_operation_metric_attributes("score.notation", "succeeded") == {
        "understand.operation": "score.notation",
        "job.outcome": "succeeded",
    }

    with pytest.raises(ValueError, match="unknown understand stage"):
        perf.understand_stage_metric_attributes("user-controlled-stage", "succeeded")
    with pytest.raises(ValueError, match="unknown understand stage outcome"):
        perf.understand_stage_metric_attributes("score", "retry-17")
    with pytest.raises(ValueError, match="unknown understand operation"):
        perf.understand_operation_metric_attributes("user-controlled-operation", "succeeded")


def test_understand_records_queue_stages_and_operations_but_standalone_does_not(
    monkeypatch,
) -> None:
    queue_histogram = _Histogram()
    stage_histogram = _Histogram()
    operation_histogram = _Histogram()
    monkeypatch.setattr(
        perf,
        "_worker_performance_metrics",
        (queue_histogram, stage_histogram, operation_histogram),
    )

    module, calls = _fake_capabilities()
    perf.install_understand_instrumentation(module)
    perf.install_understand_instrumentation(module)  # idempotent

    result = module.handle_understand(_job(), object())

    assert result == ["transcribe", "analyze", "score"]
    assert calls == [
        "transcribe",
        "transcribe.pipeline",
        "playback_synthesis",
        "analyze",
        "beat_tracking",
        "analyze.music_analysis",
        "score",
        "beat_tracking",
        "score.notation",
        "playback_synthesis",
    ]
    assert len(queue_histogram.records) == 1
    queue_seconds, queue_attributes = queue_histogram.records[0]
    assert queue_seconds >= 0.0
    assert queue_attributes == {"job.capability": "understand:1.0"}

    assert [attrs["understand.stage"] for _duration, attrs in stage_histogram.records] == [
        "transcribe",
        "analyze",
        "score",
    ]
    assert all(attrs["job.outcome"] == "succeeded" for _duration, attrs in stage_histogram.records)
    assert all(duration >= 0.0 for duration, _attrs in stage_histogram.records)

    assert [attrs["understand.operation"] for _duration, attrs in operation_histogram.records] == [
        "transcribe.pipeline",
        "transcribe.playback_synthesis",
        "analyze.beat_tracking",
        "analyze.music_analysis",
        "score.beat_tracking",
        "score.notation",
        "score.playback_synthesis",
    ]
    assert all(
        attrs["job.outcome"] == "succeeded" for _duration, attrs in operation_histogram.records
    )

    stage_before = len(stage_histogram.records)
    operation_before = len(operation_histogram.records)
    module.handle_analyze(_job(), object())
    assert len(stage_histogram.records) == stage_before
    assert len(operation_histogram.records) == operation_before


def test_failed_child_records_failure_and_preserves_exception(monkeypatch) -> None:
    queue_histogram = _Histogram()
    stage_histogram = _Histogram()
    operation_histogram = _Histogram()
    monkeypatch.setattr(
        perf,
        "_worker_performance_metrics",
        (queue_histogram, stage_histogram, operation_histogram),
    )

    module, calls = _fake_capabilities(fail_stage="analyze")
    perf.install_understand_instrumentation(module)

    with pytest.raises(RuntimeError, match="analyze failed"):
        module.handle_understand(_job(), object())

    assert calls == [
        "transcribe",
        "transcribe.pipeline",
        "playback_synthesis",
        "analyze",
        "beat_tracking",
        "analyze.music_analysis",
    ]
    assert [attrs for _duration, attrs in stage_histogram.records] == [
        {"understand.stage": "transcribe", "job.outcome": "succeeded"},
        {"understand.stage": "analyze", "job.outcome": "failed"},
    ]
