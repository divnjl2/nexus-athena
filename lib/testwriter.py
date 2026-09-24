"""The test-writer's selector (C-8.1): candidate reproduction tests are kept by what they do.

Drafted by the vanilla 9B through pi (three iterations, one reason string short); finished
by Claude (ADR-0007). A candidate is admissible when it parses, defines exactly one test
function whose docstring names the clause, and its run on the code as it is fails for a
failure — not an error, not a skip, not a pass. Admissible candidates cluster by normalised
source; the largest cluster's first member is chosen; one representative per cluster is
kept for review.

PURE throughout.
"""
from __future__ import annotations

import ast


def _tests(source: str):
    """The test functions of a candidate module text, or None when it does not parse."""
    try:
        tree = ast.parse(source or "")
    except (SyntaxError, ValueError):
        return None
    return [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test_")]


def test_function_name(source: str) -> str:
    """The one test function's name, "" when the text does not parse or holds any number of
    test functions other than one."""
    tests = _tests(source)
    if not tests or len(tests) != 1:
        return ""
    return tests[0].name


def normalize_source(source: str) -> str:
    try:
        return ast.unparse(ast.parse(source or ""))
    except (SyntaxError, ValueError):
        return source or ""


def _pytest_counts(tail: str) -> dict:
    import re
    out = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for m in re.finditer(r"(\d+)\s+(passed|failed|skipped|errors?)\b", tail or ""):
        key = m.group(2)
        out["errors" if key.startswith("error") else key] += int(m.group(1))
    return out


def admissible(source: str, run: dict, *, clause: str = "") -> str:
    """Why a candidate is NOT admissible, "" when it is. The reasons are words a reviewer can
    grep: parse, one test, <clause id>, error, skip, passes."""
    tests = _tests(source)
    if tests is None:
        return "does not parse"
    if len(tests) != 1:
        return f"one test function expected, {len(tests)} found"
    fn = tests[0]
    doc = ast.get_docstring(fn) or ""
    if clause and not doc.startswith(clause + " "):
        return f"the docstring does not name {clause}"
    exit_code = int(run.get("exit", 1) or 0) if run.get("exit") is not None else 1
    tail = str(run.get("tail") or "")
    counts = _pytest_counts(tail)
    if counts["skipped"] or "skipped" in tail.lower():
        return "the run skipped: a skipped test proves nothing"
    if counts["errors"] or exit_code in (2, 3, 4) or "Error:" in tail and counts["failed"] == 0 and "Assertion" not in tail:
        return "the run ended in an error, not a failure"
    if exit_code == 0 or (counts["passed"] and not counts["failed"]):
        return "the test passes on the current code: it reproduces nothing"
    return ""


def choose_test(candidates: list, *, clause: str = "") -> dict:
    """The chosen test source ("" when none is admissible), the size of its cluster, how many
    candidates were admissible and rejected, and one representative per cluster."""
    kept, rejected = [], 0
    for cand in candidates or []:
        src = str(cand.get("source") or "")
        why = admissible(src, cand.get("run") or {}, clause=clause)
        if why:
            rejected += 1
        else:
            kept.append(src)
    if not kept:
        return {"source": "", "cluster_size": 0, "admissible": 0, "rejected": rejected, "representatives": []}
    clusters: dict = {}
    order: list = []
    for src in kept:
        key = normalize_source(src)
        if key not in clusters:
            clusters[key] = []
            order.append(key)
        clusters[key].append(src)
    best_key = max(order, key=lambda k: (len(clusters[k]), -order.index(k)))
    return {"source": clusters[best_key][0], "cluster_size": len(clusters[best_key]),
            "admissible": len(kept), "rejected": rejected,
            "representatives": [{"source": clusters[k][0], "size": len(clusters[k])} for k in order]}
