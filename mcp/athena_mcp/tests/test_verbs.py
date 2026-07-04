import json
import pathlib

import athena_mcp.verbs as verbs

# repo-root fixtures (mcp/athena_mcp/tests -> repo root is parents[3])
FIX = pathlib.Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def test_validate_valid_plan_fallback():
    r = verbs.validate(str(FIX / "valid.md"), speckit=False)
    assert r["passed"] is True
    assert r["issues"] == []


def test_validate_speckit_tasks_primary():
    r = verbs.validate(str(FIX / "speckit_tasks.md"), speckit=True)
    assert r["passed"] is True


def test_validate_bad_dep_reports_issue():
    r = verbs.validate(str(FIX / "bad_dep.md"), speckit=False)
    assert r["passed"] is False
    assert r["issues"]


def test_validate_missing_file():
    r = verbs.validate(str(FIX / "does_not_exist.md"), speckit=False)
    assert r["passed"] is False


def test_validate_error_keeps_speckit_key():
    r = verbs.validate(str(FIX / "bad_dep.md"), speckit=False)
    assert r["passed"] is False
    assert r["speckit"] is False   # key present on the error path too (no KeyError for callers)


def test_compile_dry_run_plan():
    r = verbs.compile_plan(str(FIX / "valid.md"), speckit=False)
    assert r["issue_count"] == 2
    assert r["applied"] is False
    assert r["epic_keys"] == ["athena:demo-feature:phase1", "athena:demo-feature:phase2"]


def test_compile_dry_run_speckit():
    r = verbs.compile_plan(str(FIX / "speckit_tasks.md"), speckit=True)
    assert r["issue_count"] == 6
    assert len(r["epic_keys"]) == 4


def test_compile_apply_with_fake_run():
    calls = []

    def fake_run(argv):
        calls.append(argv)
        return "[]" if argv[:2] == ["bd", "list"] else ""

    r = verbs.compile_plan(str(FIX / "valid.md"), apply=True, speckit=False, run=fake_run)
    assert r["applied"] is True
    assert any(a[:2] == ["bd", "list"] for a in calls)
    assert any(a[:2] == ["bd", "create"] for a in calls)


def test_export_ready_hands_off_not_executes():
    def fake_run(argv):
        assert argv[:2] == ["bd", "ready"]   # only reads the queue, never executes
        return '[{"id": "bd-a1", "title": "T1"}]'

    r = verbs.export_ready(run=fake_run)
    assert r["count"] == 1
    assert r["ready"][0]["id"] == "bd-a1"


def test_report_with_fake_run():
    def fake_run(argv):
        return '{"closed": 0, "open": 2}' if argv[:2] == ["bd", "stats"] else ""

    assert verbs.report(run=fake_run)["progress"]["open"] == 2


def test_spec_pipeline_descriptor():
    d = verbs.spec("add healthcheck")
    assert d["artifact"] == "tasks.md"
    assert "analyze" in d["pipeline"]


def test_stage_dispatch_descriptor():
    d = verbs.stage("question", intent="x")
    assert d["command"] == "/crisp.question"
    assert d["artifact"] == "questions.md"


def test_replan_routes_by_trigger():
    assert verbs.replan("research incomplete")["stage"] == "research"
    assert verbs.replan("vague")["stage"] == "design"


def test_validate_returns_ast_wellformed_seam():
    r = verbs.validate(str(FIX / "valid.md"), speckit=False)
    assert r["passed"] is True
    assert r["seam"]["name"] == "seam.ast_wellformed"
    assert r["seam"]["passed"] is True


def test_compile_apply_readback_seam_catches_empty_graph():
    # execute "ran" but the read-back sees nothing -> drift / partial bd failure caught
    def fake_run(argv):
        return "[]" if argv[:2] == ["bd", "list"] else ""

    r = verbs.compile_plan(str(FIX / "valid.md"), apply=True, speckit=False, run=fake_run)
    assert r["applied"] is True
    assert r["seam"]["name"] == "seam.graph_materialized"
    assert r["seam"]["passed"] is False


def test_compile_apply_readback_seam_passes_on_full_graph():
    full = [{"labels": [f"athena:demo-feature:{k}"]} for k in ("phase1", "T1.1", "phase2", "T2.1")]

    def fake_run(argv):
        return json.dumps(full) if argv[:2] == ["bd", "list"] else ""

    r = verbs.compile_plan(str(FIX / "valid.md"), apply=True, speckit=False, run=fake_run)
    assert r["seam"]["passed"] is True


# --- v3.2 coverage-backedge verbs ---------------------------------------------

def test_replan_spec_gap_forks_deadcode_vs_lost_requirement():
    r = verbs.replan("spec_gap")
    assert "fork" in r
    assert "dead_code" in r["fork"] and "lost_requirement" in r["fork"]


def test_replan_satisfies_unproven_reopens():
    r = verbs.replan("satisfies_unproven")
    assert "reopen" in r


def test_planner_trace_coverage_proves_edge_and_reports_gap(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan: t\n## Overview\nx\n"
        "## Phase 1: p\n**Goal:** g\n**Depends on:** none\n### Tasks\n"
        "- [ ] T1.1 do\n  - success_check: `pytest x`\n  - files: `pkg/a.py`\n  - verifies: S1\n",
        encoding="utf-8")
    cov = tmp_path / "cov.xml"
    cov.write_text(
        '<coverage><packages><package><classes>'
        '<class filename="pkg/a.py" line-rate="0.5"><lines>'
        '<line number="1" hits="1"/>'
        '<line number="2" hits="1" branch="true" condition-coverage="50% (1/2)"/>'
        '</lines></class></classes></package></packages></coverage>',
        encoding="utf-8")
    r = verbs.planner_trace_coverage(str(plan), str(cov), speckit=False)
    assert r["proven"] == 1 and r["unproven"] == 0
    assert "pkg/a.py:2" in r["spec_gaps"]
    assert r["replan_trigger"] == "spec_gap"


def test_planner_trace_coverage_missing_coverage_file(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan: t\n## Overview\nx\n## Phase 1: p\n**Goal:** g\n**Depends on:** none\n"
        "### Tasks\n- [ ] T1 do\n  - success_check: `pytest x`\n", encoding="utf-8")
    r = verbs.planner_trace_coverage(str(plan), str(tmp_path / "nope.xml"), speckit=False)
    assert r["ok"] is False
