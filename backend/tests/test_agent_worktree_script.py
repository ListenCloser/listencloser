from __future__ import annotations

import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "agent-worktree.sh"


def _run(*args: str, cwd: Path, env: dict[str, str] | None = None, check: bool = True):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [*args],
        cwd=cwd,
        env=merged_env,
        text=True,
        capture_output=True,
        check=check,
    )


def _git(cwd: Path, *args: str):
    return _run("git", *args, cwd=cwd)


def test_agent_worktree_script_is_valid_bash():
    _run("bash", "-n", str(SCRIPT), cwd=REPO_ROOT)


def test_agent_worktree_lifecycle_fails_closed(tmp_path: Path):
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    lanes = tmp_path / "lanes"

    _run("git", "init", "--bare", "--initial-branch=main", str(origin), cwd=tmp_path)
    _run("git", "init", "--initial-branch=main", str(repo), cwd=tmp_path)
    _git(repo, "config", "user.name", "Agent Worktree Test")
    _git(repo, "config", "user.email", "agent-worktree@example.invalid")
    (repo / "README.md").write_text("fixture\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "fixture")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-u", "origin", "main")

    create_env = {"HELLO_AI_WORKTREE_ROOT": str(lanes)}
    created = _run(
        "bash",
        str(SCRIPT),
        "create",
        "demo",
        "lane",
        cwd=repo,
        env=create_env,
    )
    assert "Created isolated lane" in created.stdout

    lane_path = lanes / "lane"
    assert lane_path.is_dir()
    assert _git(lane_path, "branch", "--show-current").stdout.strip() == "agent/lane"

    # Make the lane visible on the remote, then prove cleanup does not confuse a
    # clean local branch with a reviewed+merged PR. The local bare remote is not
    # GitHub, so normal cleanup must fail closed; explicit abandon is required.
    _git(lane_path, "push", "-u", "origin", "agent/lane")
    refused = _run(
        "bash",
        str(SCRIPT),
        "cleanup",
        "lane",
        cwd=repo,
        check=False,
    )
    assert refused.returncode != 0
    assert "not proven as the reviewed head of a merged PR" in refused.stderr
    assert lane_path.is_dir()

    # Cleanup must resolve the path from recorded lane metadata even though the
    # custom HELLO_AI_WORKTREE_ROOT used at creation is no longer present.
    abandoned = _run(
        "bash",
        str(SCRIPT),
        "cleanup",
        "lane",
        "--abandon",
        cwd=repo,
    )
    assert "Removed lane lane" in abandoned.stdout
    assert not lane_path.exists()
    assert _git(repo, "branch", "--list", "agent/lane").stdout.strip() == ""

    # The remote branch intentionally survives cleanup. A second create must
    # detect it with ls-remote and refuse to establish competing ownership.
    duplicate = _run(
        "bash",
        str(SCRIPT),
        "create",
        "demo",
        "lane",
        cwd=repo,
        env=create_env,
        check=False,
    )
    assert duplicate.returncode != 0
    assert "remote branch already exists: agent/lane" in duplicate.stderr
    assert not lane_path.exists()
