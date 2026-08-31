from uuid import UUID

import pytest

from domain import capabilities
from domain.models import ArtifactKind, Capability, Job


@pytest.mark.parametrize(
    ("content", "expected_sha256"),
    [
        (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        (b"abc\n", "edeaaff3f1774ad2888673770c6d64097e391bc362d7d6fb34982ddf0efd18cb"),
    ],
)
def test_generated_output_version_persists_exact_content_identity(
    monkeypatch, content, expected_sha256
):
    captured = {}

    class FakeArtifactRepo:
        def __init__(self, _client):
            pass

        def create(self, artifact, owner_id):
            assert owner_id == "owner-1"
            return artifact

    class FakeVersionRepo:
        def __init__(self, _client):
            pass

        def create(self, version, owner_id):
            assert owner_id == "owner-1"
            captured["version"] = version
            return version

    monkeypatch.setattr(capabilities, "ArtifactRepo", FakeArtifactRepo)
    monkeypatch.setattr(capabilities, "VersionRepo", FakeVersionRepo)

    job = Job(
        workflow_id=UUID("11111111-1111-1111-1111-111111111111"),
        capability=Capability(name="test", version="1"),
    )
    content_before = bytes(content)

    version_id = capabilities._create_output_version(
        None,
        UUID("22222222-2222-2222-2222-222222222222"),
        ArtifactKind.audio_rendered,
        "jobs/test/attempt-0/output.bin",
        content,
        None,
        job,
        "owner-1",
    )

    version = captured["version"]
    assert version.id == version_id
    assert version.byte_size == len(content_before)
    assert version.sha256 == expected_sha256
    assert content == content_before
    assert len(version.sha256) == 64
    assert version.sha256 == version.sha256.lower()
