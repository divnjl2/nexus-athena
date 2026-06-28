"""Tests for v3 provenance graph and v3.1 scenario edges in plan2beads."""
import pytest

from lib.ast import Plan, Phase, Task, Provenance, Scenario
from lib.plan2beads import compile, CompileError, EXTERNAL_KEY_PREFIX


def _cmds(res):
    return [str(c) for c in res.commands]


def _plan_with_provenance(*, spec_version="spec1", design_version="des1", run_id="r1"):
    prov = Provenance(spec_version=spec_version, design_version=design_version, run_id=run_id)
    return Plan(
        title="Prov Test",
        overview="o",
        out_of_scope=(),
        phases=(Phase(key="p1", title="Phase One", goal="g", tasks=(
            Task("T1.1", "do thing", "pytest -q"),
        )),),
        provenance=prov,
    )


# --- v3: spec + design node emission ---

def test_spec_node_emitted_when_provenance_set():
    res = compile(_plan_with_provenance())
    cmds = _cmds(res)
    assert any("kind:spec" in c for c in cmds)
    assert any("athena:spec:spec1" in c for c in cmds)


def test_design_node_emitted_with_parent_spec():
    res = compile(_plan_with_provenance())
    cmds = _cmds(res)
    assert any("kind:design" in c for c in cmds)
    assert any("athena:design:des1" in c for c in cmds)
    # design node create must reference spec key as parent
    design_create = next(c for c in cmds if "kind:design" in c)
    assert "athena:prov-test:spec:spec1" in design_create


def test_epic_has_parent_design_when_provenance():
    res = compile(_plan_with_provenance())
    cmds = _cmds(res)
    epic_create = next(c for c in cmds if "--type epic" in c)
    assert "athena:prov-test:design:des1" in epic_create


def test_no_provenance_nodes_when_spec_version_empty():
    plan = Plan(
        title="V2 Plan", overview="o", out_of_scope=(),
        phases=(Phase(key="p1", title="P", goal="g", tasks=(
            Task("T1.1", "x", "true"),
        )),),
        # no provenance = _EMPTY_PROVENANCE (spec_version="")
    )
    cmds = _cmds(compile(plan))
    assert not any("kind:spec" in c for c in cmds)
    assert not any("kind:design" in c for c in cmds)


def test_spec_node_idempotent_on_existing_key():
    plan = _plan_with_provenance(spec_version="abc")
    existing = frozenset({"athena:prov-test:spec:abc"})
    cmds = _cmds(compile(plan, existing_keys=existing))
    spec_creates = [c for c in cmds if "kind:spec" in c]
    assert spec_creates == [], "spec-node must not be recreated if key already exists"


def test_spec_node_survives_repeated_compile():
    plan = _plan_with_provenance(spec_version="stable")
    first = compile(plan)
    all_keys = frozenset(
        a for c in first.commands for i, a in enumerate(c.argv)
        if i > 0 and c.argv[i - 1] == "--label" and a.startswith(EXTERNAL_KEY_PREFIX)
    )
    second = compile(plan, existing_keys=all_keys)
    assert _cmds(second) == [], "full re-compile with all existing keys must be no-op"


# --- v3.1: scenario nodes + verifies/satisfies edges ---

def _scenario(sid="S1.1", req="R1"):
    return Scenario(
        id=sid, requirement_key=req,
        gwt_text="Given X\nWhen Y\nThen Z",
        run_cmd="pytest tests/test_x.py -q",
    )


def _plan_with_scenarios():
    prov = Provenance(spec_version="sp1", scenario_version="sc1", design_version="d1")
    sc = _scenario()
    return Plan(
        title="Scenario Plan",
        overview="o",
        out_of_scope=(),
        phases=(Phase(key="p1", title="P", goal="g", tasks=(
            Task("T1.1", "impl x", "pytest tests/test_x.py -q", verifies=("S1.1",)),
        )),),
        provenance=prov,
        scenarios=(sc,),
    )


def test_scenario_node_emitted():
    cmds = _cmds(compile(_plan_with_scenarios()))
    assert any("kind:scenario" in c for c in cmds)
    assert any("scenario:S1.1" in c for c in cmds)


def test_verifies_edge_emitted():
    # verifies maps to bd native `validates` typed edge (scenario -> spec)
    cmds = _cmds(compile(_plan_with_scenarios()))
    verifies = [c for c in cmds if "bd dep add" in c and "--type validates" in c]
    assert verifies, "verifies edge (scenario validates spec) must be emitted"
    # must NOT use the non-existent `bd related` command
    assert not any("bd related" in c for c in cmds)


def test_satisfies_edge_emitted():
    # satisfies maps to bd native `tracks` typed edge (task -> scenario)
    cmds = _cmds(compile(_plan_with_scenarios()))
    satisfies = [c for c in cmds if "bd dep add" in c and "--type tracks" in c]
    assert satisfies, "satisfies edge (task tracks scenario) must be emitted"


def test_unknown_scenario_reference_raises():
    prov = Provenance(spec_version="sp1", scenario_version="sc1")
    plan = Plan(
        title="Bad Ref",
        overview="o",
        out_of_scope=(),
        phases=(Phase(key="p1", title="P", goal="g", tasks=(
            Task("T1.1", "x", "true", verifies=("S9.9",)),  # S9.9 not in scenarios
        )),),
        provenance=prov,
        scenarios=(_scenario("S1.1"),),
    )
    with pytest.raises(CompileError, match="unknown scenario"):
        compile(plan)


def test_task_without_verifies_still_compiles():
    prov = Provenance(spec_version="sp1", scenario_version="sc1")
    plan = Plan(
        title="Mixed",
        overview="o",
        out_of_scope=(),
        phases=(Phase(key="p1", title="P", goal="g", tasks=(
            Task("T1.1", "meta task", "echo ok"),  # no verifies — infra task
            Task("T1.2", "impl x", "pytest -q", verifies=("S1.1",)),
        )),),
        provenance=prov,
        scenarios=(_scenario("S1.1"),),
    )
    res = compile(plan)
    cmds = _cmds(res)
    satisfies = [c for c in cmds if "bd dep add" in c and "--type tracks" in c]
    assert len(satisfies) == 1, "only T1.2 should produce a satisfies edge"


def test_scenario_not_emitted_when_scenario_version_empty():
    # Guard: non-empty scenarios + empty scenario_version -> no scenario labels (malformed key prevention)
    prov = Provenance(spec_version="sp1")  # scenario_version defaults to ""
    sc = _scenario()
    plan = Plan(
        title="No Sc Version",
        overview="o",
        out_of_scope=(),
        phases=(Phase(key="p1", title="P", goal="g", tasks=(
            Task("T1.1", "x", "true"),
        )),),
        provenance=prov,
        scenarios=(sc,),
    )
    cmds = _cmds(compile(plan))
    assert not any("kind:scenario" in c for c in cmds)
    # also: no label ending in bare "athena:scenario:" (trailing colon)
    assert not any(":scenario:" in c and c.endswith(":") for c in cmds)


def test_scenario_node_idempotent():
    plan = _plan_with_scenarios()
    first = compile(plan)
    all_keys = frozenset(
        a for c in first.commands for i, a in enumerate(c.argv)
        if i > 0 and c.argv[i - 1] == "--label" and a.startswith(EXTERNAL_KEY_PREFIX)
    )
    second = compile(plan, existing_keys=all_keys)
    assert _cmds(second) == [], "full re-compile must be no-op"
