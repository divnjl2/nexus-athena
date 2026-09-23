"""
Athena dispatch — a work PACKET in, a VERDICT out; the executor's report is ignored (v3.12).

The deferred executor, closed by the frame (ADR-0006). The orchestrator writes clauses and
reads verdicts; whoever types the code — a local lane, an OpenHands run, Claude Code — gets
the same packet and is judged the same way:

  * the packet is DERIVED from the contract, the scenarios and the plan: for a task, the
    clauses its specs verify, the spec commands, the task's files (inlined when the
    executor has no Bash) and the done criterion stated as those commands (C-1.*);
  * the verdict is computed from a workspace snapshot before and after plus the spec
    commands run afterwards; the executor's claim is recorded and ignored (C-2.*). The
    local 27b lane returned `ok` with no diff twice before this rule existed;
  * every dispatch appends a record, and the per-executor landed and green rates decide
    whether local models suffice (C-4.*).

Freeze-line: PURE except `snapshot` (a directory walk, no process, no network). Running the
executor and the checks is the CLI's job.
"""
from __future__ import annotations

import json
import os
import pathlib

from lib.hooks import is_derived

SCHEMA = "athena.dispatch/1"
#: ~9k tokens: what a 30k-context worker can take with its own system prompt and output.
DEFAULT_BUDGET_CHARS = 36000
HAND_WRITTEN = ("contract.md", "scenarios.md", "CORE.md", "plan.md")
SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", ".athena",
                       ".beads", ".dolt", "thoughts", "_shakedown"})


class DispatchError(ValueError):
    """The packet cannot be built: an unknown task, a spec the scenarios do not hold."""


def _task(plan, task_id: str):
    for phase in plan.phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    raise DispatchError(f"plan has no task {task_id}")


def packet(contract, scenarios, plan, task_id: str, *, files: dict | None = None,
           budget_chars: int = DEFAULT_BUDGET_CHARS) -> dict:
    """PURE: the packet for one plan task (C-1.1, C-1.3, C-1.4). `files` is {path: text} the
    caller chose to inline (the task's files, read by the CLI)."""
    task = _task(plan, task_id)
    by_id = {s.id: s for s in scenarios}
    missing = [v for v in task.verifies if v not in by_id]
    if missing:
        raise DispatchError(f"task {task_id} verifies specs the scenarios do not hold: "
                            f"{', '.join(missing)}")
    specs = [by_id[v] for v in task.verifies]
    clauses: list[dict] = []
    seen: set[str] = set()
    for s in specs:
        cl = contract.by_id(s.requirement_key)
        if cl is None:
            raise DispatchError(f"spec {s.id} verifies {s.requirement_key}, which the contract "
                                f"does not hold")
        if cl.id not in seen:
            seen.add(cl.id)
            clauses.append({"id": cl.id, "text": cl.text, "status": cl.status})
    checks: list[str] = []
    for cmd in [s.run_cmd for s in specs] + [task.success_check]:
        if cmd and cmd not in checks:
            checks.append(cmd)
    spec_rows = [{"id": s.id, "clause": s.requirement_key, "run_cmd": s.run_cmd,
                  "case": getattr(s, "case", "")} for s in specs]
    task_row = {"id": task.id, "title": task.title, "files": list(task.files),
                "success_check": task.success_check}
    text = render_packet(task_row, clauses, spec_rows, checks, files or {})
    return {
        "schema": SCHEMA, "task": task_row, "clauses": clauses, "specs": spec_rows,
        "checks": checks, "files": dict(files or {}), "text": text,
        "chars": len(text), "budget_chars": budget_chars, "over_budget": len(text) > budget_chars,
    }


def render_packet(task: dict, clauses: list, specs: list, checks: list, files: dict) -> str:
    """PURE: the text an executor receives (C-1.2). The clauses are quoted whole; the done
    criterion is the commands; the executor is told its report does not count."""
    out = [f"# Task {task['id']} — {task['title']}", "",
           "## The requirement (numbered clauses; never edit contract.md or scenarios.md)"]
    for c in clauses:
        out.append(f"- **{c['id']}** — {c['text']}")
    out += ["", "## The specs that must go green (each is an executable command)"]
    for s in specs:
        how = f"case `{s['case']}`" if s.get("case") else f"`{s['run_cmd']}`"
        out.append(f"- {s['id']} verifies {s['clause']}: {how}")
    if task.get("files"):
        out += ["", "## Files this task may touch", *[f"- {f}" for f in task["files"]]]
    out += ["", "## Done means",
            "Done is decided by the orchestrator from the workspace diff and by running these "
            "commands after you finish; your own report of success does not count:"]
    out += [f"    {c}" for c in checks]
    out += ["", "Rules: change only the files this task names; do not touch spec_ledger.json, "
            "clause_map.json or any contract; a requirement that seems wrong is reported, not "
            "edited. When the edits are applied, answer with one line: DONE."]
    if files:
        out += ["", "## Files, already read for you (do not Read them again)"]
        for path, text in files.items():
            out += [f"=== {path} ===", text.rstrip("\n"), f"=== end of {path} ==="]
    return "\n".join(out) + "\n"


