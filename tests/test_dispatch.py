"""v3.12 dispatch — a packet derived from the artifacts, a verdict from the diff and the
spec commands, a record per attempt.

Each test is the executable spec of one C-1.*, C-2.* or C-4.* clause in
features/executor-layer/contract.md.
"""
from __future__ import annotations

import json
import pathlib

import pytest

import athena
from lib.contract import parse as parse_contract
from lib.dispatch import (DispatchError, dispatch_metrics, packet, parse_dispatches, record,
                          verdict)
from lib.plan_parser import parse as parse_plan
from lib.scenario_parser import parse as parse_scenarios

CONTRACT = parse_contract("""# Contract: Demo

## C-1 — Things

- **C-1.1** — WHEN a starts THE SYSTEM SHALL do b.
- **C-1.2** — WHEN c happens THE SYSTEM SHALL do d.
""")
SCENARIOS = parse_scenarios("""# Scenarios: Demo

### S1.1 — b
- **verifies:** C-1.1
- **run_cmd:** `python -m pytest tests/test_demo.py::test_b -q`
- **Given** a
- **When** starts
- **Then** b

### S1.2 — d
- **verifies:** C-1.2
- **case:** `features/demo/cases/S1.2.json`
- **Given** c
- **When** happens
- **Then** d
""")
PLAN = parse_plan("""# Plan: Demo

## Overview
Demo.

## Out of Scope
- nothing

## Phase 1: Things
**Goal:** things
**Depends on:** none
### Tasks
- [ ] T1.1 Do b and d
  - success_check: `python -m pytest tests/test_demo.py -q`
  - files: `lib/demo.py, tests/test_demo.py`
  - verifies: S1.1, S1.2
- [ ] T1.2 Names a spec nobody wrote
  - success_check: `python -m pytest tests/test_demo.py -q`
  - files: `lib/demo.py`
  - verifies: S1.9
""")


def test_a_packet_is_derived_from_contract_scenarios_and_plan():
    """C-1.1 — what the executor receives is read out of the artifacts, never composed by
    hand: the clauses its specs verify, the spec commands, the task's files."""
    p = packet(CONTRACT, SCENARIOS, PLAN, "T1.1")
    assert [c["id"] for c in p["clauses"]] == ["C-1.1", "C-1.2"]
    assert [s["id"] for s in p["specs"]] == ["S1.1", "S1.2"]
    assert p["task"]["files"] == ["lib/demo.py", "tests/test_demo.py"]
    assert "python -m pytest tests/test_demo.py::test_b -q" in p["checks"]
    assert "python -m pytest tests/test_demo.py -q" in p["checks"], "the task's own check too"
    assert p["specs"][1]["case"] == "features/demo/cases/S1.2.json"


def test_a_rendered_packet_states_the_done_criterion_and_disowns_the_report():
    """C-1.2 — the criterion is the commands; the executor is told its report does not count."""
    text = packet(CONTRACT, SCENARIOS, PLAN, "T1.1", files={"lib/demo.py": "x = 1\n"})["text"]
    assert "WHEN a starts THE SYSTEM SHALL do b." in text
    for cmd in ("python -m pytest tests/test_demo.py::test_b -q", "python -m pytest tests/test_demo.py -q"):
        assert cmd in text
    assert "your own report of success does not count" in text
    assert "=== lib/demo.py ===" in text and "x = 1" in text


def test_a_task_naming_an_unknown_spec_gets_no_packet():
    """C-1.3 — fail closed: a task bound to a spec nobody wrote cannot be dispatched."""
    with pytest.raises(DispatchError) as e:
        packet(CONTRACT, SCENARIOS, PLAN, "T1.2")
    assert "S1.9" in str(e.value)
    with pytest.raises(DispatchError):
        packet(CONTRACT, SCENARIOS, PLAN, "T9.9")


def test_an_oversized_packet_is_reported_not_trimmed():
    """C-1.4 — over budget is a fact in the packet, never a silent cut of the clauses."""
    big = packet(CONTRACT, SCENARIOS, PLAN, "T1.1", files={"lib/demo.py": "y = 2\n" * 200},
                 budget_chars=500)
    assert big["over_budget"] and big["chars"] > 500
    assert [c["id"] for c in big["clauses"]] == ["C-1.1", "C-1.2"], "clauses intact"
    assert "y = 2" in big["text"]
    assert not packet(CONTRACT, SCENARIOS, PLAN, "T1.1")["over_budget"]


GREEN = [{"cmd": "python -m pytest tests/test_demo.py -q", "exit": 0, "tail": ""}]


