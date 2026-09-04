from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from domain.capabilities import ProgressReporter, handle_understand
from domain.models import ArtifactKind, Capability, Job


def _running_client(*, data=None):
    client = MagicMock()
    result = MagicMock()
    result.data = [{"id": "job"}] if data is None else data
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = result
    return client


def _payloads(client):
    return [call.args[0] for call in client.table.return_value.update.call_args_list]


def test_direct_progress_reporter_preserves_range_and_message():
    client = _running_client()
    job_id = uuid4()
    reporter = ProgressReporter(client, job_id)

    reporter.report(0.0, "starting")
    reporter.report(1.0, "done")

    assert _payloads(client) == [
        {"progress": 0.0, "status_message": "starting"},
        {"progress": 1.0, "status_message": "done"},
    ]


def test_child_progress_reporter_maps_and_clamps_parent_interval():
    client = _running_client()
    reporter = ProgressReporter(client, uuid4(), base=0.65, scale=0.20)

    reporter.report(-1.0, "low")
    reporter.report(0.5, "middle")
    reporter.report(2.0, "high")

    payloads = _payloads(client)
    assert payloads[0] == {"progress": pytest.approx(0.65), "status_message": "low"}
    assert payloads[1] == {"progress": pytest.approx(0.75), "status_message": "middle"}
    assert payloads[2] == {"progress": pytest.approx(0.85), "status_message": "high"}


def test_progress_reporter_preserves_running_job_fence_failure():
    client = _running_client(data=[])
    reporter = ProgressReporter(client, uuid4())

    with pytest.raises(RuntimeError, match="job is no longer running"):
        reporter.report(0.5, "cancel boundary")

    update = client.table.return_value.update
    update.return_value.eq.assert_called_once()
    update.return_value.eq.return_value.eq.assert_called_once_with("stage", "running")


def test_understand_uses_real_client_and_explicit_stage_progress():
    client = _running_client()
    original_audio_id = uuid4()
    midi_id = uuid4()
    rendered_audio_id = uuid4()
    notation_id = uuid4()
    score_id = uuid4()
    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="understand", version="1.0"),
        input_version_ids=[original_audio_id],
    )
    calls = []

    def transcribe(child_job, child_client, progress):
        calls.append(("transcribe", child_job, child_client))
        progress.report(0.0, "transcribe start")
        progress.report(1.0, "transcribe done")
        return [str(midi_id), str(rendered_audio_id)]

    def analyze(child_job, child_client, progress):
        calls.append(("analyze", child_job, child_client))
        progress.report(0.0, "analyze start")
        progress.report(0.5, "analyze middle")
        progress.report(1.0, "analyze done")
        return []

    def score(child_job, child_client, progress):
        calls.append(("score", child_job, child_client))
        progress.report(0.0, "score start")
        progress.report(0.5, "score middle")
        progress.report(1.0, "score done")
        return [str(notation_id), str(score_id)]

    def artifact_kind(_client, version_id: UUID):
        return ArtifactKind.midi_performance if version_id == midi_id else ArtifactKind.audio_rendered

    with (
        patch("domain.capabilities._cleanup_partial_job_outputs") as cleanup,
        patch("domain.capabilities._artifact_kind_for_version", side_effect=artifact_kind),
        patch("domain.capabilities.handle_transcribe", side_effect=transcribe),
        patch("domain.capabilities.handle_analyze", side_effect=analyze),
        patch("domain.capabilities.handle_score", side_effect=score),
    ):
        output_ids = handle_understand(job, client)

    cleanup.assert_called_once_with(client, [])
    assert [name for name, _, _ in calls] == ["transcribe", "analyze", "score"]
    assert all(child_client is client for _, _, child_client in calls)
    assert calls[0][1] is job
    assert calls[1][1].capability.name == "analyze"
    assert calls[1][1].input_version_ids == [midi_id, original_audio_id]
    assert calls[2][1].capability.name == "score"
    assert calls[2][1].input_version_ids == [midi_id, original_audio_id]
    assert output_ids == [str(midi_id), str(rendered_audio_id), str(notation_id), str(score_id)]

    payloads = _payloads(client)
    assert [payload["progress"] for payload in payloads] == pytest.approx(
        [0.0, 0.65, 0.65, 0.75, 0.85, 0.85, 0.925, 1.0]
    )
    assert [payload["status_message"] for payload in payloads] == [
        "transcribe start",
        "transcribe done",
        "analyze start",
        "analyze middle",
        "analyze done",
        "score start",
        "score middle",
        "score done",
    ]
