"""Static drift protection between domain confidence semantics and migrations.

Confidence is optional unless a producer has a measured/calibrated score. These
checks keep the Pydantic models and persisted Postgres nullability/defaults in
sync so neither layer silently manufactures certainty.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from domain.models import Alignment, AlignmentKind, Insight, TimelineUnit

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"


def test_insight_confidence_is_nullable_in_domain():
    insight = Insight(
        version_id=uuid4(),
        kind="melody",
        claim="Range: C4–G5",
        confidence=None,
    )
    assert insight.confidence is None


def test_alignment_confidence_is_nullable_in_domain():
    source_id = uuid4()
    alignment = Alignment(
        version_id=source_id,
        target_version_id=uuid4(),
        kind=AlignmentKind.version,
        source_unit=TimelineUnit.seconds,
        target_unit=TimelineUnit.seconds,
    )
    assert alignment.confidence is None


def test_migrations_make_insights_confidence_nullable():
    migration = MIGRATIONS / "202608140002_insights_confidence_nullable.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "alter table public.insights" in sql
    assert "alter column confidence drop not null" in sql
    assert "alter column confidence drop default" in sql


def test_migrations_make_alignments_confidence_nullable():
    migration = MIGRATIONS / "202608310001_alignments_confidence_nullable.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "alter table public.alignments" in sql
    assert "alter column confidence drop not null" in sql
    assert "alter column confidence drop default" in sql


def test_confidence_nullability_migrations_follow_table_creation():
    files = sorted(MIGRATIONS.glob("*.sql"))
    create = next(
        p
        for p in files
        if "create table" in p.read_text(encoding="utf-8").lower()
        and "insights" in p.read_text(encoding="utf-8").lower()
        and "alignments" in p.read_text(encoding="utf-8").lower()
    )
    insight_drop = MIGRATIONS / "202608140002_insights_confidence_nullable.sql"
    alignment_drop = MIGRATIONS / "202608310001_alignments_confidence_nullable.sql"
    assert insight_drop.name > create.name
    assert alignment_drop.name > create.name
