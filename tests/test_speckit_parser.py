import pathlib

import pytest

from lib.ast import Plan, Phase, Task
from lib.speckit_parser import parse, SpecKitParseError

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_parse_structure_and_deps():
    plan = parse(_read("speckit_tasks.md"))
    assert plan.title == "Healthcheck Endpoint"
    assert [p.key for p in plan.phases] == ["setup", "foundational", "US1", "polish"]
    setup, foundational, us1, polish = plan.phases
    assert setup.depends_on == ()
    assert foundational.depends_on == ("setup",)
    assert us1.depends_on == ("setup", "foundational")          # blockers gate every US phase
    assert polish.depends_on == ("setup", "foundational", "US1")
    assert us1.checkpoint == "pytest tests/test_us1.py -q"


def test_parallel_and_markers_stripped():
    plan = parse(_read("speckit_tasks.md"))
    setup, us1 = plan.phases[0], plan.phases[2]
    assert setup.tasks[1].id == "T002" and setup.tasks[1].parallel is True
    assert us1.tasks[0].parallel is True
    assert us1.tasks[0].title == "Add route in src/routes.py"   # [P] [US1] stripped
    assert us1.tasks[1].parallel is False


def test_success_check_from_preset():
    plan = parse(_read("speckit_tasks.md"))
    assert plan.phases[2].tasks[0].success_check == "pytest tests/test_health.py -q"


def test_checkpoint_fallback_success_check():
    txt = ("# Tasks: F\n## Phase 1: User Story 1 - x\n"
           "- [ ] T001 [US1] do thing\n"
           "**Checkpoint:** `pytest -q`\n")
    plan = parse(txt)
    assert plan.phases[0].tasks[0].success_check == "pytest -q"


def test_missing_success_check_and_no_checkpoint_rejected():
    with pytest.raises(SpecKitParseError):
        parse("# Tasks: F\n## Phase 1: Setup\n- [ ] T001 do thing\n")


def test_duplicate_task_id_rejected():
    with pytest.raises(SpecKitParseError):
        parse("# Tasks: F\n## Phase 1: Setup\n- [ ] T001 a\n  - success_check: `true`\n"
              "- [ ] T001 b\n  - success_check: `true`\n")


def test_missing_title_rejected():
    with pytest.raises(SpecKitParseError):
        parse("## Phase 1: Setup\n- [ ] T001 a\n  - success_check: `true`\n")


def test_golden_ast():
    """Schema VERSION GUARD — parsed AST must equal this frozen expectation. If
    Spec-Kit's tasks.md format drifts, this fails LOUDLY (v2 §10 top risk)."""
    expected = Plan(
        title="Healthcheck Endpoint", overview="", out_of_scope=(),
        phases=(
            Phase(key="setup", title="Setup", goal="", depends_on=(), checkpoint="", tasks=(
                Task(id="T001", title="Create project structure", success_check="test -d src"),
                Task(id="T002", title="Configure linting", success_check="ruff --version", parallel=True),
            )),
            Phase(key="foundational", title="Foundational", goal="", depends_on=("setup",), checkpoint="", tasks=(
                Task(id="T003", title="Setup app skeleton in src/app.py", success_check='python -c "import src.app"'),
            )),
            Phase(key="US1", title="User Story 1 - Health endpoint (Priority: P1)",
                  goal="GET /health returns 200", depends_on=("setup", "foundational"),
                  checkpoint="pytest tests/test_us1.py -q", tasks=(
                Task(id="T004", title="Add route in src/routes.py",
                     success_check="pytest tests/test_health.py -q", parallel=True),
                Task(id="T005", title="Register blueprint in src/app.py",
                     success_check="curl -sf localhost:8000/health"),
            )),
            Phase(key="polish", title="Polish", goal="", depends_on=("setup", "foundational", "US1"),
                  checkpoint="", tasks=(
                Task(id="T006", title="Add docs", success_check="test -f README.md", parallel=True),
            )),
        ),
    )
    assert parse(_read("speckit_tasks.md")) == expected
