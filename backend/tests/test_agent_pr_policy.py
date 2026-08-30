from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "agent_pr.py"
SPEC = importlib.util.spec_from_file_location("agent_pr", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
agent_pr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = agent_pr
SPEC.loader.exec_module(agent_pr)


def test_docs_only_is_low_risk_and_lightweight() -> None:
    policy = agent_pr.classify(["docs/ARCHITECTURE.md", "README.md"])

    assert policy.kind == "docs-research"
    assert policy.risk == "low"
    assert policy.fix_mode == "none"
    assert policy.check_mode == "light"
    assert policy.required_evidence == ("diff-check",)


def test_frontend_only_selects_frontend_fix_and_gate() -> None:
    policy = agent_pr.classify(["components/workspace/Inspector.tsx"])

    assert policy.kind == "production"
    assert policy.risk == "standard"
    assert policy.fix_mode == "frontend"
    assert policy.check_mode == "frontend"
    assert "frontend-static" in policy.required_evidence
    assert "frontend-unit" in policy.required_evidence


def test_backend_only_selects_locked_backend_gate() -> None:
    policy = agent_pr.classify(["backend/domain/jobs.py", "backend/tests/test_jobs.py"])

    assert policy.kind == "production"
    assert policy.fix_mode == "python"
    assert policy.check_mode == "backend"
    assert "backend-static" in policy.required_evidence
    assert "backend-unit" in policy.required_evidence
    assert "api-contract" in policy.required_evidence


def test_mixed_frontend_backend_uses_fast_cross_stack_gate() -> None:
    policy = agent_pr.classify(["app/page.tsx", "backend/api.py"])

    assert policy.fix_mode == "all"
    assert policy.check_mode == "fast"
    assert set(policy.flags) >= {"frontend", "backend"}


def test_migration_is_high_risk_and_requires_database_integration() -> None:
    policy = agent_pr.classify(["supabase/migrations/202608300001_example.sql"])

    assert policy.kind == "production"
    assert policy.risk == "high"
    assert "database" in policy.flags
    assert "migrations" in policy.flags
    assert "database-integration" in policy.required_evidence


def test_workflow_is_high_risk_control_plane() -> None:
    policy = agent_pr.classify([".github/workflows/build.yml"])

    assert policy.kind == "control-plane"
    assert policy.risk == "high"
    assert policy.check_mode == "light"
    assert "workflows" in policy.flags
    assert "control-plane-review" in policy.required_evidence


def test_capability_registry_change_is_high_risk_truthfulness_work() -> None:
    policy = agent_pr.classify(["backend/config/capabilities.json"])

    assert policy.risk == "high"
    assert "capability-policy" in policy.flags
    assert "capability-registry/truthfulness" in policy.required_evidence


def test_dependency_lock_change_is_high_risk() -> None:
    policy = agent_pr.classify(["package-lock.json"])

    assert policy.risk == "high"
    assert "dependencies" in policy.flags
    assert policy.fix_mode == "frontend"


def test_real_stack_test_change_requests_real_stack_evidence() -> None:
    policy = agent_pr.classify(["tests/real-stack/workflow.spec.ts"])

    assert "fresh-real-stack-e2e" in policy.required_evidence


def test_empty_diff_is_explicit() -> None:
    policy = agent_pr.classify([])

    assert policy.kind == "empty"
    assert policy.check_mode == "none"
    assert policy.files == ()
