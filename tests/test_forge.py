"""v3.15 the forge — repair tasks made from the clause map by breaking owned lines.

Executable spec of C-7.5 in features/executor-layer/contract.md.
"""
from __future__ import annotations

from lib.ast import Scenario

MODULE = '''"""demo"""


def check(x):
    if x > 3 and x != 9:
        return True
    return False


def other(y):
    return not y
'''


def test_repair_tasks_are_forged_from_exclusively_owned_lines_and_verified_by_the_clauses_spec():
    """C-7.5 — targets are lines exactly one clause owns in non-test Python files; each forged
    task names the clause, its specs and its mutants; mutants apply in sequence; the plan
    names the mutated files and verifies the clause's specs; the table reads the record."""
    from lib.forge import (apply_mutants, exclusive_lines, forge_table, forged_plan, pick_targets,
                           render_forge, specs_by_clause)
    clause_map = {"clauses": {
        "C-1.1": {"lib/demo.py": [1, 5, 6], "tests/test_demo.py": [3]},
        "C-1.2": {"lib/demo.py": [5, 11], "lib/other.py": [2]},
    }}
    excl = exclusive_lines(clause_map)
    assert excl == {"C-1.1": {"lib/demo.py": [6]}, "C-1.2": {"lib/demo.py": [11], "lib/other.py": [2]}}, excl
    scen = (Scenario(id="S1.1", requirement_key="C-1.1", gwt_text="g", run_cmd="python -m pytest tests/test_demo.py::test_a -q"),
            Scenario(id="S1.2", requirement_key="C-1.2", gwt_text="g", run_cmd="python -m pytest tests/test_demo.py::test_b -q"),
            Scenario(id="S1.3", requirement_key="C-1.2", gwt_text="g", run_cmd="python cases/run.py S1.3"))
    assert specs_by_clause(scen) == {"C-1.1": [("S1.1", "python -m pytest tests/test_demo.py::test_a -q")],
                                     "C-1.2": [("S1.2", "python -m pytest tests/test_demo.py::test_b -q")]}
    sources = {"lib/demo.py": MODULE, "lib/other.py": "def f(a):\n    return a == 1\n"}
    tasks = pick_targets(clause_map, scen, sources, n=5, mutants_per_task=1, seed=1)
    assert [t["clause"] for t in tasks] and all(len(t["mutants"]) == 1 for t in tasks)
    same = pick_targets(clause_map, scen, sources, n=5, mutants_per_task=1, seed=1)
    assert [t["mutants"] for t in same] == [t["mutants"] for t in tasks], "deterministic under a seed"
    hard = pick_targets(clause_map, scen, sources, n=5, mutants_per_task=2, seed=1, clause_prefix="C-1.2")
    assert hard and hard[0]["clause"] == "C-1.2" and len(hard[0]["mutants"]) == 2
    assert len({m["path"] for m in hard[0]["mutants"]}) == 2, "the hard rung breaks two files"

    mutated = apply_mutants(sources, hard[0]["_mutants"])
    assert mutated["lib/demo.py"] != MODULE and mutated["lib/other.py"] != sources["lib/other.py"]
    two_same_file = pick_targets({"clauses": {"C-9.9": {"lib/demo.py": [5, 11]}}},
                                 (Scenario(id="S9.9", requirement_key="C-9.9", gwt_text="g",
                                           run_cmd="python -m pytest tests/t.py::t -q"),),
                                 sources, n=1, mutants_per_task=2, seed=3)
    doubly = apply_mutants(sources, two_same_file[0]["_mutants"])
    assert doubly["lib/demo.py"] != MODULE

    plan = forged_plan(hard[0], "Demo")
    assert "- [ ] T9.1 Repair C-1.2" in plan and "- verifies: S1.2" in plan
    assert "lib/demo.py" in plan and "lib/other.py" in plan and "success_check: `python -m pytest tests/test_demo.py::test_b -q`" in plan
    from lib.plan_parser import parse as parse_plan
    parsed = parse_plan(plan)
    assert parsed.phases[0].tasks[0].id == "T9.1" and set(parsed.phases[0].tasks[0].files) == {"lib/demo.py", "lib/other.py"}

    records = [{"task": "T9.1", "executor": "pi-9b#forge", "iteration": 1, "green": False, "duration_ms": 60000},
               {"task": "T9.1", "executor": "pi-9b#forge", "iteration": 2, "green": True, "duration_ms": 30000}]
    table = forge_table(records, hard, "pi-9b")
    assert table["T9.1"]["green_at"] == 2 and table["T9.1"]["attempts"] == 2 and table["T9.1"]["seconds"] == 90
    text = render_forge(table)
    assert "T9.1" in text and "green@2" in text and "C-1.2" in text
