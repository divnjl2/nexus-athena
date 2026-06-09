import json
import pathlib

import athena

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_cli_validate_ok(capsys):
    rc = athena.main(["--speckit", "off", "validate", str(FIX / "valid.md")])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip())["passed"] is True


def test_cli_validate_fail_on_bad_dep(capsys):
    # bad_dep.md compiles-fail (missing phase) — ast_wellformed flags the dangling dep
    rc = athena.main(["--speckit", "off", "validate", str(FIX / "bad_dep.md")])
    assert rc == 1


def test_cli_hermes_plan_writes_master_plan(tmp_path, capsys):
    out = tmp_path / "plan.md"
    rc = athena.main(["--speckit", "off", "hermes-plan", str(FIX / "valid.md"), "-o", str(out)])
    assert rc == 0
    md = out.read_text(encoding="utf-8")
    assert "plan_id:" in md
    assert "## Tasks" in md
    assert "workflow: ATHENA_TASK" in md


def test_cli_seam_compile_pure_ok():
    assert athena.main(["--speckit", "off", "seam", "compile_pure", str(FIX / "valid.md")]) == 0


def test_cli_stats(capsys):
    # done via shakedown loop: claurst@35B self-reported OK but added nothing; gate caught it; repaired here
    rc = athena.main(["--speckit", "off", "stats", str(FIX / "valid.md")])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip()) == {"epics": 2, "issues": 2, "tasks": 2}


def test_cli_speckit_path(tmp_path):
    out = tmp_path / "plan.md"
    rc = athena.main(["--speckit", "on", "hermes-plan", str(FIX / "speckit_tasks.md"), "-o", str(out)])
    assert rc == 0
    assert "task_id: T001" in out.read_text(encoding="utf-8")


def test_cli_hermes_plan_compile_error_is_structured(tmp_path, capsys):
    # empty-slug front: passes ast_wellformed but compile raises -> structured error, exit 1
    out = tmp_path / "plan.md"
    rc = athena.main(["--speckit", "off", "hermes-plan", str(FIX / "empty_slug.md"), "-o", str(out)])
    assert rc == 1
    assert "error" in json.loads(capsys.readouterr().out.strip())
    assert not out.exists()


def test_cli_seam_speckit_schema_pass_and_fail():
    assert athena.main(["seam", "speckit_schema", str(FIX / "speckit_tasks.md")]) == 0
    # a canonical plan.md is NOT a Spec-Kit tasks.md -> schema gate fails closed
    assert athena.main(["seam", "speckit_schema", str(FIX / "valid.md")]) == 1


def test_cli_parse_error_is_structured_not_traceback(capsys):
    # plan.md fed to the speckit parser -> ParseError -> structured fail (exit 1), no traceback
    rc = athena.main(["--speckit", "on", "seam", "ast_wellformed", str(FIX / "valid.md")])
    assert rc == 1
    assert "error" in json.loads(capsys.readouterr().out.strip())


def test_cli_validate_missing_file_structured(capsys):
    rc = athena.main(["--speckit", "off", "validate", str(FIX / "nope.md")])
    assert rc == 1
    assert "error" in json.loads(capsys.readouterr().out.strip())


def test_cli_hermes_plan_reads_env_fallback(tmp_path, monkeypatch):
    out = tmp_path / "plan.md"
    monkeypatch.setenv("CEX_HERMES_INPUT_FRONT", str(FIX / "valid.md"))
    monkeypatch.setenv("CEX_HERMES_INPUT_OUT", str(out))
    monkeypatch.setenv("CEX_HERMES_INPUT_SPECKIT", "off")
    rc = athena.main(["hermes-plan"])           # no positional args — must read env
    assert rc == 0
    assert "## Tasks" in out.read_text(encoding="utf-8")