def snapshot(root) -> dict:
    """EFFECTFUL (directory walk): {relative path: (mtime_ns, size)} outside the skipped dirs."""
    root = pathlib.Path(root)
    out: dict = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = pathlib.Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            out[str(p.relative_to(root)).replace("\\", "/")] = (st.st_mtime_ns, st.st_size)
    return out


def verdict(before: dict, after: dict, checks: list, *, claim: str = "") -> dict:
    """PURE: the decision (C-2.1..C-2.4). `checks` is [{cmd, exit, tail}] from the spec
    commands run AFTER the executor. The claim is kept for the record and ignored."""
    changed = sorted(p for p, sig in after.items() if before.get(p) != sig)
    deleted = sorted(p for p in before if p not in after)
    touched = changed + deleted
    landed = bool(touched)
    red = [c for c in checks if c.get("exit", 1) != 0]
    green = bool(checks) and not red
    flags = [p for p in touched
             if is_derived(p) or p.rsplit("/", 1)[-1] in HAND_WRITTEN or "/docs/adr/" in f"/{p}"]
    reasons: list[str] = []
    if not landed:
        reasons.append("no file changed: the executor's answer is a claim, not an edit")
    if not checks:
        reasons.append("no check was run: silence is not proof")
    for c in red:
        reasons.append(f"{c.get('cmd')} exit {c.get('exit')}: {str(c.get('tail', ''))[-300:]}")
    if flags:
        reasons.append("touched a derived or hand-written file: " + ", ".join(flags))
    return {
        "landed": landed, "green": green, "passed": landed and green,
        "changed_files": changed, "deleted_files": deleted, "review_flags": flags,
        "red": [{"cmd": c.get("cmd"), "exit": c.get("exit")} for c in red],
        "claim": (claim or "")[:400], "reason": "; ".join(reasons),
    }


def record(task_id: str, executor: str, result: dict, *, duration_ms: int, tokens: dict | None,
           ts: str) -> dict:
    """PURE: one line of the dispatch record (C-4.1)."""
    return {"schema": SCHEMA, "ts": ts, "task": task_id, "executor": executor,
            "landed": bool(result.get("landed")), "green": bool(result.get("green")),
            "passed": bool(result.get("passed")), "duration_ms": int(duration_ms),
            "tokens": {k: int(v) for k, v in (tokens or {}).items() if isinstance(v, int)},
            "changed": len(result.get("changed_files", [])),
            "review_flags": list(result.get("review_flags", []))}


def parse_dispatches(text: str) -> tuple[list[dict], int]:
    """PURE: dispatch.jsonl -> (records, skipped)."""
    records, skipped = [], 0
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(rec, dict) or "executor" not in rec or "landed" not in rec:
            skipped += 1
            continue
        records.append(rec)
    return records, skipped


def dispatch_metrics(records: list) -> dict:
    """PURE: per executor — attempts, landed rate, green rate, mean duration (C-4.2)."""
    by: dict = {}
    for r in records:
        row = by.setdefault(r.get("executor", "?"), {"attempts": 0, "landed": 0, "green": 0,
                                                     "duration_ms": 0})
        row["attempts"] += 1
        row["landed"] += bool(r.get("landed"))
        row["green"] += bool(r.get("green"))
        row["duration_ms"] += int(r.get("duration_ms", 0))
    out = {}
    for name, row in sorted(by.items()):
        n = row["attempts"]
        out[name] = {"attempts": n, "landed": row["landed"], "green": row["green"],
                     "landed_rate": round(row["landed"] / n, 2) if n else 0.0,
                     "green_rate": round(row["green"] / n, 2) if n else 0.0,
                     "mean_duration_ms": round(row["duration_ms"] / n) if n else 0}
    return {"schema": SCHEMA, "by_executor": out, "attempts": len(records)}


def render_metrics(rep: dict) -> str:
    lines = ["# dispatch — per executor, from the record"]
    if not rep["by_executor"]:
        lines.append("  (no dispatch recorded yet)")
    for name, row in rep["by_executor"].items():
        lines.append(f"  {name:12} attempts={row['attempts']}  landed={row['landed_rate']}  "
                     f"green={row['green_rate']}  mean={row['mean_duration_ms']} ms")
    return "\n".join(lines)
