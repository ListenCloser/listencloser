from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-real-stack.sh"
ISOLATION_LIST_COMMAND = "git ls-files -z --cached --others --exclude-standard -- supabase"


def test_real_stack_isolation_includes_untracked_nonignored_supabase_files(
    tmp_path: Path,
) -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert ISOLATION_LIST_COMMAND in script
    assert "git ls-files -z supabase" not in script

    repo = tmp_path / "repo"
    migrations = repo / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    (repo / "supabase" / "config.toml").write_text("project_id = 'test'\n")
    (migrations / "001_tracked.sql").write_text("select 1;\n")
    (migrations / "002_untracked.sql").write_text("select 2;\n")
    (migrations / "003_ignored.sql").write_text("select 3;\n")
    (repo / ".gitignore").write_text(
        "supabase/migrations/003_ignored.sql\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "add",
            ".gitignore",
            "supabase/config.toml",
            "supabase/migrations/001_tracked.sql",
        ],
        cwd=repo,
        check=True,
    )
    listed = (
        subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "supabase",
            ],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .split("\0")
    )

    assert set(filter(None, listed)) == {
        "supabase/config.toml",
        "supabase/migrations/001_tracked.sql",
        "supabase/migrations/002_untracked.sql",
    }
