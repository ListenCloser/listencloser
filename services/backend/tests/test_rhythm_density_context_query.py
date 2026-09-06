from datetime import UTC, datetime, timedelta
from uuid import uuid4

from domain.models import Artifact, ArtifactKind, Insight, Version, Work
from domain.rhythm_density_context_query import (
    RhythmDensityContextQuery,
    query_persisted_rhythm_density_context,
)
from domain.work_bundle_repository import WorkBundleSnapshot


def _window(start: float, end: float, density: float) -> dict:
    return {
        "start": start,
        "end": end,
        "density": density,
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": 2.0,
        "step_size": 1.0,
    }


def _windows() -> list[dict]:
    return [
        _window(0.0, 2.0, 1.0),
        _window(1.0, 3.0, 1.0),
        _window(2.0, 4.0, 2.0),
        _window(3.0, 5.0, 4.0),
        _window(4.0, 6.0, 5.0),
        _window(5.0, 7.0, 4.0),
        _window(6.0, 8.0, 2.0),
        _window(7.0, 9.0, 3.0),
        _window(8.0, 10.0, 1.0),
    ]


def _coverage(windows: list[dict]) -> dict:
    return {
        "policy_version": "complete_series_v1",
        "total_generated_window_count": len(windows),
        "stored_window_count": len(windows),
        "start_seconds": windows[0]["start"],
        "end_seconds": windows[-1]["end"],
        "truncated": False,
    }


def _snapshot(*, artifact_kind: ArtifactKind = ArtifactKind.midi_performance):
    work = Work(project_id=uuid4(), title="Context query test")
    artifact = Artifact(
        work_id=work.id,
        kind=artifact_kind,
        mime_type="audio/midi",
    )
    version = Version(
        artifact_id=artifact.id,
        storage_key="analysis-input.mid",
        storage_bucket="artifacts",
        created_by="owner",
        label="Analysis MIDI",
    )
    snapshot = WorkBundleSnapshot(
        work=work,
        artifacts=[artifact],
        versions_by_artifact={artifact.id: [version]},
        jobs=[],
    )
    return snapshot, version


def _density_insight(
    version_id,
    *,
    created_at: datetime | None = None,
    evidence: dict | None = None,
    kind: str = "rhythm_density",
) -> Insight:
    windows = _windows()
    return Insight(
        version_id=version_id,
        kind=kind,
        claim="Note density profile",
        evidence=(
            {"windows": windows, "coverage": _coverage(windows)} if evidence is None else evidence
        ),
        confidence=None,
        provenance={
            "method": "computed",
            "engine": {"engine": "beat_this", "engine_version": "1.1.0"},
        },
        created_at=created_at or datetime(2026, 8, 30, 1, tzinfo=UTC),
        created_by="owner",
    )


def _query(*, origin="user_selected", start: float = 4.0, end: float = 6.0):
    return RhythmDensityContextQuery(
        subject_start_seconds=start,
        subject_end_seconds=end,
        subject_origin=origin,
    )


def test_supported_query_uses_exact_authorized_version_and_preserves_context_contract():
    snapshot, version = _snapshot()
    density = _density_insight(version.id)
    other = _density_insight(version.id, kind="rhythm")
    calls = []

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: calls.append(loaded_version) or [other, density],
    )

    assert calls == [version]
    assert result.status == "supported"
    assert result.rhythm_density_insight_id == density.id
    assert result.reasons == []
    assert result.finding is not None
    assert result.finding.subject_locator.source_artifact_version_id == version.id
    assert result.finding.subject_locator.authority == "user_selected"
    assert result.finding.subject_origin == "user_selected"
    assert result.finding.selection_conditioned_on_rhythm_density is False
    assert result.finding.available_actions == ["focus", "evidence"]
    assert result.finding.support_refs[0].id == f"{density.id}:rhythm_density"
    assert result.finding.provenance["pulse_provenance"] == {
        "engine": "beat_this",
        "engine_version": "1.1.0",
    }


def test_user_selected_neutral_context_remains_supported_through_persisted_query():
    snapshot, version = _snapshot()
    windows = [_window(float(i), float(i + 2), 4.0) for i in range(9)]
    density = _density_insight(
        version.id,
        evidence={"windows": windows, "coverage": _coverage(windows)},
    )

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: [density],
    )

    assert result.status == "supported"
    assert result.reasons == []
    assert result.finding is not None
    assert result.finding.subject_origin == "user_selected"
    assert result.finding.selection_conditioned_on_rhythm_density is False
    assert result.finding.measurements[0].direction == "unchanged"
    assert result.finding.measurements[0].subject_value == 4.0
    assert result.finding.measurements[0].reference_median == 4.0
    assert result.finding.headline == (
        "Median event density here matches the median elsewhere in this Work (4 events/beat)."
    )


