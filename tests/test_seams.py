import json
import pathlib

from lib.ast import Plan, Phase, Task
from lib.plan_parser import parse as plan_parse
from lib.plan2beads import compile, _slugify
from lib import seams

FIX = pathlib.Path(__file__).parent / "fixtures"


def _plan() -> Plan:
    return plan_parse((FIX / "valid.md").read_text(encoding="utf-8"))


def test_seam_intent_pass_and_fail():
    assert seams.seam_intent("build x", True).passed
    r = seams.seam_intent("", False)
    assert not r.passed
    assert len(r.issues) == 2


def test_seam_structural_required_and_forbidden():
    assert seams.seam_structural("seam.research", "## Facts\nstuff", required=("## Facts",)).passed
    bad = seams.seam_structural("seam.research", "nothing", required=("## Facts",))
    assert not bad.passed
    forb = seams.seam_structural("seam.design", "has NEEDS_CLARIFICATION here", required=(),
                                 forbidden=("NEEDS_CLARIFICATION",))
    assert not forb.passed


def test_seam_ast_wellformed_pass():
    assert seams.seam_ast_wellformed(_plan()).passed


def test_seam_ast_wellformed_detects_cycle():
    plan = Plan("C", "o", (), (
        Phase("a", "A", "g", depends_on=("b",), tasks=(Task("T1", "x", "true"),)),
        Phase("b", "B", "g", depends_on=("a",), tasks=(Task("T2", "y", "true"),)),
    ))
    r = seams.seam_ast_wellformed(plan)
    assert not r.passed
    assert any("cycle" in i for i in r.issues)


def test_seam_ast_wellformed_detects_missing_check():
    plan = Plan("C", "o", (), (Phase("p", "P", "g", tasks=(Task("T1", "x", ""),)),))
    r = seams.seam_ast_wellformed(plan)
    assert not r.passed
    assert any("success_check" in i for i in r.issues)


def test_seam_compile_pure():
    assert seams.seam_compile_pure(compile, _plan()).passed


def test_seam_graph_materialized_readback():
    plan = _plan()
    slug = _slugify(plan.title)
    full = []
    for ph in plan.phases:
        full.append({"labels": [f"athena:{slug}:{ph.key}", "athena"]})
        for t in ph.tasks:
            full.append({"labels": [f"athena:{slug}:{t.id}", "athena"]})
    assert seams.seam_graph_materialized(plan, full, slug).passed
    # drop one issue -> partial bd failure / schema drift caught
    r = seams.seam_graph_materialized(plan, full[:-1], slug)
    assert not r.passed
    assert any("missing" in i for i in r.issues)


def test_seam_toggle_equiv():
    p = _plan()
    assert seams.seam_toggle_equiv(p, p).passed
    q = Plan("X", "o", (), (Phase("zzz", "Z", "g", tasks=(Task("T9", "x", "true"),)),))
    assert not seams.seam_toggle_equiv(p, q).passed


def test_record_jsonl_roundtrip(tmp_path):
    rec = seams.make_record(seams.seam_intent("x", True), src="Hermes", dst="CRISP",
                            ts="2026-06-09T00:00:00Z", context={"k": "v"})
    path = tmp_path / ".athena" / "seams.jsonl"
    seams.record_seam(rec, path=path)
    seams.record_seam(rec, path=path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    obj = json.loads(lines[0])
    assert obj["name"] == "seam.intent"
    assert obj["passed"] is True
    assert obj["ts"] == "2026-06-09T00:00:00Z"
    assert obj["context"] == {"k": "v"}


def test_render_mermaid_shows_pass_fail():
    recs = [
        seams.make_record(seams.seam_intent("x", True), src="Hermes", dst="CRISP", ts="t"),
        seams.make_record(seams.SeamResult("seam.analyze", False, ("inconsistent",)),
                          src="SpecKit", dst="compile", ts="t"),
    ]
    out = seams.render_mermaid(recs)
    assert "mermaid" in out
    assert "seam.intent" in out
    assert "FAIL" in out
    assert "failnode" in out
