"""Real-bd integration for v3+v3.1: provenance graph + scenario harness.

Compiles a Plan carrying Provenance + Scenarios, executes against a real `bd` in a
temp repo (label->ID resolution incl. the second positional of typed `bd dep add`),
and reads the graph back: spec/design/scenario nodes materialize and the
verifies(validates)/satisfies(tracks) typed edges wire correctly.

This is the test that surfaced the real bug fakes could not: the v3.1 edges were first
emitted as `bd related <a> <b> --label verifies`, a command bd v1.0.4 does not have.
Skipped if `bd` is not on PATH.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

from lib.ast import Plan, Phase, Task, Provenance, Scenario
from lib.plan2beads import compile, _slugify
from lib.bd_client import execute, fetch_existing_keys

BD = shutil.which("bd")
pytestmark = pytest.mark.skipif(BD is None, reason="bd not installed")


def _runner(cwd: pathlib.Path):
    def run(argv):
        argv = [BD if a == "bd" else str(a) for a in argv]
        return subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd)).stdout
    return run


def _v3_plan():
    prov = Provenance(
        spec_version="specv1", scenario_version="scenv1",
        design_version="desv1", run_id="run1",
    )
    scenario = Scenario(
        id="S1.1", requirement_key="R1",
        gwt_text="Given the system\nWhen pinged\nThen it responds",
        run_cmd="true",
    )
    return Plan(
        title="Prov E2E",
        overview="o",
        out_of_scope=(),
        phases=(Phase(key="p1", title="Build", goal="g", tasks=(
            Task("T1.1", "impl ping", "true", verifies=("S1.1",)),
        )),),
        provenance=prov,
        scenarios=(scenario,),
    )


def _labels_of(issues, kind):
    return [it for it in issues if f"kind:{kind}" in it.get("labels", [])]


def test_v3_provenance_graph_materializes(tmp_path):
    subprocess.run([BD, "init"], cwd=str(tmp_path), capture_output=True, text=True)
    run = _runner(tmp_path)
    plan = _v3_plan()

    execute(compile(plan), run=run)

    issues = json.loads(run(["bd", "list", "--label", "athena", "--json"]) or "[]")
    # spec + design + scenario + epic + task = 5 nodes
    assert len(_labels_of(issues, "spec")) == 1, "spec node must materialize"
    assert len(_labels_of(issues, "design")) == 1, "design node must materialize"
    assert len(_labels_of(issues, "scenario")) == 1, "scenario node must materialize"

    spec_id = _labels_of(issues, "spec")[0]["id"]
    scenario_id = _labels_of(issues, "scenario")[0]["id"]
    # task: the only issue with neither epic type nor a kind:* provenance label
    task = next(it for it in issues
                if it.get("issue_type") != "epic"
                and not any(l.startswith("kind:") for l in it.get("labels", [])))

    # verifies edge: scenario --[validates]--> spec
    scen_deps = run(["bd", "dep", "list", scenario_id])
    assert "validates" in scen_deps, f"scenario must validate spec; got: {scen_deps}"

    # satisfies edge: task --[tracks]--> scenario
    task_deps = run(["bd", "dep", "list", task["id"]])
    assert "tracks" in task_deps, f"task must track scenario; got: {task_deps}"


def test_v3_graph_is_idempotent(tmp_path):
    subprocess.run([BD, "init"], cwd=str(tmp_path), capture_output=True, text=True)
    run = _runner(tmp_path)
    plan = _v3_plan()

    execute(compile(plan), run=run)
    slug = _slugify(plan.title)
    existing = fetch_existing_keys(slug, run=run)

    res2 = compile(plan, existing_keys=existing)
    creates = [c for c in res2.commands if str(c).split()[:2] == ["bd", "create"]]
    assert creates == [], "re-compile of unchanged v3 plan must create nothing"


def test_v3_no_bd_related_command_emitted(tmp_path):
    # Regression guard for the real bug: bd has no `related` command.
    plan = _v3_plan()
    res = compile(plan)
    assert not any("bd related" in str(c) for c in res.commands)
    # the verifies/satisfies edges use native typed deps
    assert any("--type validates" in str(c) for c in res.commands)
    assert any("--type tracks" in str(c) for c in res.commands)
