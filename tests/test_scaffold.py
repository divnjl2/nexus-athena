"""v3.5 adoption — a frame nobody can start is a frame nobody uses.

Each test is the executable spec of one C-11.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

from lib.contract import critique, lint, parse
from lib.contract_report import coverage
from lib.plan_parser import parse as parse_plan
from lib.scaffold import next_steps, render_files
from lib.scenario_parser import parse as parse_scenarios


def test_a_scaffolded_feature_is_already_wired_clause_to_spec_to_task():
    """C-11.8 — the three files reference each other on creation; a scaffold whose parts do
    not connect teaches the user the tool is broken, not that their contract is empty."""
    files = render_files(title="Payment Retry", run_cmd="pytest tests/test_retry.py::test_x -q")
    assert set(files) == {"contract.md", "scenarios.md", "plan.md"}

    contract = parse(files["contract.md"])
    scenarios = parse_scenarios(files["scenarios.md"])
    plan = parse_plan(files["plan.md"])

    assert [c.id for c in contract.clauses] == ["C-1.1"]
    assert scenarios[0].requirement_key == "C-1.1", "the spec names the clause"
    assert plan.phases[0].tasks[0].verifies == ("S1.1",), "the task names the spec"
    assert scenarios[0].run_cmd == "pytest tests/test_retry.py::test_x -q"
    assert plan.phases[0].tasks[0].success_check == scenarios[0].run_cmd


def test_a_fresh_scaffold_passes_the_gates_it_will_be_judged_by():
    """C-11.9 — the first `check` on a new project must be green, or the frame reads as
    broken before the user has written a single requirement."""
    files = render_files(title="Payment Retry")
    contract = parse(files["contract.md"])
    scenarios = parse_scenarios(files["scenarios.md"])

    assert lint(contract) == ()
    assert critique(contract) == (), "the template must obey the wording rules it ships"
    rep = coverage(contract, scenarios)
    assert rep["passed"] and rep["uncovered"] == [] and rep["coverage_rate"] == 1.0
    # no placeholder markers: C-10.12 refuses TBD/TODO inside a live clause
    assert "TODO" not in files["contract.md"] and "TBD" not in files["contract.md"]


def test_the_scaffold_tells_the_user_what_to_do_next():
    """C-11.10 — the step after `init` is the one people get wrong; it is printed, not
    left in a skill file."""
    text = next_steps("features/payments", 3)
    assert "features/payments/contract.md" in text
    assert "contract pin" in text and "athena check" in text
    assert "contract import spec.md" in text, "migration is an option, not a rewrite"
    assert "created 3 files" in text
