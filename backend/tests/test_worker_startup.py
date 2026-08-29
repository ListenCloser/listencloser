from __future__ import annotations

import worker as worker_entry


class _FakeWorker:
    def __init__(self, events: list[str], **_kwargs) -> None:
        self._events = events

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
        "JobWorker",
        lambda **kwargs: _FakeWorker(events, **kwargs),
    )
    monkeypatch.setattr(
        worker_entry.capability_module,
        "register_all_capabilities",
        lambda _worker: None,
    )
    monkeypatch.setattr(worker_entry, "register_perceptual_capability", lambda _worker: None)
    monkeypatch.setattr(worker_entry.signal, "signal", lambda *_args: None)


def test_worker_prewarms_before_run(monkeypatch):
    events: list[str] = []
    _stub_worker_runtime(monkeypatch, events)
    monkeypatch.setattr(
        worker_entry,
        "prewarm_librosa_beat_tracking",
        lambda: events.append("prewarm") or True,
    )

    worker_entry.main()

    assert events == ["prewarm", "run"]


def test_worker_still_runs_when_prewarm_fails(monkeypatch):
    events: list[str] = []
    _stub_worker_runtime(monkeypatch, events)

    def fail_prewarm() -> bool:
        events.append("prewarm")
        raise RuntimeError("synthetic warmup failure")

    monkeypatch.setattr(worker_entry, "prewarm_librosa_beat_tracking", fail_prewarm)

    worker_entry.main()

    assert events == ["prewarm", "run"]
