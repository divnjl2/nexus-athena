"""v3.14 the ceiling — graded tasks that say how far a local model in a harness reaches.

Each test is the executable spec of one C-7.* clause in features/executor-layer/contract.md.
"""
from __future__ import annotations

import json


def test_a_bench_matrix_is_planned_and_read_back_from_the_record():
    """C-7.1 — the matrix is the ordered runs of tasks × executors, each in its own workspace;
    the record folds back into one table per (task, executor): green at which iteration,
    landed, seconds, tokens."""
    from lib.bench import matrix_table, plan_matrix, render_matrix
    runs = plan_matrix(["T2.1", "T2.3"], ["pi-9b", "pi-27b"], "D:/w/bench")
    assert [(r["task"], r["executor"], r["workspace"]) for r in runs] == [
        ("T2.1", "pi-9b", "D:/w/bench-pi-9b"), ("T2.3", "pi-9b", "D:/w/bench-pi-9b"),
        ("T2.1", "pi-27b", "D:/w/bench-pi-27b"), ("T2.3", "pi-27b", "D:/w/bench-pi-27b")]
    assert plan_matrix([], ["pi-9b"], "D:/w/b") == []

    records = [
        {"task": "T2.1", "executor": "pi-9b", "iteration": 1, "landed": True, "green": True,
         "duration_ms": 40000, "tokens": {"input_tokens": 12000, "output_tokens": 600}},
        {"task": "T2.3", "executor": "pi-9b", "iteration": 1, "landed": True, "green": False,
         "duration_ms": 50000, "tokens": {"input_tokens": 20000, "output_tokens": 900}},
        {"task": "T2.3", "executor": "pi-9b", "iteration": 2, "landed": True, "green": True,
         "duration_ms": 30000, "tokens": {"input_tokens": 15000, "output_tokens": 500}},
        {"task": "T2.1", "executor": "pi-27b", "iteration": 1, "landed": False, "green": False,
         "duration_ms": 61000, "tokens": {"input_tokens": 51000, "output_tokens": 1400}},
        {"task": "T9.9", "executor": "pi-27b", "iteration": 1, "landed": True, "green": True,
         "duration_ms": 1000, "tokens": {}},                       # not in the matrix: ignored
    ]
    table = matrix_table(records, ["T2.1", "T2.3"], ["pi-9b", "pi-27b"])
    assert table["T2.1"]["pi-9b"] == {"green_at": 1, "attempts": 1, "landed": 1, "seconds": 40,
                                      "input_tokens": 12000, "output_tokens": 600}
    assert table["T2.3"]["pi-9b"]["green_at"] == 2 and table["T2.3"]["pi-9b"]["seconds"] == 80
    assert table["T2.1"]["pi-27b"]["green_at"] is None and table["T2.1"]["pi-27b"]["landed"] == 0
    assert table["T2.3"]["pi-27b"]["attempts"] == 0
    text = render_matrix(table, ["T2.1", "T2.3"], ["pi-9b", "pi-27b"])
    lines = text.splitlines()
    assert "pi-9b" in lines[0] and "pi-27b" in lines[0]
    assert any(l.startswith("T2.1") and "green@1" in l and "-" in l for l in lines)
    assert any(l.startswith("T2.3") and "green@2" in l and "not run" in l for l in lines)


def test_the_bench_command_prints_its_plan_without_running_when_dry():
    """C-7.4 — `athena bench --dry-run` prints the planned runs as JSON and dispatches nothing;
    the flags it will hand to each dispatch are part of the plan."""
    import athena
    args = athena.build_parser().parse_args([
        "bench", "features/refinery-layer/contract.md", "--front", "features/refinery-layer/plan.md",
        "--tasks", "T2.1,T2.3", "--executors", "pi-9b,pi-27b", "--base-workspace", "D:/w/bench",
        "--iterations", "2", "--dry-run"])
    assert args.dry_run is True and args.iterations == 2
    plan = athena.bench_plan(args)
    assert [r["task"] for r in plan["runs"]] == ["T2.1", "T2.3", "T2.1", "T2.3"]
    assert plan["runs"][0]["workspace"].replace("\\", "/").endswith("bench-pi-9b")
    assert plan["dispatch_flags"]["iterations"] == 2 and plan["dispatch_flags"]["executor"] == "<per run>"
    assert plan["dry_run"] is True and plan["ran"] == 0
    assert json.loads(json.dumps(plan))["runs"][3]["executor"] == "pi-27b"
