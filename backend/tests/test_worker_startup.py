from __future__ import annotations

import pytest
from pydantic import ValidationError

import worker as worker_entry


class _FakeWorker:
    def __init__(self, events: list[str], **_kwargs) -> None:
        self._events = events

    def register(self, *_args) -> None:
        pass

    def run(self) -> None:
        self._events.append("run")

    def stop(self) -> None:
        self._events.append("stop")


def _stub_worker_runtime(monkeypatch, events: list[str]) -> None:
    monkeypatch.setattr(worker_entry, "configure_logging", lambda *_args: None)
    monkeypatch.setattr(worker_entry, "init_telemetry", lambda *_args: None)
    monkeypatch.setattr(worker_entry, "init_sentry", lambda *_args: None)
    monkeypatch.setattr(
        worker_entry,
        "FencedJobWorker",
        lambda **kwargs: _FakeWorker(events, **kwargs),
    )
    monkeypatch.setattr(
        worker_entry.capability_module,
        "register_all_capabilities",
        lambda _worker: None,
    )
    monkeypatch.setattr(worker_entry, "register_perceptual_capability", lambda _worker: None)
    monkeypatch.setattr(worker_entry, "prewarm_beat_this_inference", lambda: None)
    monkeypatch.setattr(worker_entry.signal, "signal", lambda *_args: None)


def test_worker_prewarms_transcription_then_beats_before_run(monkeypatch):
    events: list[str] = []
    _stub_worker_runtime(monkeypatch, events)
    monkeypatch.delenv("WORKER_CONCURRENCY", raising=False)
    monkeypatch.setattr(
        worker_entry,
        "prewarm_basic_pitch_inference",
        lambda: events.append("basic_pitch") or True,
    )
    monkeypatch.setattr(
        worker_entry,
        "prewarm_librosa_beat_tracking",
        lambda: events.append("librosa") or True,
    )

    worker_entry.main()

    assert events == ["basic_pitch", "librosa", "run"]


def test_worker_continues_to_beats_and_run_when_basic_pitch_prewarm_fails(monkeypatch):
    events: list[str] = []
    _stub_worker_runtime(monkeypatch, events)
    monkeypatch.delenv("WORKER_CONCURRENCY", raising=False)

    def fail_basic_pitch_prewarm() -> bool:
        events.append("basic_pitch")
        raise RuntimeError("synthetic Basic Pitch warmup failure")

    monkeypatch.setattr(
        worker_entry,
        "prewarm_basic_pitch_inference",
        fail_basic_pitch_prewarm,
    )
    monkeypatch.setattr(
        worker_entry,
        "prewarm_librosa_beat_tracking",
        lambda: events.append("librosa") or True,
    )

    worker_entry.main()

    assert events == ["basic_pitch", "librosa", "run"]


def test_worker_still_runs_when_librosa_prewarm_fails(monkeypatch):
    events: list[str] = []
    _stub_worker_runtime(monkeypatch, events)
    monkeypatch.delenv("WORKER_CONCURRENCY", raising=False)
    monkeypatch.setattr(
        worker_entry,
        "prewarm_basic_pitch_inference",
        lambda: events.append("basic_pitch") or True,
    )

    def fail_librosa_prewarm() -> bool:
        events.append("librosa")
        raise RuntimeError("synthetic librosa warmup failure")

    monkeypatch.setattr(
        worker_entry,
        "prewarm_librosa_beat_tracking",
        fail_librosa_prewarm,
    )

    worker_entry.main()

    assert events == ["basic_pitch", "librosa", "run"]


def test_worker_passes_typed_concurrency_to_job_worker(monkeypatch):
    events: list[str] = []
    captured: dict[str, int] = {}
    _stub_worker_runtime(monkeypatch, events)
    monkeypatch.setenv("WORKER_CONCURRENCY", "4")
    monkeypatch.setattr(worker_entry, "prewarm_basic_pitch_inference", lambda: True)
    monkeypatch.setattr(worker_entry, "prewarm_librosa_beat_tracking", lambda: True)

    def make_worker(**kwargs):
        captured.update(kwargs)
        return _FakeWorker(events, **kwargs)

    monkeypatch.setattr(worker_entry, "FencedJobWorker", make_worker)

    worker_entry.main()

    assert captured == {"max_workers": 4}
    assert events == ["run"]


def test_invalid_worker_concurrency_fails_before_expensive_warmup(monkeypatch):
    events: list[str] = []
    _stub_worker_runtime(monkeypatch, events)
    monkeypatch.setenv("WORKER_CONCURRENCY", "0")
    monkeypatch.setattr(
        worker_entry,
        "prewarm_basic_pitch_inference",
        lambda: events.append("basic_pitch") or True,
    )
    monkeypatch.setattr(
        worker_entry,
        "prewarm_librosa_beat_tracking",
        lambda: events.append("librosa") or True,
    )

    with pytest.raises(ValidationError):
        worker_entry.main()

    assert events == []
