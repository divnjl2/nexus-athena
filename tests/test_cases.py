"""v3.11 specs as data — a case is given/when/then in JSON, run in the current process.

Each test is the executable spec of one C-1.* clause in features/team-layer/contract.md.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from lib.ast import Scenario
from lib.cases import CaseError, binding_issues, derived_run_cmd, parse_case, run_case
from lib.scenario_parser import parse as parse_scenarios
from lib.spec_runner import run_specs

CASE = {
    "clause": "C-1.1",
    "given": {"text": "# Contract: X\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n"},
    "when": {"call": "lib.contract:parse", "args": ["$text"]},
    "then": [{"path": "clauses[0].id", "equals": "C-1.1"},
             {"path": "clauses", "length": 1},
             {"path": "title", "startswith": "X"}],
}


def test_a_case_file_parses_given_when_then_and_refuses_a_missing_part():
    """C-1.1 — three parts or nothing; the refusal names the part that is missing."""
    case = parse_case(CASE)
    assert case["when"]["call"] == "lib.contract:parse" and len(case["then"]) == 3
    for part in ("given", "when", "then"):
        broken = {k: v for k, v in CASE.items() if k != part}
        with pytest.raises(CaseError) as e:
            parse_case(broken)
        assert part in str(e.value)
    with pytest.raises(CaseError):
        parse_case({**CASE, "then": []})


def test_a_case_runs_in_the_current_process_without_spawning(monkeypatch):
    """C-1.2 — the point of a case is the missing process boundary."""
    def boom(*a, **kw):
        raise AssertionError("a case must not spawn")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    res = run_case(parse_case(CASE))
    assert res.passed, res.message
    assert res.duration_ms >= 0


def test_a_failed_then_is_red_with_expected_and_actual():
    """C-1.3 — a red case must say what it wanted and what it got."""
    bad = {**CASE, "then": [{"path": "clauses[0].id", "equals": "C-9.9"}]}
    res = run_case(parse_case(bad))
    assert not res.passed
    assert "C-9.9" in res.message and "C-1.1" in res.message and "clauses[0].id" in res.message


def test_an_expected_exception_passes_only_when_raised():
    """C-1.4 — `raises` is a check like any other: it passes on the named exception and
    fails when the call returns."""
    raising = {**CASE, "given": {"text": "no clauses here"},
               "then": [{"raises": "ContractParseError"}]}
    assert run_case(parse_case(raising)).passed
    not_raising = {**CASE, "then": [{"raises": "ContractParseError"}]}
    res = run_case(parse_case(not_raising))
    assert not res.passed and "ContractParseError" in res.message
    wrong_type = {**raising, "then": [{"raises": "KeyError"}]}
    assert not run_case(parse_case(wrong_type)).passed


def test_a_case_scenario_derives_a_replayable_run_command():
    """C-1.5 — a case scenario needs no run_cmd of its own; the derived one replays the case
    through the CLI, so the map, the mutation sweep and the guard see a command like any other."""
    text = ("# Scenarios: X\n\n### S1.1 — a case spec\n- **verifies:** C-1.1\n"
            "- **case:** `features/x/cases/S1.1.json`\n- **Given** a\n- **When** b\n- **Then** c\n")
    (sc,) = parse_scenarios(text)
    assert sc.case == "features/x/cases/S1.1.json"
    assert sc.run_cmd == derived_run_cmd("features/x/cases/S1.1.json")
    assert sc.run_cmd.startswith("python -m athena case run ")
    assert "features/x/cases/S1.1.json" in sc.run_cmd


def test_case_and_command_scenarios_share_one_ledger(tmp_path):
    """C-1.6 — one run, one ledger: cases in-process, commands through the spawn seam, results
    in document order."""
    case_file = tmp_path / "S1.1.json"
    case_file.write_text(json.dumps(CASE), encoding="utf-8")
    spawned = []

    def spawn(argv, *, cwd, timeout):
        spawned.append(argv)
        return 0, ""

    scenarios = (
        Scenario(id="S1.1", requirement_key="C-1.1", gwt_text="g",
                 run_cmd=derived_run_cmd(str(case_file)), case=str(case_file)),
        Scenario(id="S1.2", requirement_key="C-1.2", gwt_text="g",
                 run_cmd="python -m pytest tests/test_x.py::t -q"),
    )
    res = run_specs(scenarios, spawn=spawn, jobs=2, cwd=str(tmp_path))
    assert [r.scenario_id for r in res] == ["S1.1", "S1.2"]
    assert res[0].passed and res[1].passed
    assert len(spawned) == 1 and "tests/test_x.py::t" in spawned[0], "only the command spawned"


def test_a_case_naming_another_clause_is_a_broken_binding():
    """C-1.7 — a case documents the clause it proves, the same rule the pytest guard applies."""
    scenarios = (
        Scenario(id="S1.1", requirement_key="C-1.1", gwt_text="g", run_cmd="x", case="a.json"),
        Scenario(id="S1.2", requirement_key="C-1.2", gwt_text="g", run_cmd="x", case="b.json"),
    )
    issues = binding_issues(scenarios, {"a.json": CASE, "b.json": {**CASE, "clause": "C-1.9"}})
    assert len(issues) == 1 and "S1.2" in issues[0] and "C-1.9" in issues[0]
    assert binding_issues(scenarios, {"a.json": CASE, "b.json": {**CASE, "clause": "C-1.2"}}) == ()
