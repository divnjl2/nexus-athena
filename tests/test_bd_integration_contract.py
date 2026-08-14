"""Real-bd integration for v3.3: does `bd` actually ACCEPT the contract-layer commands?

The unit tests in test_contract_graph.py assert the SHAPE of the emitted commands. That is
exactly the assertion that missed the v3.1 bug: the edges were emitted as `bd related <a> <b>
--label verifies`, a command bd v1.0.4 does not have, and every fake-based test passed. So
this test executes the compiled graph against a real `bd` in a temp repo and reads it back:

  * `kind:clause` nodes materialize, one per clause, carrying their own version label
  * the supersede edge (`--type related`) is a type bd accepts
  * the `validates` edge lands on the CLAUSE node, not on the spec node

Skipped if `bd` is not on PATH.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

from lib.ast import Phase, Plan, Provenance, Scenario, Task
from lib.contract import parse as parse_contract
from lib.plan2beads import compile
from lib.bd_client import execute

BD = shutil.which("bd")
pytestmark = pytest.mark.skipif(BD is None, reason="bd not installed")

CONTRACT = parse_contract("""# Contract: Real BD

- **C-1.1** — WHEN pinged THE SYSTEM SHALL respond.
- **C-1.2** *(superseded-by C-1.3)* — WHEN pinged THE SYSTEM SHALL log the old way.
- **C-1.3** — WHEN pinged THE SYSTEM SHALL log the new way.
""")


def _runner(cwd: pathlib.Path):
    def run(argv):
        argv = [BD if a == "bd" else str(a) for a in argv]
        return subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd)).stdout
    return run


def _plan():
    return Plan(
        title="Contract E2E", overview="o", out_of_scope=(),
        phases=(Phase(key="p1", title="Build", goal="g",
                      tasks=(Task("T1.1", "impl ping", "true", verifies=("S1.1",)),)),),
        provenance=Provenance(spec_version="specv1", scenario_version="scenv1",
                              contract_version=CONTRACT.version, run_id="run1"),
        scenarios=(Scenario("S1.1", "C-1.1", "Given/When/Then", "true"),),
        contract=CONTRACT,
    )


def test_clause_nodes_and_edges_materialize_in_a_real_bd_graph(tmp_path):
    """C-5.11 — a real bd accepts the clause nodes, the supersede edge and the clause-rooted
    validates edge; the graph reads back with one clause node per clause."""
    subprocess.run([BD, "init"], cwd=str(tmp_path), capture_output=True, text=True)
    run = _runner(tmp_path)

    execute(compile(_plan()), run=run)

    issues = json.loads(run(["bd", "list", "--label", "athena", "--json"]) or "[]")
    clauses = [it for it in issues if "kind:clause" in it.get("labels", [])]
    assert len(clauses) == 3, f"one node per clause; got {[i['title'] for i in issues]}"
    assert {c["title"] for c in clauses} == {"clause:C-1.1", "clause:C-1.2", "clause:C-1.3"}

    by_title = {c["title"]: c for c in clauses}
    # per-clause version label (NOT a whole-file hash) survives the round trip
    assert f"athena:clause:{CONTRACT.by_id('C-1.1').version}" in by_title["clause:C-1.1"]["labels"]
    assert "status:superseded" in by_title["clause:C-1.2"]["labels"]

    # supersede edge: bd must ACCEPT `--type related` (the v3.1 bug class)
    deps_new = run(["bd", "dep", "list", by_title["clause:C-1.3"]["id"]])
    assert "related" in deps_new, f"supersede edge missing; got: {deps_new}"

    # validates edge lands on the CLAUSE, not on the spec node
    scenario = next(i for i in issues if "kind:scenario" in i.get("labels", []))
    deps_scen = run(["bd", "dep", "list", scenario["id"]])
    assert "validates" in deps_scen, f"validates edge missing; got: {deps_scen}"
    assert by_title["clause:C-1.1"]["id"] in deps_scen, (
        f"validates must target the clause, not the spec node; got: {deps_scen}")
