from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import domain.capabilities as capabilities
from domain.api.storage import signed_url
from domain.capabilities import _ProgressClient, register_all_capabilities
from domain.models import ArtifactKind, Capability, Job


def test_audio_rendered_is_distinct_from_enhanced_audio():
    assert ArtifactKind.audio_rendered.value == "audio_rendered"
    assert ArtifactKind.audio_rendered is not ArtifactKind.audio_enhanced


def test_signed_url_normalizes_supabase_response_shapes():
    assert signed_url({"signedURL": "https://example.test/a"}) == ("https://example.test/a")
    assert (
        signed_url(SimpleNamespace(data={"signed_url": "https://example.test/b"}))
        == "https://example.test/b"
    )


def test_production_worker_registers_score_capability():
    registrations: list[tuple[str, str]] = []

    class Worker:
        def register(self, name, version, _handler):
            registrations.append((name, version))

    register_all_capabilities(Worker())

    assert ("transcribe", "1.0") in registrations
    assert ("understand", "1.0") in registrations
    assert ("analyze", "1.0") in registrations
    assert ("score", "1.0") in registrations


def test_child_progress_is_mapped_into_parent_interval():
    table = MagicMock()
    client = MagicMock()
    client.table.return_value = table

    _ProgressClient(client, 0.65, 0.2).table("jobs").update(
        {"progress": 0.5, "status_message": "analyzing"}
    )

    table.update.assert_called_once_with({"progress": 0.75, "status_message": "analyzing"})


def test_progress_boundary_stops_a_job_that_is_no_longer_running():
    client = MagicMock()
    chain = client.table.return_value.update.return_value.eq.return_value.eq
    chain.return_value.execute.return_value = SimpleNamespace(data=[])

    with pytest.raises(RuntimeError, match="job is no longer running"):
        capabilities._update_progress(client, uuid4(), 0.5, "analyzing")

    chain.assert_called_once_with("stage", "running")


def test_retry_attempts_get_distinct_storage_keys():
    base = Job(
        workflow_id=uuid4(),
        capability=Capability(name="understand", version="1.0"),
    )
    retried = base.model_copy(
        update={"lifecycle": base.lifecycle.model_copy(update={"retry_count": 2})}
    )

    assert capabilities._job_storage_key(base, "score.musicxml").endswith(
        "/attempt-0/score.musicxml"
    )
    assert capabilities._job_storage_key(retried, "score.musicxml").endswith(
        "/attempt-2/score.musicxml"
    )


def test_retry_cleanup_removes_storage_before_cascading_artifact_rows():
    client = MagicMock()
    versions = client.table.return_value.select.return_value.in_
    versions.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "artifact_id": "artifact-midi",
                "storage_bucket": "artifacts",
                "storage_key": "jobs/old/transcribed.mid",
            },
            {
                "artifact_id": "artifact-score",
                "storage_bucket": "artifacts",
                "storage_key": "jobs/old/score.musicxml",
            },
        ]
    )

    capabilities._cleanup_partial_job_outputs(client, ["old-job"])

    client.storage.from_.return_value.remove.assert_called_once_with(
        [
            "jobs/old/transcribed.mid",
            "jobs/old/score.musicxml",
        ]
    )
    client.table.return_value.delete.return_value.in_.assert_called_once_with(
        "id", ["artifact-midi", "artifact-score"]
    )


def test_understand_runs_all_stages_without_browser_orchestration(monkeypatch):
    midi_id = uuid4()
    audio_id = uuid4()
    score_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="understand", version="1.0"),
        input_version_ids=[uuid4()],
    )
    original_audio_id = job.input_version_ids[0]
    analyzed_inputs = []
    derived_capabilities = []
    progress_ranges = []

    def transcribe(_job, derived_client):
        progress_ranges.append(("transcribe", derived_client._base, derived_client._scale))
        return [str(midi_id), str(audio_id)]

    monkeypatch.setattr(capabilities, "handle_transcribe", transcribe)
    monkeypatch.setattr(
        capabilities,
        "_artifact_kind_for_version",
        lambda _client, version_id: (
            ArtifactKind.midi_performance if version_id == midi_id else ArtifactKind.audio_rendered
        ),
    )

    def analyze(derived_job, derived_client):
        analyzed_inputs.extend(derived_job.input_version_ids)
        derived_capabilities.append(derived_job.capability.name)
        progress_ranges.append(("analyze", derived_client._base, derived_client._scale))
        return []

    def score(derived_job, derived_client):
        derived_capabilities.append(derived_job.capability.name)
        progress_ranges.append(("score", derived_client._base, derived_client._scale))
        return [str(score_id)]

    monkeypatch.setattr(capabilities, "handle_analyze", analyze)
    monkeypatch.setattr(capabilities, "handle_score", score)

    outputs = capabilities.handle_understand(job, MagicMock())

    assert outputs == [str(midi_id), str(audio_id), str(score_id)]
    assert analyzed_inputs == [midi_id, original_audio_id]
    assert derived_capabilities == ["analyze", "score"]
    assert progress_ranges == [
        ("transcribe", 0.0, 0.65),
        ("analyze", 0.65, 0.20),
        ("score", 0.85, 0.15),
    ]
