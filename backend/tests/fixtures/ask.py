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
) -> AskInsight:
    return AskInsight(
        id=id,
        version_id="version-1",
        kind=kind,
        claim=claim,
        span=AskInsightSpan(start_seconds=start_seconds, end_seconds=end_seconds),
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
def whole_work_context() -> AskContext:
    return make_context(
        visible_insights=[
            AskVisibleInsight(insight=make_insight(), category="whole-work"),
        ]
    )


@pytest.fixture
def selection_context() -> AskContext:
    return make_context(
        selection=AskSelection(
            timeRange={"start": 2.0, "end": 4.0, "domain": "performance"},
            noteIds=["note-1", "note-2"],
            provenance={"origin": "piano_roll", "timeExact": True, "measureApproximate": False},  # type: ignore[arg-type]
        ),
        visible_insights=[
            AskVisibleInsight(
                insight=make_insight(id="insight-selection", claim="Chord: G7", start_seconds=2.0, end_seconds=4.0),
                category="selection",
            ),
            AskVisibleInsight(insight=make_insight(), category="whole-work"),
        ],
    )