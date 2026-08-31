"""Worker capability registration truthfulness guards."""

from domain.capabilities import register_all_capabilities


class _RecordingWorker:
    def __init__(self) -> None:
        self.names: list[str] = []

    def register(self, name: str, version: str, handler) -> None:
        self.names.append(name)


def test_legacy_describe_capability_is_not_registered() -> None:
    worker = _RecordingWorker()
    register_all_capabilities(worker)

    assert "describe" not in worker.names
    assert "audio_structure" in worker.names
