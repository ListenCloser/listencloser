"""Server-authoritative Ask evidence resolution tests — no network."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ask.contracts import AskContext
from ask.evidence import canonicalize_ask_context, load_canonical_ask_context
from domain.models import Insight, Span


def _context(work_id, requested):
    return AskContext.model_validate(
        {
            "workId": str(work_id),
            "representationId": "piano_roll",
            "currentTime": 2.0,
            "selection": {
                "timeRange": {"start": 2.0, "end": 4.0, "domain": "performance"},
                "provenance": {
                    "origin": "piano_roll",
                    "timeExact": True,
                    "measureApproximate": False,
                },
            },
            "visibleInsights": requested,
        }
    )


def _requested(insight_id, *, claim="client-forged claim", category="whole-work"):
    return {
        "insight": {
            "id": str(insight_id),
            "version_id": str(uuid4()),
            "kind": "key",
            "claim": claim,
            "span": {},
            "entity_ids": [],
        },
        "category": category,
    }


def test_canonicalization_replaces_client_fields_recomputes_category_and_drops_invalid():
    work_id = uuid4()
    allowed_version = uuid4()
    foreign_version = uuid4()
    canonical_id = uuid4()
    unrelated_id = uuid4()
    foreign_id = uuid4()
    hidden_id = uuid4()

    canonical = Insight(
        id=canonical_id,
        version_id=allowed_version,
        kind="chord",
        claim="Chord: G7",
        span=Span(start_seconds=2.25, end_seconds=3.75),
        entity_ids=[uuid4()],
    )
    unrelated = Insight(
        id=unrelated_id,
        version_id=allowed_version,
        kind="key",
        claim="Key elsewhere",
        span=Span(start_seconds=10.0, end_seconds=12.0),
    )
    foreign = Insight(
        id=foreign_id,
        version_id=foreign_version,
        kind="key",
        claim="Foreign work key",
    )
    hidden = Insight(
        id=hidden_id,
        version_id=allowed_version,
        kind="definitely_unregistered_kind",
        claim="Must not reach Ask",
    )

    context = _context(
        work_id,
        [
            _requested(canonical_id),
            _requested(unrelated_id, category="selection"),
            _requested(foreign_id),
            _requested(hidden_id),
            _requested(canonical_id, claim="duplicate forged claim"),
            _requested("not-a-uuid"),
        ],
    )

    resolved = canonicalize_ask_context(
        context,
        persisted_insights=[canonical, unrelated, foreign, hidden],
        allowed_version_ids={allowed_version},
    )

    assert len(resolved.visibleInsights) == 1
    item = resolved.visibleInsights[0]
    assert item.insight.id == str(canonical_id)
    assert item.insight.version_id == str(allowed_version)
    assert item.insight.kind == "chord"
    assert item.insight.claim == "Chord: G7"
    assert item.insight.span.start_seconds == 2.25
    assert item.insight.entity_ids == [str(canonical.entity_ids[0])]
    assert item.category == "selection"


def test_batch_loader_proves_version_belongs_to_requested_work():
    work_id = uuid4()
    other_work_id = uuid4()
    allowed_artifact = uuid4()
    foreign_artifact = uuid4()
    allowed_version = uuid4()
    foreign_version = uuid4()
    allowed_insight = Insight(
        id=uuid4(),
        version_id=allowed_version,
        kind="key",
        claim="Key: C major",
    )
    foreign_insight = Insight(
        id=uuid4(),
        version_id=foreign_version,
        kind="key",
        claim="Key: F minor",
    )

    rows = {
        "insights": [
            allowed_insight.model_dump(mode="json"),
            foreign_insight.model_dump(mode="json"),
        ],
        "artifact_versions": [
            {"id": str(allowed_version), "artifact_id": str(allowed_artifact)},
            {"id": str(foreign_version), "artifact_id": str(foreign_artifact)},
        ],
        "artifacts": [
            {"id": str(allowed_artifact), "work_id": str(work_id)},
            {"id": str(foreign_artifact), "work_id": str(other_work_id)},
        ],
    }
    calls = []

    class FakeQuery:
        def __init__(self, table):
            self.table = table
            self.ids = []

        def select(self, columns):
            assert columns == "*"
            return self

        def in_(self, column, ids):
            assert column == "id"
            self.ids = list(ids)
            return self

        def execute(self):
            calls.append((self.table, tuple(self.ids)))
            allowed = set(self.ids)
            return SimpleNamespace(
                data=[row for row in rows[self.table] if str(row["id"]) in allowed]
            )

    class FakeSupabase:
        def table(self, table):
            return FakeQuery(table)

    context = _context(
        work_id,
        [_requested(allowed_insight.id), _requested(foreign_insight.id)],
    )
    resolved = load_canonical_ask_context(FakeSupabase(), context)

    assert [item.insight.id for item in resolved.visibleInsights] == [str(allowed_insight.id)]
    assert resolved.visibleInsights[0].insight.claim == "Key: C major"
    assert [name for name, _ in calls] == ["insights", "artifact_versions", "artifacts"]
