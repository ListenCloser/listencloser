from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_env_is_restricted_before_credentials_are_written() -> None:
    deploy = (REPO_ROOT / "scripts" / "deploy.sh").read_text()
    write_runtime_env = deploy.split("write_runtime_env() {", 1)[1].split(
        "\n}\n\nset_runtime_env_value() {", 1
    )[0]

    truncate = ': > "$env_file"'
    restrict = 'chmod 600 "$env_file"'
    write_credentials = 'cat > "$env_file" <<ENVEOF'

    assert truncate in write_runtime_env
    assert restrict in write_runtime_env
    assert write_credentials in write_runtime_env
    assert write_runtime_env.index(truncate) < write_runtime_env.index(restrict)
    assert write_runtime_env.index(restrict) < write_runtime_env.index(write_credentials)
    assert "SUPABASE_SERVICE_ROLE_KEY=" in write_runtime_env
    assert "LLM_API_KEY=" in write_runtime_env
