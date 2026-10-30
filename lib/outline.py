"""
Athena outline — the artifacts explaining how the thing is built (v3.6).

An audit read this repo's artifacts with no access to the code and reconstructed what the
frame does — then said the honest part out loud: every sentence about HOW IT IS PUT TOGETHER
had to be inferred, because 143 clauses in a flat file answer "what is guaranteed" and never
"what are the parts". The usual fix is an architecture document, which is a claim nobody
re-derives and everybody outgrows.

The clause map records, per clause, which module lines its bound specs executed. Grouping
those observations helps navigate the implementation; execution reach does not establish
architecture, semantic correspondence, or completeness of the observed inputs.

Freeze-line: PURE. It folds three artifacts (contract, coverage report, clause map) into a
structure; reading them from disk is the CLI's job.
"""
from __future__ import annotations

#: How many modules to name per group. More than this and the block stops being a summary.
TOP_FILES = 4


def outline(contract, coverage_report: dict, clause_map: dict | None = None) -> dict:
    """PURE: contract + coverage + map -> a readable structure of the system.

    Per group: clause statuses, declared spec-binding counts, and observed execution reach.
    No execution ledger or semantic assessment is supplied to this function.
    """
    groups: dict = {}
    owners = (clause_map or {}).get("clauses") or {}
    half = (clause_map or {}).get("partial") or {}
    covered = set(coverage_report.get("covered", ()))
    uncovered = set(coverage_report.get("uncovered", ()))

    for c in contract.clauses:
        key = c.group or "(ungrouped)"
        g = groups.setdefault(key, {"clauses": 0, "live": 0, "superseded": 0, "draft": 0,
                                    "withdrawn": 0, "bound": 0, "unbound": [],
                                    "half_proved": set(), "files": {}})
        g["clauses"] += 1
        g[c.status if c.status in ("superseded", "draft", "withdrawn") else "live"] += 1
        if c.is_live and c.id in covered:
            g["bound"] += 1
        if c.id in uncovered:
            g["unbound"].append(c.id)
        for path, lines in (owners.get(c.id) or {}).items():
            g["files"].setdefault(path, set()).update(lines)
        # Depth, not size: lines this group owns whose other arm nothing ever took.
        # DISTINCT — two clauses of one group flagging the same line is one hole, not two.
        # Summing the per-clause counts printed "274 half-proved" for a group owning 290.
        for path, lns in (half.get(c.id) or {}).items():
            g["half_proved"].update((path, ln) for ln in lns)

    # Ranking by raw line count made lib/contract.py the "home" of every group, because every
    # spec executes the parser on its way to anything else. That is execution reach, not
    # purpose.
    #
    # Counting how many GROUPS touch a file was the second try and it over-corrected: it
    # called lib/contract.py shared for everyone, so C-1 (the parser) and C-7 (the wording
    # critique) — both of which genuinely live there — came out homeless, and the modules
    # they merely passed through were promoted in their place.
    #
    # Exclusivity is per LINE, which is the granularity the map already has. The lines only
    # this group owns are its own; a file where it owns no such line is one it visits.
    for g in groups.values():
        g["half_proved"] = len(g["half_proved"])

    owners_of: dict = {}
    for g in groups.values():
        for path, lines in g["files"].items():
            for ln in lines:
                owners_of[(path, ln)] = owners_of.get((path, ln), 0) + 1
    for g in groups.values():
        ranked = []
        for path, lines in g["files"].items():
            exclusive = sum(1 for ln in lines if owners_of[(path, ln)] == 1)
            ranked.append((path, len(lines), exclusive))
        ranked.sort(key=lambda r: (-r[2], -r[1], r[0]))
        # Truncate the two lists SEPARATELY: a group with five home modules would otherwise
        # push every shared one off the end, and read as if it touched nothing else.
        home = [r for r in ranked if r[2]][:TOP_FILES]
        visited = [r for r in ranked if not r[2]][:TOP_FILES]
        g["files"] = [{"path": p, "lines": n, "exclusive": e, "shared": not e}
                      for p, n, e in home + visited]

    return {"schema": "athena.outline/2", "title": contract.title,
            "limitations": [
                "bound counts live clauses with declared scenario bindings, not successful execution.",
                "home and shared rank observed execution reach; partial branch coverage counts executed lines with unobserved arms.",
                "Execution results, intent fidelity, check adequacy and code correspondence are not assessed by this outline.",
            ],
            "clauses": len(contract.clauses), "live": len(contract.live()),
            "groups": groups}


def render(o: dict) -> str:
    """PURE: the terminal view — one block per group, its home modules and its shared ones."""
    lines = [f"# {o['title']} — {o['clauses']} clauses, {o['live']} live", ""]
    lines.extend(o.get("limitations", ()))
    lines.append("")
    for name, g in o["groups"].items():
        head = f"{name}  ({g['live']} live"
        for extra in ("superseded", "draft", "withdrawn"):
            if g[extra]:
                head += f", {g[extra]} {extra}"
        head += f")  spec-bound {g['bound']}/{g['live']}"
        lines.append(head)
        if g["unbound"]:
            lines.append(f"    unbound: {', '.join(g['unbound'])}")
        if g.get("half_proved"):
            lines.append(f"    partial branch coverage: {g['half_proved']} executed lines "
                         f"have unobserved arms")
        home = [f for f in g["files"] if not f["shared"]]
        shared = [f for f in g["files"] if f["shared"]]
        if home:
            lines.append("    home: " + "  ".join(
                f"{f['path']} ({f['lines']} lines)" for f in home))
        if shared:
            lines.append("    shared: " + ", ".join(f["path"] for f in shared))
        if not g["files"]:
            lines.append("    home: (no map — run `athena contract map`)")
        lines.append("")
    return "\n".join(lines)
