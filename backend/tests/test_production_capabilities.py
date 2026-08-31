from __future__ import annotations

from collections.abc import Callable

from domain.production_capabilities import register_production_capabilities


class _FakeWorker:
    def __init__(self) -> None:
        self.registered: list[tuple[str, str, Callable[..., list[str]]]] = []

    def register(
        self,
        name: str,
        version: str,
        handler: Callable[..., list[str]],
    ) -> None:
        self.registered.append((name, version, handler))


def _handler(*_args) -> list[str]:
    return []


def test_retired_describe_is_not_registered_for_production() -> None:
    worker = _FakeWorker()

    def register_all(registrar) -> None:
        registrar.register("transcribe", "1.0", _handler)
        registrar.register("describe", "1.0", _handler)
        registrar.register("score", "1.0", _handler)

    register_production_capabilities(worker, register_all)

    assert [(name, version) for name, version, _handler_fn in worker.registered] == [
        ("transcribe", "1.0"),
        ("score", "1.0"),
    ]


def test_unknown_future_capability_is_forwarded_by_default() -> None:
    worker = _FakeWorker()

    def register_all(registrar) -> None:
        registrar.register("future_capability", "2.0", _handler)

    register_production_capabilities(worker, register_all)

    assert [(name, version) for name, version, _handler_fn in worker.registered] == [
        ("future_capability", "2.0")
    ]
