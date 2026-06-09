"""
Athena seams — fail-closed contracts + observability at the framework boundaries.

The frameworks (CRISP / Spec-Kit / Beads) are battle-tested; the bugs live in OUR glue at
the seams. So every cross-boundary handoff gets (a) a fail-closed validator that fires AT
the seam — cheap to debug, it breaks where it breaks, not three stages later — and (b) a
structural record for observability.

Freeze-line split (same as the compiler):
  * the validators below are PURE + deterministic + fail-closed — golden-able.
  * record_seam() is the ONLY effectful bit (ts injected, JSONL append) — never in a validator.

Deterministic seams (1,5,6,7,8,9) are guaranteed by tests. Fuzzy seams (2,3 — LLM handoffs)
can only guarantee STRUCTURAL completeness + an auditable record; semantics are Hermes's
tier-review job, not a golden test.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass

from lib.ast import Plan


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def trace_id_hex(run_id: str) -> str:
    """128-bit (32-hex) OTel trace_id, deterministic from run_id — correlates one run."""
    return hashlib.sha256((run_id or "norun").encode("utf-8")).hexdigest()[:32]


def span_id_hex(seed: str) -> str:
    """64-bit (16-hex) OTel span_id, deterministic from a seed."""
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SeamResult:
    name: str
    passed: bool
    issues: tuple[str, ...] = ()
    artifact_hash: str = ""


@dataclass(frozen=True)
class SeamRecord:
    name: str
    passed: bool
    issues: tuple[str, ...]
    artifact_hash: str
    src: str
    dst: str
    ts: str                                       # injected ISO ts — never time.time() in this module
    context: tuple[tuple[str, str], ...] = ()
    # --- OTel-span-compatible correlation (all INJECTED; validators stay pure) ---
    run_id: str = ""                              # one run -> OTel trace_id (the cross-cut thread)
    span_id: str = ""                             # this seam's 16-hex OTel span id
    parent_span_id: str = ""                      # 16-hex of an earlier seam's span_id -> SDK chain (else run root)
    ts_ns: int = 0                                # injected unix-nano START (0 -> SDK clock)
    ts_ns_end: int = 0                            # injected unix-nano END (0 -> == start, a point check)

    def to_json(self) -> str:
        return json.dumps({
            "name": self.name, "passed": self.passed, "issues": list(self.issues),
            "hash": self.artifact_hash, "src": self.src, "dst": self.dst,
            "ts": self.ts, "context": dict(self.context),
            "run_id": self.run_id, "span_id": self.span_id,
            "parent_span_id": self.parent_span_id, "ts_ns": self.ts_ns,
            "ts_ns_end": self.ts_ns_end,
        }, ensure_ascii=False, sort_keys=True)

    def to_otel_span_dict(self) -> dict:
        """OTel-span-compatible field schema — maps 1:1 onto an OTLP span (trace-ready)."""
        return {
            "trace_id": trace_id_hex(self.run_id),
            "span_id": self.span_id or span_id_hex(f"{self.run_id}:{self.name}:{self.ts}"),
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time_unix_nano": self.ts_ns,
            "end_time_unix_nano": self.ts_ns_end or self.ts_ns,
            "status": {"code": "OK" if self.passed else "ERROR",
                       "message": "" if self.passed else "; ".join(self.issues)},
            "attributes": {
                "athena.run_id": self.run_id,
                "seam.src": self.src, "seam.dst": self.dst,
                "seam.passed": self.passed, "seam.hash": self.artifact_hash,
                **({"seam.issues": list(self.issues)} if self.issues else {}),
                **{f"seam.ctx.{k}": v for k, v in self.context},
            },
        }

    @classmethod
    def from_json(cls, line: str) -> "SeamRecord":
        """Replay a JSONL line back into a SeamRecord (durable solo trace -> emit_otel)."""
        d = json.loads(line)
        return cls(d["name"], d["passed"], tuple(d["issues"]), d["hash"], d["src"], d["dst"],
                   d["ts"], tuple(sorted((str(k), str(v)) for k, v in d["context"].items())),
                   d.get("run_id", ""), d.get("span_id", ""), d.get("parent_span_id", ""),
                   d.get("ts_ns", 0), d.get("ts_ns_end", 0))


# --- seam validators (pure, fail-closed) ---------------------------------------

def seam_intent(intent: str, repo_resolves: bool) -> SeamResult:
    """Seam 1: Hermes -> CRISP. intent non-empty + repo resolves."""
    issues = []
    if not (intent or "").strip():
        issues.append("intent is empty")
    if not repo_resolves:
        issues.append("repo path does not resolve")
    return SeamResult("seam.intent", not issues, tuple(issues), _hash(intent or ""))


def seam_structural(name: str, text: str, *, required: tuple[str, ...],
                    forbidden: tuple[str, ...] = ()) -> SeamResult:
    """Fuzzy-seam guard (2,3): STRUCTURAL completeness only — required sections present,
    forbidden markers absent. Does NOT judge semantics (that is Hermes tier-review)."""
    issues = [f"missing required section: {r}" for r in required if r not in text]
    issues += [f"forbidden marker present: {f}" for f in forbidden if f in text]
    return SeamResult(name, not issues, tuple(issues), _hash(text))


def _has_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}

    def visit(n: str) -> bool:
        color[n] = GRAY
        for m in graph.get(n, ()):
            if m not in color:        # dep to unknown node — reported elsewhere
                continue
            if color[m] == GRAY:
                return True
            if color[m] == WHITE and visit(m):
                return True
        color[n] = BLACK
        return False

    return any(color[k] == WHITE and visit(k) for k in graph)


def seam_ast_wellformed(plan: Plan) -> SeamResult:
    """Seam 6: success_check non-empty, deps resolve, no dup task ids, NO CYCLES
    (the compiler does not check cycles — this seam closes that gap)."""
    issues: list[str] = []
    keys = [ph.key for ph in plan.phases]
    if len(set(keys)) != len(keys):
        issues.append("duplicate phase key")
    keyset = set(keys)
    seen: set[str] = set()
    for ph in plan.phases:
        if not ph.tasks:
            issues.append(f"phase {ph.key} has no tasks")
        for d in ph.depends_on:
            if d not in keyset:
                issues.append(f"phase {ph.key} depends on missing {d}")
        for t in ph.tasks:
            if not t.success_check.strip():
                issues.append(f"task {t.id} missing success_check")
            if t.id in seen:
                issues.append(f"duplicate task id {t.id}")
            seen.add(t.id)
    if _has_cycle({ph.key: tuple(ph.depends_on) for ph in plan.phases}):
        issues.append("dependency cycle among phases")
    shape = repr([(p.key, p.depends_on, tuple(t.id for t in p.tasks)) for p in plan.phases])
    return SeamResult("seam.ast_wellformed", not issues, tuple(issues), _hash(shape))


def seam_compile_pure(compile_fn, plan: Plan) -> SeamResult:
    """Seam 7: same AST -> same commands twice (determinism)."""
    a = [str(c) for c in compile_fn(plan).commands]
    b = [str(c) for c in compile_fn(plan).commands]
    passed = a == b
    return SeamResult("seam.compile_pure", passed,
                      () if passed else ("compile is non-deterministic",), _hash("\n".join(a)))


def seam_graph_materialized(plan: Plan, bd_issues: list[dict], slug: str) -> SeamResult:
    """Seam 8 (POST-CONDITION read-back): re-read bd, the graph must match AST intent.
    bd_issues = parsed `bd list --label athena --json`. Catches Beads schema drift +
    partial `bd` failures — the 'glue tore' class."""
    expected = ({f"athena:{slug}:{ph.key}" for ph in plan.phases}
                | {f"athena:{slug}:{t.id}" for ph in plan.phases for t in ph.tasks})
    found = {lbl for it in bd_issues for lbl in it.get("labels", [])
             if lbl.startswith(f"athena:{slug}:")}
    missing = expected - found
    issues = [f"missing from graph: {sorted(missing)}"] if missing else []
    return SeamResult("seam.graph_materialized", not issues, tuple(issues), _hash(repr(sorted(found))))


def seam_toggle_equiv(plan_a: Plan, plan_b: Plan) -> SeamResult:
    """Seam 9: two fronts -> structurally equivalent AST (same phase keys + task ids + deps)."""
    def shape(p: Plan):
        return [(ph.key, tuple(sorted(ph.depends_on)), tuple(t.id for t in ph.tasks)) for ph in p.phases]
    passed = shape(plan_a) == shape(plan_b)
    return SeamResult("seam.toggle_equiv", passed,
                      () if passed else ("toggle paths produce structurally different ASTs",),
                      _hash(repr(shape(plan_a))))


# --- observability: record (effectful) + render (pure) -------------------------

def make_record(result: SeamResult, *, src: str, dst: str, ts: str,
                context: dict | None = None, run_id: str = "",
                parent_span_id: str = "", ts_ns: int = 0, ts_ns_end: int = 0) -> SeamRecord:
    ctx = tuple(sorted((str(k), str(v)) for k, v in (context or {}).items()))
    span_id = span_id_hex(f"{run_id}:{result.name}:{ts}")
    return SeamRecord(result.name, result.passed, result.issues, result.artifact_hash,
                      src, dst, ts, ctx, run_id, span_id, parent_span_id, ts_ns, ts_ns_end)


def record_seam(record: SeamRecord, *, path) -> None:
    """The ONLY effectful function: append one SeamRecord as a JSONL line. ts already injected."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")


