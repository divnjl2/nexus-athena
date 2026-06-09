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


def test_cli_speckit_path(tmp_path):
    out = tmp_path / "plan.md"
    rc = athena.main(["--speckit", "on", "hermes-plan", str(FIX / "speckit_tasks.md"), "-o", str(out)])
    assert rc == 0
    assert "task_id: T001" in out.read_text(encoding="utf-8")
