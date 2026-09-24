"""Selection among fanned attempts — by behaviour, not by order or text (C-5.8).

Drafted by the vanilla 9B through pi (three iterations, one assertion short); finished by
Claude (ADR-0007). What the lane got right stands: the cluster key is (normalised patch,
which checks passed), the quicker member represents its cluster, green clusters win by size.
What it missed: an attempt that did not land is still an attempt — its own cluster, kept
for the record, never selected.

PURE throughout.
"""
from __future__ import annotations

import ast


def normalize_source(source: str) -> str:
    """The program without its spacing and comments: parse and unparse. Unparsable text
    stays as it is, so a broken attempt clusters only with an identical broken attempt."""
    try:
        return ast.unparse(ast.parse(source or ""))
    except (SyntaxError, ValueError):
        return source or ""


def _key(attempt: dict) -> tuple:
    if not attempt.get("landed"):
        return ("<not landed>", ())
    sources = attempt.get("sources") or {}
    patch = tuple((path, normalize_source(text)) for path, text in sorted(sources.items()))
    passed = tuple(sorted(c.get("cmd", "") for c in (attempt.get("checks") or []) if c.get("exit", 1) == 0))
    return (patch, passed)


def cluster_attempts(attempts: list) -> list:
    """Attempts grouped by behaviour: the normalised patch and the set of checks that passed.
    Each cluster: members (indices, in order), green, landed, passed (count), representative
    (the quicker member)."""
    clusters: dict = {}
    order: list = []
    for i, attempt in enumerate(attempts):
        idx = attempt.get("index", i)
        key = _key(attempt)
        if key not in clusters:
            clusters[key] = {"members": [], "green": False, "landed": bool(attempt.get("landed")),
                             "passed": len(key[1]) if attempt.get("landed") else 0,
                             "representative": idx, "_rep_ms": int(attempt.get("duration_ms") or 0)}
            order.append(key)
        cl = clusters[key]
        cl["members"].append(idx)
        cl["green"] = cl["green"] or bool(attempt.get("green"))
        ms = int(attempt.get("duration_ms") or 0)
        if ms < cl["_rep_ms"]:
            cl["_rep_ms"], cl["representative"] = ms, idx
    out = []
    for key in order:
        cl = dict(clusters[key])
        cl.pop("_rep_ms", None)
        out.append(cl)
    return out


def select_attempt(attempts: list) -> dict:
    """The attempt to carry forward: the largest green cluster (the quicker representative on
    a tie), else the largest landed cluster with the most passed checks; None when nothing
    landed. One representative per cluster comes back for review."""
    clusters = cluster_attempts(attempts or [])
    reps = [{"index": cl["representative"], "size": len(cl["members"]), "green": cl["green"],
             "landed": cl["landed"], "passed": cl["passed"]} for cl in clusters]
    green_clusters = [cl for cl in clusters if cl["green"] and cl["landed"]]
    landed = [cl for cl in clusters if cl["landed"]]
    by_ms = {}
    for i, attempt in enumerate(attempts or []):
        by_ms[attempt.get("index", i)] = int(attempt.get("duration_ms") or 0)
    if green_clusters:
        best = max(green_clusters, key=lambda cl: (len(cl["members"]), -by_ms.get(cl["representative"], 0)))
    elif landed:
        best = max(landed, key=lambda cl: (len(cl["members"]), cl["passed"], -by_ms.get(cl["representative"], 0)))
    else:
        return {"index": None, "cluster_size": 0, "green_clusters": 0, "representatives": reps}
    return {"index": best["representative"], "cluster_size": len(best["members"]),
            "green_clusters": len(green_clusters), "representatives": reps}
