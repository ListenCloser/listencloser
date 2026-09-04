from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "project_cockpit.py"
FIXTURES = Path(__file__).parent / "fixtures" / "project_cockpit" / "scenarios.json"

spec = importlib.util.spec_from_file_location("project_cockpit", SCRIPT)
assert spec and spec.loader
project_cockpit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project_cockpit)


@pytest.fixture(scope="module")
def scenarios() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def compile_scenario(scenarios: dict, name: str) -> dict:
    scenario = scenarios[name]
    return project_cockpit.compile_cockpit(
        scenario["live"],
        scenario["roadmap"],
        scenario["graph"],
        now=datetime(2026, 9, 4, 20, 0, tzinfo=UTC),
    )


def test_open_focused_issue_with_no_pr_is_eligible(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "open_focused_issue_no_pr")
    assert [item["issue"] for item in cockpit["eligible_next"]] == [10]
    assert cockpit["in_flight"] == []


def test_exactly_one_active_pr_claims_issue(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "exactly_one_active_pr")
    assert [(item["pr"], item["issue"]) for item in cockpit["in_flight"]] == [(101, 10)]
    assert cockpit["eligible_next"] == []


def test_duplicate_active_pr_ownership_warns(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "duplicate_active_pr_ownership")
    assert any(
        "duplicate active PR ownership for issue #10: #101, #102" in warning
        for warning in cockpit["warnings"]
    )


def test_draft_and_ready_are_distinct(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "draft_vs_ready")
    states = {item["pr"]: item["draft"] for item in cockpit["in_flight"]}
    assert states == {101: True, 102: False}


def test_green_red_pending_build_states(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "green_red_pending_build")
    states = {item["pr"]: item["build"] for item in cockpit["in_flight"]}
    assert states == {101: "green", 102: "red", 103: "pending"}
    reasons = {(item["number"], item["reason"]) for item in cockpit["blocked"]}
    assert (102, "Build red") in reasons
    assert (103, "Build pending") in reasons
    assert not any(
        number == 101 and reason.startswith("Build") for number, reason in reasons
    )


def test_protected_build_name_is_case_insensitive() -> None:
    assert project_cockpit.build_state(
        {
            "statusCheckRollup": [
                {"name": "build", "status": "COMPLETED", "conclusion": "SUCCESS"}
            ]
        }
    ) == "green"


def test_hard_dependency_blocks_delivery(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "hard_dependency_blocks_delivery")
    assert cockpit["eligible_next"] == []
    assert any(
        item["number"] == 20 and item["reason"] == "hard delivery dependency open: #10"
        for item in cockpit["blocked"]
    )


def test_recent_merge_moves_out_of_in_flight(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "recent_merge_transition")
    assert cockpit["in_flight"] == []
    assert [
        (item["pr"], item["issue"]) for item in cockpit["recently_landed"]
    ] == [(101, 10)]


def test_unknown_or_gated_posture_is_not_guessed(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "unknown_and_gated_posture")
    assert cockpit["eligible_next"] == []
    assert any(
        item["number"] == 30 and item["reason"] == "ROADMAP posture GATED"
        for item in cockpit["blocked"]
    )
    assert any(
        warning == "issue #31 eligibility: requires judgment"
        for warning in cockpit["warnings"]
    )
    assert "requires judgment" in project_cockpit.render_markdown(cockpit)


def test_api_failure_is_explicitly_incomplete(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "api_failure_is_incomplete")
    assert cockpit["complete"] is False
    assert cockpit["main_sha"] is None
    assert any(
        warning.startswith("incomplete status: GitHub/API query failed")
        for warning in cockpit["warnings"]
    )
    assert "**Status: incomplete**" in project_cockpit.render_markdown(cockpit)


def test_markdown_and_json_contract_are_serializable(scenarios: dict) -> None:
    cockpit = compile_scenario(scenarios, "exactly_one_active_pr")
    markdown = project_cockpit.render_markdown(cockpit)
    assert "## In flight" in markdown
    assert "## Blocked / waiting" in markdown
    assert "## Recently landed" in markdown
    assert "## Eligible next" in markdown
    assert "## Warnings" in markdown
    assert json.loads(json.dumps(cockpit))["main_sha"] == "a" * 40
