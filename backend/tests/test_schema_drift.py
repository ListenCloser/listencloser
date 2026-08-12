"""Static drift protection between the domain model and database migrations.

Guards the concrete regression where the domain model permits ``confidence =
None`` (heuristic evidence) but the database enforced ``NOT NULL``. This test
runs without a database and fails if either side of the contract drifts.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from domain.models import Insight

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"


def test_insight_confidence_is_nullable_in_domain():
    insight = Insight(
        version_id=uuid4(),
        kind="melody",
        claim="Range: C4–G5",
        confidence=None,
    )
    assert insight.confidence is None


def test_migrations_make_insights_confidence_nullable():
    sql = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql"))
    ).lower()
    assert "alter column confidence drop not null" in sql
    assert "alter column confidence drop default" in sql


def test_drop_not_null_migration_follows_insights_creation():
    files = sorted(MIGRATIONS.glob("*.sql"))
    create = next(
        p for p in files if "create table" in p.read_text() and "insights" in p.read_text()
    )
    drop = next(
        p
        for p in files
        if "alter column confidence drop not null" in p.read_text(encoding="utf-8").lower()
    )
    # The initial NOT NULL definition is historical; the drop must come after it.
    assert drop.name > create.name
