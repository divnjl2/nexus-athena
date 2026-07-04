"""v3.2 — coverage-backed provenance: close the code->spec leg the graph only DECLARES.

Athena v3.1 proves spec -> scenario -> pass (top-down, the `scenario_failed` backedge). It is
blind to two failures of the REVERSE leg, both surfaced by the qa_unit pilot:

  (a) fake `satisfies` edge — a task claims `verifies: S`, its scenario passes (exit 0), but the
      scenario never covers the task's SOURCE. The edge is declared, not real.
  (b) orphan code / `spec_gap` — a code branch no scenario exercises: code with no requirement.

Both are read deterministically from a coverage.xml produced by RUNNING the scenarios. This
module is the mirror of `scenario_failed`: it turns the dotted `code -> spec` arrow solid.
Stdlib-only, no LLM, pure — same freeze-line as the compiler and the other seams.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().lstrip("./")


def _is_test(path: str) -> bool:
    """Test files are the scenario RUNNERS; the SOURCE files are what a real edge must cover."""
    p = _norm(path)
    base = p.rsplit("/", 1)[-1]
    return base.startswith("test_") or base.endswith("_test.py") or "/tests/" in p


@dataclass(frozen=True)
class FileCoverage:
    path: str
    line_rate: float
    covered_lines: frozenset
    uncovered_branches: tuple


@dataclass(frozen=True)
class Coverage:
    files: dict           # path -> FileCoverage

    def covered(self, path: str) -> bool:
        fc = self.files.get(_norm(path))
        return bool(fc and fc.covered_lines)


def parse_coverage(xml_text: str) -> Coverage:
    """Cobertura coverage.xml -> per-file covered lines + uncovered branch lines. Deterministic."""
    root = ET.fromstring(xml_text)
    files: dict = {}
    for cls in root.iter("class"):
        path = _norm(cls.get("filename", ""))
        if not path:
            continue
        covered = set()
        uncovered_br = set()
        for ln in cls.iter("line"):
            num = ln.get("number")
            if num is None:
                continue
            n = int(num)
            if ln.get("hits", "0") != "0":
                covered.add(n)
            if ln.get("branch") == "true":
                cc = ln.get("condition-coverage") or ""
                if cc and "100%" not in cc:
                    uncovered_br.add(n)
        if path in files:                       # class listed twice -> merge
            prev = files[path]
            covered |= set(prev.covered_lines)
            uncovered_br |= set(prev.uncovered_branches)
        files[path] = FileCoverage(path, float(cls.get("line-rate", 0.0)),
                                   frozenset(covered), tuple(sorted(uncovered_br)))
    return Coverage(files)


def trace_coverage(plan, cov: Coverage) -> dict:
    """The third trace axis (v3.2): walk every `satisfies` edge and confirm the scenario
    actually covers the task's source; then list orphan branches (code with no scenario).

    Returns a report the `planner_trace_coverage` verb exposes and `planner_replan` reads:
      proven_edges   — task->scenario where the source IS covered (real edge)
      unproven_edges — task->scenario declared but source uncovered (FAKE edge)
      spec_gaps      — file:line branches no scenario exercises (orphan code)
      replan_trigger — 'satisfies_unproven' | 'spec_gap' | None
    """
    proven, unproven = [], []
    for ph in plan.phases:
        for t in ph.tasks:
            srcs = [f for f in t.files if not _is_test(f)]
            if not t.verifies or not srcs:
                continue                         # harness/meta task: no edge to prove
            covered_srcs = [s for s in srcs if cov.covered(s)]
            edge = {"task": t.id, "verifies": list(t.verifies),
                    "src": srcs, "covered_src": covered_srcs}
            (proven if covered_srcs else unproven).append(edge)

    spec_gaps = [f"{path}:{ln}" for path, fc in sorted(cov.files.items())
                 for ln in fc.uncovered_branches]

    trigger = "satisfies_unproven" if unproven else ("spec_gap" if spec_gaps else None)
    return {
        "proven_edges": proven,
        "unproven_edges": unproven,
        "spec_gaps": spec_gaps,
        "spec_gap_count": len(spec_gaps),
        "proven": len(proven),
        "unproven": len(unproven),
        "replan_trigger": trigger,
    }
