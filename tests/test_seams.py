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


def test_to_otel_span_dict_schema():
    r = seams.make_record(seams.seam_intent("x", True), src="Hermes", dst="CRISP",
                          ts="t", run_id="r1", ts_ns=5)
    d = r.to_otel_span_dict()
    assert d["trace_id"] == seams.trace_id_hex("r1") and len(d["trace_id"]) == 32
    assert len(d["span_id"]) == 16
    assert d["name"] == "seam.intent"
    assert d["start_time_unix_nano"] == 5
    assert d["status"]["code"] == "OK"
    assert d["attributes"]["athena.run_id"] == "r1"
    assert d["attributes"]["seam.src"] == "Hermes"
    assert d["attributes"]["seam.passed"] is True


def test_to_otel_span_dict_error_carries_issues():
    r = seams.make_record(seams.SeamResult("seam.analyze", False, ("inconsistent",)),
                          src="SpecKit", dst="compile", ts="t", run_id="r1")
    d = r.to_otel_span_dict()
    assert d["status"]["code"] == "ERROR"
    assert "inconsistent" in d["status"]["message"]
    assert d["attributes"]["seam.issues"] == ["inconsistent"]


def test_emit_otel_correlates_run_by_trace_id():
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exp = InMemorySpanExporter()
    recs = [
        seams.make_record(seams.seam_intent("x", True), src="Hermes", dst="CRISP",
                          ts="t1", run_id="run-abc", ts_ns=1000),
        seams.make_record(seams.SeamResult("seam.analyze", False, ("inconsistent",)),
                          src="SpecKit", dst="compile", ts="t2", run_id="run-abc", ts_ns=2000),
    ]
    seams.emit_otel(recs, span_processor=SimpleSpanProcessor(exp))
    spans = exp.get_finished_spans()
    assert len(spans) == 2
    # both seams of one run share ONE trace_id — the cross-cut thread
    assert spans[0].context.trace_id == spans[1].context.trace_id
    assert spans[0].context.trace_id == int(seams.trace_id_hex("run-abc"), 16)
    by_name = {s.name: s for s in spans}
    assert by_name["seam.intent"].status.status_code.name == "OK"
    assert by_name["seam.analyze"].status.status_code.name == "ERROR"
    assert by_name["seam.intent"].attributes["athena.run_id"] == "run-abc"


def test_emit_otel_distinct_runs_distinct_traces():
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exp = InMemorySpanExporter()
    recs = [
        seams.make_record(seams.seam_intent("a", True), src="H", dst="C", ts="t", run_id="run-1"),
        seams.make_record(seams.seam_intent("b", True), src="H", dst="C", ts="t", run_id="run-2"),
    ]
    seams.emit_otel(recs, span_processor=SimpleSpanProcessor(exp))
    tids = {s.context.trace_id for s in exp.get_finished_spans()}
    assert len(tids) == 2   # different runs -> different traces


def test_emit_otel_honors_parent_chain_and_duration():
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exp = InMemorySpanExporter()
    r1 = seams.make_record(seams.seam_intent("a", True), src="H", dst="C", ts="t1",
                           run_id="run-x", ts_ns=1000, ts_ns_end=4000)
    r2 = seams.make_record(seams.seam_intent("b", True), src="C", dst="D", ts="t2",
                           run_id="run-x", parent_span_id=r1.span_id, ts_ns=5000, ts_ns_end=9000)
    seams.emit_otel([r1, r2], span_processor=SimpleSpanProcessor(exp))
    spans = exp.get_finished_spans()
    s1 = next(s for s in spans if s.start_time == 1000)
    s2 = next(s for s in spans if s.start_time == 5000)
    assert s1.end_time == 4000                         # duration honored (not zero-width)
    assert s2.parent.span_id == s1.context.span_id     # r2 chained under r1's REAL SDK span
    assert s1.context.trace_id == s2.context.trace_id  # same run
