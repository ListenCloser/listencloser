from uuid import uuid4

import pytest

from domain.relation_observations import SecondsSpanLocator
from domain.rhythm_density_relations import (
    RhythmDensityEvidence,
    compare_rhythm_density_spans,
)


def _window(
    start: float,
    end: float,
    density: float,
    *,
    window_size: float = 2.0,
    step_size: float = 1.0,
) -> dict:
    return {
        "start": start,
        "end": end,
        "density": density,
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": window_size,
        "step_size": step_size,
    }


def _evidence(windows: list[dict]):
    source_version_id = uuid4()
    return (
        RhythmDensityEvidence(
            evidence_id=uuid4(),
            source_version_id=source_version_id,
            windows=windows,
            coverage=None,
            pulse_provenance={"engine": "beat_this"},
        ),
        source_version_id,
    )


def _locator(source_version_id, start: float, end: float):
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


@pytest.mark.parametrize(
    ("span", "expected_fragment"),
    [
        ((4.0, 10.0), "outside local rhythm density evidence coverage"),
        ((1.0, 7.0), "outside local rhythm density evidence coverage"),
    ],
)
def test_remote_series_bounds_do_not_hide_missing_local_edge_coverage(span, expected_fragment):
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 1.0),
            _window(1.0, 3.0, 1.0),
            _window(8.0, 10.0, 2.0),
            _window(9.0, 11.0, 2.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, *span),
        comparison_locator=_locator(source_version_id, 8.0, 11.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any(expected_fragment in reason for reason in result.sufficiency.reasons)


def test_internal_gap_without_persistence_coverage_withholds():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 1.0),
            _window(1.0, 3.0, 1.0),
            _window(8.0, 10.0, 2.0),
            _window(9.0, 11.0, 2.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 10.0),
        comparison_locator=_locator(source_version_id, 8.0, 11.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("internal gap" in reason for reason in result.sufficiency.reasons)


def test_sub_hop_edge_slack_remains_supported_with_remote_windows_present():
    evidence, source_version_id = _evidence(
        [
            _window(1.0, 3.0, 1.0),
            _window(2.0, 4.0, 3.0),
            _window(10.0, 12.0, 9.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.25, 4.75),
        comparison_locator=_locator(source_version_id, 1.0, 3.0),
    )

    assert result.sufficiency.status == "supported"
    assert len(result.measurements) == 1
    assert result.measurements[0].subject_window_count == 2
    assert result.measurements[0].subject_value == 2.0


def test_tempo_changing_span_uses_selected_local_hop_not_remote_series_boundary():
    evidence, source_version_id = _evidence(
        [
            # Same beat-domain contract, materially different seconds durations.
            _window(0.0, 4.0, 1.0),
            _window(2.0, 4.5, 2.0),
            _window(4.0, 5.0, 3.0),
            # A remote window must not make the earlier requested span look covered.
            _window(10.0, 12.0, 4.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 6.0),
        comparison_locator=_locator(source_version_id, 0.0, 4.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any(
        "outside local rhythm density evidence coverage" in reason
        for reason in result.sufficiency.reasons
    )
