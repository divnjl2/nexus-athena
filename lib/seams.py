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
    ts: str                                       # injected — never time.time() in this module
    context: tuple[tuple[str, str], ...] = ()

    def to_json(self) -> str:
        return json.dumps({
            "name": self.name, "passed": self.passed, "issues": list(self.issues),
            "hash": self.artifact_hash, "src": self.src, "dst": self.dst,
            "ts": self.ts, "context": dict(self.context),
        }, ensure_ascii=False, sort_keys=True)


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
                context: dict | None = None) -> SeamRecord:
    ctx = tuple(sorted((str(k), str(v)) for k, v in (context or {}).items()))
    return SeamRecord(result.name, result.passed, result.issues, result.artifact_hash, src, dst, ts, ctx)


def record_seam(record: SeamRecord, *, path) -> None:
    """The ONLY effectful function: append one SeamRecord as a JSONL line. ts already injected."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")


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
