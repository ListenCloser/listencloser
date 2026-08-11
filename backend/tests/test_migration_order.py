from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"


def test_latest_jobs_definition_follows_every_jobs_drop():
    files = sorted(MIGRATIONS.glob("*.sql"))
    drops = [path for path in files if "drop table if exists public.jobs" in path.read_text()]
    creates = [
        path for path in files if "create table if not exists public.jobs" in path.read_text()
    ]
    assert drops
    assert creates
    assert creates[-1].name > drops[-1].name
    repair = creates[-1].read_text()
    for required in (
        "workflow_id",
        "capability_name",
        "capability_version",
        "lease_expires_at",
        "input_version_ids",
        "output_version_ids",
        'create policy "jobs owner select"',
    ):
        assert required in repair
