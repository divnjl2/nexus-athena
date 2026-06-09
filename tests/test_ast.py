import dataclasses

import pytest

from lib.ast import Task, Phase, Plan, ParseError


def test_task_defaults():
    t = Task(id="T1.1", title="x", success_check="true")
    assert t.files == ()
    assert t.parallel is False
    assert t.autonomy == "default"


def test_phase_defaults():
    p = Phase(key="setup", title="Setup", goal="g")
    assert p.depends_on == ()
    assert p.checkpoint == ""
    assert p.tasks == ()


def test_frozen_is_immutable():
    t = Task(id="T1", title="x", success_check="true")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.title = "y"  # type: ignore[misc]


def test_plan_holds_phases():
    plan = Plan(
        title="P", overview="o", out_of_scope=(),
        phases=(Phase(key="phase1", title="A", goal="g", tasks=(Task("T1.1", "t", "true"),)),),
    )
    assert plan.phases[0].key == "phase1"
    assert plan.phases[0].tasks[0].id == "T1.1"


def test_parse_error_is_valueerror():
    assert issubclass(ParseError, ValueError)