def test_the_verdict_ignores_the_executors_report():
    """C-2.1 — the claim is recorded and ignored; the diff and the exit codes decide."""
    before = {"lib/demo.py": (1, 10)}
    same = verdict(before, {"lib/demo.py": (1, 10)}, GREEN, claim="DONE, all tests pass")
    assert not same["landed"] and not same["passed"] and same["claim"].startswith("DONE")
    moved = verdict(before, {"lib/demo.py": (2, 12)}, GREEN, claim="I could not do it")
    assert moved["landed"] and moved["green"] and moved["passed"]


def test_no_change_means_not_landed():
    """C-2.2 — identical snapshots: nothing landed, whatever ran."""
    v = verdict({"a.py": (1, 1)}, {"a.py": (1, 1)}, GREEN)
    assert v["landed"] is False and v["passed"] is False and v["changed_files"] == []
    assert "no file changed" in v["reason"]


def test_a_red_spec_command_makes_the_attempt_red_with_its_tail():
    """C-2.3 — a red check is the verdict, and its tail is the reason."""
    red = [{"cmd": "python -m pytest tests/test_demo.py::test_b -q", "exit": 1,
            "tail": "AssertionError: b was not done"}]
    v = verdict({"a.py": (1, 1)}, {"a.py": (2, 2)}, red)
    assert v["landed"] and not v["green"] and not v["passed"]
    assert "b was not done" in v["reason"] and v["red"][0]["exit"] == 1
    silent = verdict({"a.py": (1, 1)}, {"a.py": (2, 2)}, [])
    assert not silent["green"] and "silence" in silent["reason"]


def test_touching_a_derived_or_hand_written_file_flags_review():
    """C-2.4 — an executor that edited the ledger or the contract did not do the task; it
    changed the question."""
    before = {"features/x/spec_ledger.json": (1, 1), "features/x/contract.md": (1, 1), "lib/a.py": (1, 1)}
    after = {"features/x/spec_ledger.json": (2, 2), "features/x/contract.md": (3, 3), "lib/a.py": (2, 2)}
    v = verdict(before, after, GREEN)
    assert set(v["review_flags"]) == {"features/x/spec_ledger.json", "features/x/contract.md"}
    assert "hand-written" in v["reason"]
    assert verdict(before, {**before, "lib/a.py": (2, 2)}, GREEN)["review_flags"] == []


def test_a_dispatch_appends_one_record():
    """C-4.1 — executor, task, landed, green, duration, tokens: one line per attempt."""
    v = verdict({"a.py": (1, 1)}, {"a.py": (2, 2)}, GREEN, claim="DONE")
    rec = record("T1.1", "local-27b", v, duration_ms=4200,
                 tokens={"input_tokens": 27000, "output_tokens": 500, "junk": "x"}, ts="2026-09-23T20:00:00+00:00")
    assert rec["executor"] == "local-27b" and rec["task"] == "T1.1"
    assert rec["landed"] and rec["green"] and rec["passed"] and rec["duration_ms"] == 4200
    assert rec["tokens"] == {"input_tokens": 27000, "output_tokens": 500}
    line = json.dumps(rec)
    records, skipped = parse_dispatches(line + "\nnot json\n" + line + "\n")
    assert len(records) == 2 and skipped == 1


def test_dispatch_metrics_report_landed_and_green_rates_per_executor():
    """C-4.2 — the numbers that decide whether local models suffice."""
    def r(executor, landed, green, ms=1000):
        return {"executor": executor, "landed": landed, "green": green, "duration_ms": ms}
    rep = dispatch_metrics([r("local-27b", False, False), r("local-27b", True, False),
                            r("local-27b", True, True, 4000), r("claude", True, True)])
    lane = rep["by_executor"]["local-27b"]
    assert lane["attempts"] == 3 and lane["landed_rate"] == 0.67 and lane["green_rate"] == 0.33
    assert lane["mean_duration_ms"] == 2000
    assert rep["by_executor"]["claude"]["green_rate"] == 1.0 and rep["attempts"] == 4


def test_a_packet_without_an_executor_is_printed_and_not_recorded(tmp_path, capsys):
    """C-4.3 — `--executor none` is how a packet reaches a hand-driven lane; it is not an
    attempt and leaves no record."""
    feature = tmp_path / "demo"
    assert athena.main(["init", str(feature), "--title", "Demo"]) == 0
    capsys.readouterr()
    rc = athena.main(["dispatch", str(feature / "contract.md"), "--front", str(feature / "plan.md"),
                      "--task", "T1.1", "--executor", "none", "--workspace", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "# Task T1.1" in out and "your own report of success does not count" in out
    assert not (feature / ".athena" / "dispatch.jsonl").exists()
