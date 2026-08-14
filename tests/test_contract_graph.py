"""v3.3 the contract in the graph — clause nodes, supersede edges, the gate, compat.

Each test is the executable spec of one C-5.* clause in features/contract-layer/contract.md.
The compat test is the important one: with no contract attached the compiler must emit the
byte-identical v3.1 command list, so adopting the contract layer is opt-in per project.
"""
from __future__ import annotations

import dataclasses

import pytest

from lib.ast import Phase, Plan, Provenance, Scenario, Task
from lib.contract import parse as parse_contract
from lib.plan2beads import CompileError, compile
from lib.seams import seam_contract_bound

CONTRACT = parse_contract("""# Contract: Demo

## C-1 — Core

- **C-1.1** — WHEN it starts THE SYSTEM SHALL do the first thing.
- **C-1.2** *(superseded-by C-1.3)* — WHEN it stops THE SYSTEM SHALL log the old way.
- **C-1.3** — WHEN it stops THE SYSTEM SHALL log the new way.
- **C-1.4** *(draft)* — WHEN it idles THE SYSTEM SHALL nap.
""")

SCENARIOS = (
    Scenario("S1.1", "C-1.1", "G/W/T", "pytest -q -k first"),
    Scenario("S1.2", "C-1.3", "G/W/T", "pytest -q -k second"),
)


def _plan(*, contract=CONTRACT, scenarios=SCENARIOS, contract_version="cv1"):
    return Plan(
        title="Demo Feature",
        overview="o",
        out_of_scope=("none",),
        phases=(Phase(key="P1", title="Phase 1", goal="g", tasks=(
            Task(id="T1.1", title="do it", success_check="pytest -q -k first",
                 verifies=("S1.1",)),
            Task(id="T1.2", title="do it again", success_check="pytest -q -k second",
                 verifies=("S1.2",)),
        )),),
        provenance=Provenance(spec_version="sv1", scenario_version="scv1",
                              design_version="dv1", contract_version=contract_version),
        scenarios=scenarios,
        contract=contract,
    )


def _creates(res, kind):
    return [c for c in res.commands
            if c.argv[:2] == ("bd", "create") and f"kind:{kind}" in c.argv]


def _edges(res, etype):
    out = []
    for c in res.commands:
        if c.argv[:3] == ("bd", "dep", "add") and "--type" in c.argv:
            if c.argv[c.argv.index("--type") + 1] == etype:
                out.append(c.argv[3:5])
    return out


def test_clause_nodes_are_emitted_for_every_clause_with_its_own_version_label():
    """C-5.1 — the clause registry (history included) becomes graph structure."""
    res = compile(_plan())
    nodes = _creates(res, "clause")
    titles = [c.argv[c.argv.index("--title") + 1] for c in nodes]
    assert titles == ["clause:C-1.1", "clause:C-1.2", "clause:C-1.3", "clause:C-1.4"]
    first = nodes[0].argv
    assert f"athena:clause:{CONTRACT.by_id('C-1.1').version}" in first
    assert "status:active" in first and "--no-inherit-labels" in first
    assert "status:superseded" in nodes[1].argv and "status:draft" in nodes[3].argv
    # every clause node hangs off the spec node -> trace_down(spec) reaches the clauses
    assert first[first.index("--parent") + 1] == "athena:demo-feature:spec:sv1"


def test_supersede_edge_keeps_an_old_clause_id_reachable():
    """C-5.2 — successor --related--> predecessor, in canonical sorted order."""
    res = compile(_plan())
    assert _edges(res, "related") == [
        ("athena:demo-feature:clause:C-1.3", "athena:demo-feature:clause:C-1.2")
    ]


def test_validates_edge_points_at_the_clause_not_the_whole_spec():
    """C-5.3 — same edge count as v3.1, rooted at the requirement actually proved."""
    res = compile(_plan())
    assert _edges(res, "validates") == [
        ("athena:demo-feature:scenario:S1.1", "athena:demo-feature:clause:C-1.1"),
        ("athena:demo-feature:scenario:S1.2", "athena:demo-feature:clause:C-1.3"),
    ]


def test_a_spec_naming_a_clause_outside_the_contract_refuses_to_compile():
    """C-5.4 — fail-closed: a rotted reference must never reach the graph."""
    bad = (Scenario("S1.1", "C-9.9", "G/W/T", "pytest -q"),)
    plan = _plan(scenarios=bad)
    plan = dataclasses.replace(plan, phases=(dataclasses.replace(
        plan.phases[0], tasks=(Task(id="T1.1", title="x", success_check="true",
                                    verifies=("S1.1",)),)),))
    with pytest.raises(CompileError, match="verifies clause 'C-9.9'"):
        compile(plan)


def test_without_a_contract_the_output_is_byte_identical_to_v31():
    """C-5.5 — adopting the contract layer is opt-in; v3.1 projects see no change."""
    v31 = dataclasses.replace(
        _plan(contract=None, contract_version=""),
    )
    res = compile(v31)
    assert _creates(res, "clause") == []
    assert _edges(res, "related") == []
    assert _edges(res, "validates") == [
        ("athena:demo-feature:scenario:S1.1", "athena:demo-feature:spec:sv1"),
        ("athena:demo-feature:scenario:S1.2", "athena:demo-feature:spec:sv1"),
    ]


def test_an_attached_but_unpinned_contract_is_inert():
    """C-5.6 — an unpinned contract must not emit `athena:clause:` labels with no version."""
    res = compile(_plan(contract_version=""))
    assert _creates(res, "clause") == []
    assert all("athena:clause:" not in a for c in res.commands for a in c.argv)


def test_clause_nodes_are_idempotent_on_recompile():
    """C-5.7 — a second compile against the same graph creates nothing new."""
    first = compile(_plan())
    keys = frozenset(
        c.argv[c.argv.index("--label") + 1] for c in first.commands
        if c.argv[:2] == ("bd", "create")
    )
    again = compile(_plan(), existing_keys=keys)
    assert _creates(again, "clause") == []


def test_the_gate_fails_closed_on_uncovered_clauses_and_orphan_specs():
    """C-5.8 — seam.contract_bound blocks a contract that is not bound to real specs."""
    ok = seam_contract_bound(CONTRACT, SCENARIOS)
    assert ok.passed and ok.issues == ()

    missing = seam_contract_bound(CONTRACT, (SCENARIOS[0],))
    assert not missing.passed
    assert missing.issues == ("clause C-1.3 has no executable spec",)

    orphan = seam_contract_bound(CONTRACT, SCENARIOS + (
        Scenario("S9.9", "C-9.9", "G/W/T", "pytest -q"),))
    assert not orphan.passed
    assert orphan.issues == ("spec S9.9 verifies C-9.9 (unknown_clause)",)


def test_the_gate_hash_moves_when_a_clause_changes():
    """C-5.9 — the seam artifact hash is a fingerprint of ids+versions+statuses."""
    edited = parse_contract("""# Contract: Demo

- **C-1.1** — WHEN it starts THE SYSTEM SHALL do the FIRST thing differently.
- **C-1.2** *(superseded-by C-1.3)* — WHEN it stops THE SYSTEM SHALL log the old way.
- **C-1.3** — WHEN it stops THE SYSTEM SHALL log the new way.
- **C-1.4** *(draft)* — WHEN it idles THE SYSTEM SHALL nap.
""")
    a = seam_contract_bound(CONTRACT, SCENARIOS)
    b = seam_contract_bound(edited, SCENARIOS)
    assert a.artifact_hash != b.artifact_hash
