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
