"""v3.1 regression: the canonical plan.md path materialises task->scenario provenance.

Before this fix the flat `plan.md -> bd` path silently dropped `verifies:` lines
(plan_parser had no field) and emitted no scenario nodes / verifies / satisfies edges.
These tests pin the whole chain on the real snake-game showcase artifacts.
"""
from __future__ import annotations

import pathlib

import pytest

from lib.ast import Scenario
from lib.frontend import parse_source, parse_with_provenance
from lib.plan2beads import compile
from lib.plan_parser import parse as parse_plan
from lib.scenario_parser import ScenarioParseError
from lib.scenario_parser import parse as parse_scenarios

EXAMPLE = pathlib.Path(__file__).resolve().parents[1] / "examples" / "snake_game"


def _edge_types(res):
    out = {}
    for c in res.commands:
        if "dep" in c.argv and "--type" in c.argv:
            t = c.argv[c.argv.index("--type") + 1]
            out[t] = out.get(t, 0) + 1
    return out


# ---- 1. plan_parser now parses `verifies:` ----

def test_plan_parser_extracts_verifies():
    plan = parse_plan((EXAMPLE / "plan.md").read_text(encoding="utf-8"))
    tasks = [t for ph in plan.phases for t in ph.tasks]
    assert tasks, "no tasks parsed"
    assert all(t.verifies for t in tasks), "every snake task binds a scenario"
    t11 = next(t for t in tasks if t.id == "T1.1")
    assert t11.verifies == ("S3.1",)


def test_verifies_is_optional_backward_compat():
    src = (
        "# Plan: x\n## Overview\no\n## Out of Scope\n- none\n"
        "## Phase 1: p\n**Goal:** g\n**Depends on:** none\n### Tasks\n"
        "- [ ] T1.1 do it\n  - success_check: `true`\n"
    )
    plan = parse_plan(src)
    assert plan.phases[0].tasks[0].verifies == ()


# ---- 2. scenario_parser ----

def test_scenario_parser_round_trip():
    scen = parse_scenarios((EXAMPLE / "scenarios.md").read_text(encoding="utf-8"))
    assert len(scen) == 31
    assert all(isinstance(s, Scenario) for s in scen)
    s11 = next(s for s in scen if s.id == "S1.1")
    assert s11.requirement_key == "R1.1"
    assert s11.run_cmd.startswith("pytest ")
    assert "Given" in s11.gwt_text and "Then" in s11.gwt_text


def test_scenario_parser_keeps_multiline_gwt():
    """Regression: a Given/When/Then clause wrapped onto an indented continuation line
    must NOT be silently truncated (was cutting 4/31 snake scenarios mid-sentence)."""
    scen = parse_scenarios((EXAMPLE / "scenarios.md").read_text(encoding="utf-8"))
    by_id = {s.id: s for s in scen}
    # S1.1 Then wraps: "...near the center with the\n  head as the right-most cell..."
    assert "head as the right-most cell and the heading set to Right." in by_id["S1.1"].gwt_text
    # S4.2 Then wraps onto a second line too
    assert "valid non-reversing input relative to the committed Right heading" in by_id["S4.2"].gwt_text
    # no scenario should end on a known truncation fragment
    for s in scen:
        assert not s.gwt_text.endswith("with the")
        assert not s.gwt_text.endswith("(the last")


def test_scenario_parser_rejects_empty():
    with pytest.raises(ScenarioParseError):
        parse_scenarios("# no scenarios here\n")


# ---- 3. end-to-end: edges materialise ----

def test_flat_plan_emits_no_provenance_edges():
    """Baseline: without provenance attachment, no scenario/verifies/satisfies edges."""
    plan = parse_plan((EXAMPLE / "plan.md").read_text(encoding="utf-8"))
    res = compile(plan)
    assert _edge_types(res) == {}  # only blocked-by (no --type) edges exist


def test_parse_with_provenance_materialises_edges():
    plan = parse_with_provenance(str(EXAMPLE / "plan.md"), speckit=False)
    assert len(plan.scenarios) == 31
    assert plan.provenance.spec_version and plan.provenance.scenario_version
    res = compile(plan)
    edges = _edge_types(res)
    # one validates edge per scenario (scenario -> spec)
    assert edges["validates"] == 31
    # one tracks edge per task->scenario binding (27 tasks each verify exactly one)
    assert edges["tracks"] == 27


def test_provenance_compile_is_deterministic():
    p1 = parse_with_provenance(str(EXAMPLE / "plan.md"), speckit=False)
    p2 = parse_with_provenance(str(EXAMPLE / "plan.md"), speckit=False)
    assert [c.argv for c in compile(p1).commands] == [c.argv for c in compile(p2).commands]
