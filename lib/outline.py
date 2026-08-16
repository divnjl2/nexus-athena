"""
Athena outline — the artifacts explaining how the thing is built (v3.6).

An audit read this repo's artifacts with no access to the code and reconstructed what the
frame does — then said the honest part out loud: every sentence about HOW IT IS PUT TOGETHER
had to be inferred, because 143 clauses in a flat file answer "what is guaranteed" and never
"what are the parts". The usual fix is an architecture document, which is a claim nobody
re-derives and everybody outgrows.

There is a better source. The clause map already knows, per clause, which lines of which
modules its spec actually executed. So the architecture is DERIVABLE: group the clauses, and
name the modules each group's specs really run. Nobody writes it down and it cannot go stale
against the code, because it is read out of the code's own execution.

Freeze-line: PURE. It folds three artifacts (contract, coverage report, clause map) into a
structure; reading them from disk is the CLI's job.
"""
from __future__ import annotations

#: How many modules to name per group. More than this and the block stops being a summary.
TOP_FILES = 4


def outline(contract, coverage_report: dict, clause_map: dict | None = None) -> dict:
    """PURE: contract + coverage + map -> a readable structure of the system.

    Per group: how many clauses, how they are split across the four statuses, how many are
    proved, and which modules the group's clauses own. That last column is the architecture,
    and it is measured rather than claimed.
    """
    groups: dict = {}
    owners = (clause_map or {}).get("clauses") or {}
    covered = set(coverage_report.get("covered", ()))
    uncovered = set(coverage_report.get("uncovered", ()))

    for c in contract.clauses:
        key = c.group or "(ungrouped)"
        g = groups.setdefault(key, {"clauses": 0, "live": 0, "superseded": 0, "draft": 0,
                                    "withdrawn": 0, "proved": 0, "unproved": [], "files": {}})
        g["clauses"] += 1
        g[c.status if c.status in ("superseded", "draft", "withdrawn") else "live"] += 1
        if c.id in covered:
            g["proved"] += 1
        if c.id in uncovered:
            g["unproved"].append(c.id)
        for path, lines in (owners.get(c.id) or {}).items():
            g["files"].setdefault(path, set()).update(lines)

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

    return {"schema": "athena.outline/1", "title": contract.title,
            "clauses": len(contract.clauses), "live": len(contract.live()),
            "groups": groups}


def render(o: dict) -> str:
    """PURE: the terminal view — one block per group, its home modules and its shared ones."""
    lines = [f"# {o['title']} — {o['clauses']} clauses, {o['live']} live", ""]
    for name, g in o["groups"].items():
        head = f"{name}  ({g['live']} live"
        for extra in ("superseded", "draft", "withdrawn"):
            if g[extra]:
                head += f", {g[extra]} {extra}"
        head += f")  proved {g['proved']}/{g['live']}"
        lines.append(head)
        if g["unproved"]:
            lines.append(f"    unproved: {', '.join(g['unproved'])}")
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
