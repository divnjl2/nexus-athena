import pathlib

import pytest

from lib.plan_parser import parse, PlanParseError

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_parse_valid_structure():
    plan = parse(_read("valid.md"))
    assert plan.title == "Demo Feature"
    assert len(plan.phases) == 2
    p1, p2 = plan.phases
    assert p1.index == 1 and p1.title == "Endpoint"
    assert p1.goal == "expose GET /health"
    assert p1.depends_on == ()
    assert p1.tasks[0].id == "T1.1"
    assert p1.tasks[0].success_check == "pytest tests/test_health.py -q"
    assert p1.tasks[0].files == ("app/routes.py",)
    assert p2.depends_on == (1,)
    assert "auth on the endpoint" in plan.out_of_scope


def test_missing_success_check_rejected():
    with pytest.raises(PlanParseError):
        parse(_read("no_check.md"))


def test_duplicate_task_id_rejected():
    with pytest.raises(PlanParseError):
        parse(_read("dup_id.md"))


def test_missing_title_rejected():
    with pytest.raises(PlanParseError):
        parse("## Phase 1: x\n**Goal:** g\n**Depends on:** none\n"
              "- [ ] T1.1 t\n  - success_check: `true`\n")


def test_no_phases_rejected():
    with pytest.raises(PlanParseError):
        parse("# Plan: Empty\n## Overview\nnothing here\n")


def test_autonomy_parsed():
    plan = parse(
        "# Plan: A\n## Overview\no\n## Phase 1: P\n**Goal:** g\n**Depends on:** none\n"
        "- [ ] T1.1 t\n  - success_check: `true`\n  - autonomy: high\n"
    )
    assert plan.phases[0].tasks[0].autonomy == "high"


def test_bad_dep_parses_but_records_phase_ref():
    # bad_dep.md is structurally valid at PARSE time (the missing-phase check is
    # the compiler's job); the parser only records the referenced index.
    plan = parse(_read("bad_dep.md"))
    assert plan.phases[0].depends_on == (2,)
