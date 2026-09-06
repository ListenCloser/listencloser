from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIGRATED_BACKEND_FILES = (
    "backend/observability.py",
    "backend/worker.py",
    "backend/domain/repositories/client.py",
    "backend/engines/registry.py",
)
_SERVER_ONLY_ENV_NAMES = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "LLM_API_KEY",
    "SENTRY_DSN_BACKEND",
    "OTEL_EXPORTER_OTLP_HEADERS",
)
_FRONTEND_ROOTS = ("apps/web/src/app", "apps/web/src/components", "apps/web/src/lib")
_FRONTEND_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}


def test_migrated_backend_slices_do_not_parse_process_environment_directly():
    offenders: list[str] = []
    for relative_path in _MIGRATED_BACKEND_FILES:
        text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
        if "os.environ" in text or "os.getenv" in text or "getenv(" in text:
            offenders.append(relative_path)

    assert offenders == []


def test_frontend_sources_do_not_reference_server_only_environment_names():
    offenders: list[str] = []
    for root_name in _FRONTEND_ROOTS:
        root = _REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _FRONTEND_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            leaked_names = [name for name in _SERVER_ONLY_ENV_NAMES if name in text]
            if leaked_names:
                offenders.append(f"{path.relative_to(_REPO_ROOT)}: {', '.join(leaked_names)}")

    assert offenders == []


def test_env_examples_use_the_canonical_backend_sentry_name():
    for relative_path in (".env.example", "backend/.env.example"):
        lines = (_REPO_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        assert "SENTRY_DSN_BACKEND=https://..." in lines
        assert not any(line.startswith("SENTRY_DSN=") for line in lines)