def test_legacy_density_peak_is_explicit_and_selection_conditioned():
    snapshot, version = _snapshot(artifact_kind=ArtifactKind.midi_corrected)
    density = _density_insight(version.id)

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(origin="legacy_density_peak"),
        load_insights=lambda loaded_version: [density],
    )

    assert result.status == "supported"
    assert result.finding is not None
    assert result.finding.subject_locator.authority == "explicit"
    assert result.finding.selection_conditioned_on_rhythm_density is True
    assert result.finding.provenance["salience_independence_claimed"] is False


def test_missing_density_insight_is_unavailable_after_one_exact_version_read():
    snapshot, version = _snapshot()
    calls = []
    rhythm = _density_insight(version.id, kind="rhythm")

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: calls.append(loaded_version) or [rhythm],
    )

    assert calls == [version]
    assert result.status == "unavailable"
    assert result.rhythm_density_insight_id is None
    assert result.finding is None


def test_version_must_belong_to_authorized_work_before_loader_runs():
    snapshot, _ = _snapshot()
    calls = []

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=uuid4(),
        query=_query(),
        load_insights=lambda loaded_version: calls.append(loaded_version) or [],
    )

    assert result.status == "failed"
    assert result.finding is None
    assert calls == []
    assert any("authorized Work snapshot" in reason for reason in result.reasons)


def test_density_owner_must_be_a_midi_version_before_loader_runs():
    snapshot, version = _snapshot(artifact_kind=ArtifactKind.audio_original)
    calls = []

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: calls.append(loaded_version) or [],
    )

    assert result.status == "failed"
    assert calls == []
    assert any("MIDI Version" in reason for reason in result.reasons)


def test_loader_failure_is_failed_without_raw_exception_text():
    snapshot, version = _snapshot()

    def _raise(_):
        raise RuntimeError("secret database detail")

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=_raise,
    )

    assert result.status == "failed"
    assert result.reasons == ["persisted Insights could not be loaded"]
    assert "secret database detail" not in " ".join(result.reasons)


def test_newest_density_insight_is_authoritative_and_corruption_does_not_fall_back():
    snapshot, version = _snapshot()
    base_time = datetime(2026, 8, 30, 1, tzinfo=UTC)
    older_valid = _density_insight(version.id, created_at=base_time)
    newer_corrupt = _density_insight(
        version.id,
        created_at=base_time + timedelta(minutes=1),
        evidence={"windows": "not-a-window-list", "coverage": {}},
    )

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: [older_valid, newer_corrupt],
    )

    assert result.status == "failed"
    assert result.rhythm_density_insight_id == newer_corrupt.id
    assert result.finding is None
    assert result.reasons == ["rhythm density Insight evidence could not be validated"]


def test_newest_density_insight_for_wrong_version_fails_closed():
    snapshot, version = _snapshot()
    base_time = datetime(2026, 8, 30, 1, tzinfo=UTC)
    valid = _density_insight(version.id, created_at=base_time)
    wrong_version = _density_insight(
        uuid4(),
        created_at=base_time + timedelta(minutes=1),
    )

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: [valid, wrong_version],
    )

    assert result.status == "failed"
    assert result.rhythm_density_insight_id == wrong_version.id
    assert any("Version is inconsistent" in reason for reason in result.reasons)


def test_incomplete_complete_series_contract_is_withheld_not_silently_weakened():
    snapshot, version = _snapshot()
    windows = _windows()
    incomplete = _density_insight(
        version.id,
        evidence={"windows": windows},
    )

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: [incomplete],
    )

    assert result.status == "withheld"
    assert result.rhythm_density_insight_id == incomplete.id
    assert result.finding is None
    assert any("complete_series_v1" in reason for reason in result.reasons)


def test_invalid_subject_span_is_withheld_with_relation_reason():
    snapshot, version = _snapshot()
    density = _density_insight(version.id)

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(start=6.0, end=4.0),
        load_insights=lambda loaded_version: [density],
    )

    assert result.status == "withheld"
    assert result.rhythm_density_insight_id == density.id
    assert result.finding is None
    assert any("positive duration" in reason for reason in result.reasons)


def test_non_insight_loader_payload_is_failed_before_candidate_selection():
    snapshot, version = _snapshot()

    result = query_persisted_rhythm_density_context(
        snapshot,
        density_owner_version_id=version.id,
        query=_query(),
        load_insights=lambda loaded_version: [{"kind": "rhythm_density"}],
    )

    assert result.status == "failed"
    assert result.finding is None
    assert result.reasons == ["persisted Insights could not be validated"]