def load_seams(path) -> list:
    """Read a seams.jsonl back into SeamRecords (durable solo trace -> emit_otel replay)."""
    p = pathlib.Path(path)
    if not p.exists():
        return []
    return [SeamRecord.from_json(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def render_mermaid(records: list[SeamRecord]) -> str:
    """Pure: SeamRecord list -> a Mermaid flowchart (waterfall of seams, pass/fail)."""
    lines = ["```mermaid", "flowchart TD"]
    prev = None
    for i, r in enumerate(records):
        nid = f"s{i}"
        status = "OK" if r.passed else "FAIL"
        lines.append(f'    {nid}["{r.name}<br/>{r.src}->{r.dst} [{status}]"]')
        if not r.passed:
            lines.append(f"    class {nid} failnode")
        if prev:
            lines.append(f"    {prev} --> {nid}")
        prev = nid
    lines.append("    classDef failnode fill:#fdd,stroke:#c00")
    lines.append("```")
    return "\n".join(lines)


def emit_otel(records, *, span_processor=None, tracer_provider=None):
    """
    Emit SeamRecords as real OpenTelemetry spans (EFFECTFUL). run_id -> trace_id correlates
    every seam of one pipeline run into ONE distributed trace — the cross-cut thread that no
    framework (CRISP files / Spec-Kit analyze / bd db) gives you. Pass span_processor (e.g.
    otlp_processor(endpoint)) to ship to Jaeger/Tempo, or a tracer_provider directly.
    Returns the (force-flushed) provider.
    """
    from collections import defaultdict
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import (NonRecordingSpan, SpanContext, TraceFlags,
                                      set_span_in_context)
    from opentelemetry.trace.status import Status, StatusCode

    provider = tracer_provider
    if provider is None:
        provider = TracerProvider()
        if span_processor is not None:
            provider.add_span_processor(span_processor)
    tracer = provider.get_tracer("athena.seams")

    by_run: dict[str, list] = defaultdict(list)
    for r in records:
        by_run[r.run_id or "norun"].append(r)

    for run_id, recs in by_run.items():
        root_ctx = set_span_in_context(NonRecordingSpan(SpanContext(
            trace_id=int(trace_id_hex(run_id), 16),
            span_id=int(span_id_hex(f"{run_id}:root"), 16),
            is_remote=False, trace_flags=TraceFlags(TraceFlags.SAMPLED))))
        emitted: dict = {}                            # logical span_id -> emitted SDK span (for chains)
        for r in recs:
            d = r.to_otel_span_dict()
            # honor parent_span_id: chain under the earlier seam's SDK span if we emitted it, else root
            parent = set_span_in_context(emitted[r.parent_span_id]) if r.parent_span_id in emitted else root_ctx
            span = tracer.start_span(r.name, context=parent, start_time=r.ts_ns or None)
            for k, v in d["attributes"].items():
                span.set_attribute(k, v)
            span.set_status(Status(StatusCode.OK if r.passed else StatusCode.ERROR,
                                   d["status"]["message"]))
            span.end(end_time=(r.ts_ns_end or r.ts_ns) or None)
            emitted[r.span_id] = span

    if tracer_provider is None:                       # only flush providers we created
        provider.force_flush()
    return provider


def otlp_processor(endpoint: str = "http://localhost:4317"):
    """Convenience: a SimpleSpanProcessor wired to an OTLP/gRPC collector (Jaeger/Tempo)."""
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    return SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
