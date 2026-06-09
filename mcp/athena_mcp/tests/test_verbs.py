import pathlib

import athena_mcp.verbs as verbs

# repo-root fixtures (mcp/athena_mcp/tests -> repo root is parents[3])
FIX = pathlib.Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def test_validate_valid():
    r = verbs.validate(str(FIX / "valid.md"))
    assert r["passed"] is True
    assert r["issues"] == []


def test_validate_bad_dep_reports_issue():
    r = verbs.validate(str(FIX / "bad_dep.md"))
    assert r["passed"] is False
    assert r["issues"]


def test_validate_missing_file():
    r = verbs.validate(str(FIX / "does_not_exist.md"))
    assert r["passed"] is False


def test_compile_dry_run():
    r = verbs.compile_plan(str(FIX / "valid.md"), apply=False)
    assert r["issue_count"] == 2
    assert r["applied"] is False
    assert len(r["commands"]) == 5
    assert r["epic_keys"] == ["athena:demo-feature:epic1", "athena:demo-feature:epic2"]


def test_compile_apply_with_fake_run():
    calls = []

    def fake_run(argv):
        calls.append(argv)
        return "[]" if argv[:2] == ["bd", "list"] else ""

    r = verbs.compile_plan(str(FIX / "valid.md"), apply=True, run=fake_run)
    assert r["applied"] is True
    assert any(a[:2] == ["bd", "list"] for a in calls)      # existing-keys fetch
    assert any(a[:2] == ["bd", "create"] for a in calls)    # execute ran the creates


def test_next_complete_report_with_fake_run():
    def fake_run(argv):
        if argv[:2] == ["bd", "ready"]:
            return '[{"id": "bd-a1b2", "title": "T1.1"}]'
        if argv[:2] == ["bd", "stats"]:
            return '{"closed": 0, "open": 2}'
        return ""

    assert verbs.next_issue(run=fake_run)["issue"]["id"] == "bd-a1b2"
    assert verbs.complete("bd-a1b2", True, run=fake_run) == {"ok": True}
    assert verbs.report(run=fake_run)["progress"]["open"] == 2


def test_stage_dispatch_descriptor():
    d = verbs.stage("question", intent="add healthcheck")
    assert d["command"] == "/qrspi/question"
    assert d["artifact"] == "questions.md"
    assert d["tier_gate"] == "dense"
