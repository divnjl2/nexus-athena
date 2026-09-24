"""The forge (C-7.5): benchmark tasks made from the frame itself, the SWE-smith way — break
the lines a clause owns, confirm the clause's spec went red, hand the repair to an executor
as a task whose verdict is that spec. The ground truth is the unbroken code; nobody has to
write it. One mutant is the atomic rung; several mutants across several files is the rung
past the envelope.

PURE throughout; the CLI applies the mutants in a worktree and runs the spec.
"""
from __future__ import annotations

import random

from lib.mutation import mutants


def exclusive_lines(clause_map: dict) -> dict:
    """{clause id: {path: [lines]}} restricted to lines exactly one clause owns and to
    Python files that are not tests — the lines whose break has one unambiguous spec."""
    clauses = (clause_map or {}).get("clauses") or {}
    count: dict = {}
    for files in clauses.values():
        for path, lines in files.items():
            for ln in lines:
                count[(path, ln)] = count.get((path, ln), 0) + 1
    out: dict = {}
    for cid, files in clauses.items():
        mine: dict = {}
        for path, lines in files.items():
            p = str(path).replace("\\", "/")
            if not p.endswith(".py") or "/tests/" in "/" + p or p.startswith("tests/"):
                continue
            keep = sorted(ln for ln in lines if count.get((path, ln)) == 1 and ln > 1)
            if keep:
                mine[p] = keep
        if mine:
            out[cid] = mine
    return out


def specs_by_clause(scenarios) -> dict:
    """{clause id: [(scenario id, run_cmd)]} for scenarios that run a pytest node."""
    out: dict = {}
    for s in scenarios:
        cmd = getattr(s, "run_cmd", "") or ""
        if "pytest" in cmd and "::" in cmd:
            out.setdefault(s.requirement_key, []).append((s.id, cmd))
    return out


def pick_targets(clause_map: dict, scenarios, sources: dict, *, n: int = 6, mutants_per_task: int = 1,
                 seed: int = 7, clause_prefix: str = "") -> list:
    """The forged tasks: each names a clause, its specs, and `mutants_per_task` mutants on
    lines it exclusively owns — across different files when the clause owns more than one.
    `sources` is {path: text} for the files the map names. Deterministic under `seed`."""
    rng = random.Random(seed)
    excl = exclusive_lines(clause_map)
    specs = specs_by_clause(scenarios)
    candidates = []
    for cid in sorted(excl):
        if clause_prefix and not cid.startswith(clause_prefix):
            continue
        if cid not in specs:
            continue
        per_file = {}
        for path, lines in excl[cid].items():
            text = sources.get(path)
            if text is None:
                continue
            ms = mutants(text, lines, path=path)
            if ms:
                per_file[path] = list(ms)
        if per_file:
            candidates.append((cid, per_file))
    rng.shuffle(candidates)
    tasks = []
    for k, (cid, per_file) in enumerate(candidates[:n], 1):
        paths = sorted(per_file)
        rng.shuffle(paths)
        chosen = []
        # one mutant per file first (the hard rung is across files), then more from the same
        for path in paths:
            if len(chosen) >= mutants_per_task:
                break
            chosen.append(rng.choice(per_file[path]))
        while len(chosen) < mutants_per_task and any(per_file.values()):
            path = rng.choice(paths)
            chosen.append(rng.choice(per_file[path]))
        tasks.append({"id": f"T9.{k}", "clause": cid, "specs": specs[cid],
                      "mutants": [{"path": m.path, "line": m.line, "kind": m.kind} for m in chosen],
                      "_mutants": chosen})
    return tasks


def apply_mutants(sources: dict, chosen) -> dict:
    """{path: mutated text}. Mutants carry whole sources computed against the ORIGINAL text,
    so several on one file are re-derived in sequence on the running text: the second break
    is applied to the first break's result, by line and kind."""
    out = dict(sources)
    for m in chosen:
        current = out.get(m.path, "")
        if current == sources.get(m.path):
            out[m.path] = m.source
            continue
        again = [x for x in mutants(current, [m.line], path=m.path) if x.kind == m.kind and x.line == m.line]
        if again:
            out[m.path] = again[0].source
    return out


def forged_plan(task: dict, contract_title: str = "Forge") -> str:
    """A plan.md holding one task: repair the clause whose spec is red. The task's files
    are the mutated ones; it verifies the clause's specs; its success check is the first."""
    files = sorted({m["path"] for m in task["mutants"]})
    verifies = ", ".join(sid for sid, _ in task["specs"])
    check = task["specs"][0][1]
    return (f"# Plan: {contract_title} forge\n\n## Overview\nRepair tasks forged from the clause map: the "
            f"clause's specs are red because lines it owns were broken.\n\n## Out of Scope\n- anything but the repair\n\n"
            f"## Phase 1: Repair\n**Goal:** the clause's specs are green again.\n**Depends on:** none\n### Tasks\n"
            f"- [ ] {task['id']} Repair {task['clause']}: its spec is red; find and fix the break in the named files\n"
            f"  - success_check: `{check}`\n  - files: `{', '.join(files)}`\n  - verifies: {verifies}\n")


def forge_table(records: list, tasks: list, executor: str) -> dict:
    """{task id: {clause, mutants, green_at, attempts}} from the dispatch record."""
    out = {}
    for t in tasks:
        rows = [r for r in records if r.get("task") == t["id"] and str(r.get("executor", "")).startswith(executor)]
        green = [r for r in rows if r.get("green")]
        out[t["id"]] = {"clause": t["clause"], "mutants": len(t["mutants"]),
                        "files": len({m["path"] for m in t["mutants"]}),
                        "attempts": len(rows),
                        "green_at": int(green[0].get("iteration") or 1) if green else None,
                        "seconds": sum(int(r.get("duration_ms", 0)) for r in rows) // 1000}
    return out


def render_forge(table: dict) -> str:
    lines = ["# forge — repair tasks from the clause map", "  task   clause   mutants files  result"]
    for tid, row in table.items():
        res = f"green@{row['green_at']}" if row["green_at"] else (f"red x{row['attempts']}" if row["attempts"] else "not run")
        lines.append(f"  {tid:6} {row['clause']:8} {row['mutants']:7} {row['files']:5}  {res}  {row['seconds']}s")
    return "\n".join(lines)
