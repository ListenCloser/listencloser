from types import SimpleNamespace

from domain.api import _signed_url
from domain.capabilities import register_all_capabilities
from domain.models import ArtifactKind


def test_audio_rendered_is_distinct_from_enhanced_audio():
    assert ArtifactKind.audio_rendered.value == "audio_rendered"
    assert ArtifactKind.audio_rendered is not ArtifactKind.audio_enhanced


def test_signed_url_normalizes_supabase_response_shapes():
    assert _signed_url({"signedURL": "https://example.test/a"}) == (
        "https://example.test/a"
    )
    assert _signed_url(
        SimpleNamespace(data={"signed_url": "https://example.test/b"})
    ) == "https://example.test/b"


def test_production_worker_registers_score_capability():
    registrations: list[tuple[str, str]] = []

    class Worker:
        def register(self, name, version, _handler):
            registrations.append((name, version))

    register_all_capabilities(Worker())

    assert ("transcribe", "1.0") in registrations
    assert ("analyze", "1.0") in registrations
    assert ("score", "1.0") in registrations
