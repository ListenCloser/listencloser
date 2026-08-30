#!/usr/bin/env python3
"""Reject legacy product/repository identity on live repository surfaces.

Historical migrations, evaluation evidence, and design mockups are deliberately
outside this guard: preserving provenance there is not a production identity bug.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

LEGACY_IDENTIFIERS = (
    "hello" + "-" + "ai",
    "hello" + "_" + "ai",
    "hello" + " " + "ai",
    "gr" + "-" + "rr/hello" + "-" + "ai",
    "hello" + "-h7k6w5h4d-giancarloricci.vercel.app",
)

EXACT_LIVE_PATHS = {
    ".env.example",
    ".gitignore",
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
    "AGENTS.md",
    "CODEOWNERS",
    "DESIGN.md",
    "Dockerfile",
    "README.md",
    "docker-compose.yml",
    "openapi/openapi.json",
    "package-lock.json",
    "package.json",
    "supabase/config.toml",
    "docs/OPS.md",
}
LIVE_PREFIXES = (
    ".github/",
    "app/",
    "components/",
    "lib/",
    "backend/",
    "scripts/",
    "tests/",
)
HISTORICAL_PREFIXES = (
    "backend/evaluation/",
    "evaluation/",
    "supabase/migrations/",
    "design/mockups/",
)

COMPATIBILITY_PATTERNS = {
    ".gitignore": ("hello-ai-worktrees/",),
    ".github/workflows/deploy-backend.yml": ("~/hello-ai",),
    "backend/domain/api.py": (
        "hello-ai:understand:1.0:",
        "hello-ai:understand-workflow:1.0:",
        "hello-ai:variation:1.0:",
        "hello-ai:variation-workflow:1.0:",
    ),
    "backend/domain/repositories.py": ("hello-ai:retry:",),
    "backend/observability.py": (
        "hello_ai.http.server.requests",
        "hello_ai.http.server.duration",
        "hello_ai.worker.job.executions",
        "hello_ai.worker.job.duration",
        "hello_ai.worker.orphans_recovered",
    ),
    "backend/domain/performance_instrumentation.py": (
        "hello_ai.worker.queue_wait",
        "hello_ai.worker.understand.stage.duration",
        "hello_ai.worker.understand.operation.duration",
    ),
    "backend/tests/test_analysis_v3_audio_language.py": ("hello_ai_sha",),
    "backend/tests/test_analysis_v3_multitrack_transcription.py": ("hello_ai_sha",),
    "backend/tests/test_piano_transcription_profiles.py": ("hello_ai_sha",),
    "backend/tests/test_fixture_manifest.py": ("hello-ai-autonomous-handoff",),
    "backend/tests/test_job_controls.py": ("hello-ai:retry:",),
    "scripts/deploy.sh": ("$HOME/hello-ai",),
}


def is_live(path: str) -> bool:
    if path.startswith(HISTORICAL_PREFIXES):
        return False
    return path in EXACT_LIVE_PATHS or path.startswith(LIVE_PREFIXES)


def main() -> int:
    matches: list[str] = []
    output = subprocess.check_output(["git", "ls-files", "-z"])
    for raw in output.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode()
        if rel == "scripts/check_repo_identity.py":
            continue
        if not is_live(rel):
            continue
        path = Path(rel)
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            folded = line.casefold()
            allowed = COMPATIBILITY_PATTERNS.get(rel, ())
            for identifier in LEGACY_IDENTIFIERS:
                if identifier.casefold() not in folded:
                    continue
                if any(pattern.casefold() in folded for pattern in allowed):
                    continue
                matches.append(f"{rel}:{line_number}: {identifier}")

    if matches:
        print("Legacy identity remains on live repository surfaces:")
        for match in matches:
            print(f"  {match}")
        return 1

    print("Live repository identity is fully migrated to Listen Closer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
