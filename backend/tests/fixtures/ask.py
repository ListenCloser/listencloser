"""Shared fixtures for the grounded contextual Ask tests."""

from __future__ import annotations

import pytest

from ask.contracts import AskContext, AskInsight, AskInsightSpan, AskSelection, AskVisibleInsight


def make_insight(
    *,
    id: str = "insight-key",
    kind: str = "key",
    claim: str = "Key: C major",
    start_seconds: float | None = 0.0,
    end_seconds: float | None = 4.0,
    start_measure: int | None = 1,
    end_measure: int | None = 4,
) -> AskInsight:
    return AskInsight(
        id=id,
        version_id="version-1",
        kind=kind,
        claim=claim,
        span=AskInsightSpan(
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            start_measure=start_measure,
            end_measure=end_measure,
        ),
        entity_ids=[],
    )


def make_context(
    *,
    visible_insights: list[AskVisibleInsight] | None = None,
    selection: AskSelection | None = None,
    representation: str = "score",
) -> AskContext:
    return AskContext(
        workId="00000000-0000-0000-0000-000000000001",
        representationId=representation,  # type: ignore[arg-type]
        currentTime=2.0,
        playbackSourceId="source-1",
        selection=selection,
        visibleInsights=visible_insights or [],
    )


@pytest.fixture
def whole_work_context():
    return make_context(
        visible_insights=[
            AskVisibleInsight(insight=make_insight(), category="whole-work"),
        ]
    )


@pytest.fixture
def selection_context():
    return make_context(
        selection=AskSelection(
            timeRange={"start": 1.0, "end": 5.0, "domain": "performance"},
            noteIds=["note-1", "note-2"],
            measureRange={"start": 1, "end": 4},
            provenance={"origin": "piano_roll", "timeExact": True, "measureApproximate": False},  # type: ignore[arg-type]
        ),
        visible_insights=[
            AskVisibleInsight(
                insight=make_insight(
                    id="insight-selection",
                    claim="Chord: G7",
                    start_seconds=1.0,
                    end_seconds=5.0,
                    start_measure=1,
                    end_measure=4,
                ),
                category="selection",
            ),
            AskVisibleInsight(insight=make_insight(), category="whole-work"),
        ],
    )


@pytest.fixture
def no_selection_context():
    """Context with no selection and no time/measure spans in insights."""
    return make_context(
        visible_insights=[
            AskVisibleInsight(
                insight=make_insight(
                    id="insight-key",
                    claim="Key: C major",
                    start_seconds=None,
                    end_seconds=None,
                    start_measure=None,
                    end_measure=None,
                ),
                category="whole-work",
            ),
        ]
    )


@pytest.fixture
def selection_notation_context():
    """Selection with notation domain time range."""
    return make_context(
        selection=AskSelection(
            timeRange={"start": 10.0, "end": 20.0, "domain": "notation"},
            noteIds=["note-a", "note-b"],
            provenance={"origin": "score", "timeExact": False, "measureApproximate": True},  # type: ignore[arg-type]
        ),
        visible_insights=[
            AskVisibleInsight(
                insight=make_insight(
                    id="insight-notation", claim="Note: C4", start_seconds=10.0, end_seconds=20.0
                ),
                category="selection",
            ),
        ],
    )
