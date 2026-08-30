from uuid import uuid4

from domain.relation_observations import SecondsSpanLocator
from domain.rhythm_density_relations import (
    RhythmDensityEvidence,
    compare_rhythm_density_spans,
)


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


def _locator(source_version_id, start: float, end: float) -> SecondsSpanLocator:
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def test_duplicate_window_starts_withhold_instead_of_double_weighting_density():
    source_version_id = uuid4()
    evidence = RhythmDensityEvidence(
        evidence_id=uuid4(),
        source_version_id=source_version_id,
        windows=[
            _window(0.0, 2.0, 1.0),
            _window(0.0, 2.0, 9.0),
        ],
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("strictly ordered" in reason for reason in result.sufficiency.reasons)


def test_complete_series_metadata_with_internal_gap_withholds():
    source_version_id = uuid4()
    evidence = RhythmDensityEvidence(
        evidence_id=uuid4(),
        source_version_id=source_version_id,
        windows=[
            _window(0.0, 2.0, 1.0),
            _window(3.0, 5.0, 2.0),
        ],
        coverage={
            "policy_version": "complete_series_v1",
            "total_generated_window_count": 2,
            "stored_window_count": 2,
            "start_seconds": 0.0,
            "end_seconds": 5.0,
            "truncated": False,
        },
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 5.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("internal gap" in reason for reason in result.sufficiency.reasons)
