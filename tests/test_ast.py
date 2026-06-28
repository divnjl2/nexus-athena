import dataclasses

import pytest

from lib.ast import Task, Phase, Plan, ParseError, Provenance, Scenario, _EMPTY_PROVENANCE


def test_task_defaults():
    t = Task(id="T1.1", title="x", success_check="true")
    assert t.files == ()
    assert t.parallel is False
    assert t.autonomy == "default"
    assert t.verifies == ()  # v3.1 default


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


# --- v3: Provenance ---

def test_provenance_defaults():
    p = Provenance(spec_version="abc123")
    assert p.design_version == ""
    assert p.scenario_version == ""
    assert p.run_id == ""


def test_provenance_frozen():
    p = Provenance(spec_version="abc", design_version="def", run_id="r1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.spec_version = "xyz"  # type: ignore[misc]


def test_plan_default_provenance_is_empty_sentinel():
    plan = Plan(title="P", overview="o", out_of_scope=(), phases=())
    assert plan.provenance is _EMPTY_PROVENANCE
    assert plan.provenance.spec_version == ""


def test_plan_with_provenance():
    prov = Provenance(spec_version="abc", design_version="def", run_id="r1")
    plan = Plan(
        title="P", overview="o", out_of_scope=(),
        phases=(Phase(key="p1", title="A", goal="g", tasks=(Task("T1.1", "t", "true"),)),),
        provenance=prov,
    )
    assert plan.provenance.spec_version == "abc"
    assert plan.provenance.design_version == "def"


def test_plan_default_scenarios_empty():
    plan = Plan(title="P", overview="o", out_of_scope=(), phases=())
    assert plan.scenarios == ()


# --- v3.1: Scenario ---

def test_scenario_fields():
    s = Scenario(
        id="S1.1",
        requirement_key="R1",
        gwt_text="Given X\nWhen Y\nThen Z",
        run_cmd="pytest tests/test_x.py -q",
    )
    assert s.id == "S1.1"
    assert s.requirement_key == "R1"
    assert "When" in s.gwt_text
    assert s.run_cmd.startswith("pytest")


def test_scenario_frozen():
    s = Scenario(id="S1.1", requirement_key="R1", gwt_text="g", run_cmd="true")
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.id = "S1.2"  # type: ignore[misc]


def test_task_verifies_tuple():
    t = Task(id="T1.1", title="x", success_check="pytest -q", verifies=("S1.1", "S1.2"))
    assert t.verifies == ("S1.1", "S1.2")


def test_plan_with_scenarios():
    sc = Scenario(id="S1.1", requirement_key="R1", gwt_text="g", run_cmd="true")
    prov = Provenance(spec_version="abc", scenario_version="sc1")
    plan = Plan(
        title="P", overview="o", out_of_scope=(),
        phases=(Phase(key="p1", title="A", goal="g", tasks=(
            Task("T1.1", "t", "true", verifies=("S1.1",)),
        )),),
        provenance=prov,
        scenarios=(sc,),
    )
    assert len(plan.scenarios) == 1
    assert plan.scenarios[0].id == "S1.1"
    assert plan.phases[0].tasks[0].verifies == ("S1.1",)
