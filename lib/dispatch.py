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
#: Never evidence of work: caches the checks themselves write, and the executors' own state.
SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", ".athena",
                       ".beads", ".dolt", "thoughts", "_shakedown", ".pytest_cache",
                       ".hypothesis", ".openhands", ".mypy_cache", ".ruff_cache"})


class DispatchError(ValueError):
    """The packet cannot be built: an unknown task, a spec the scenarios do not hold."""


def _task(plan, task_id: str):
    for phase in plan.phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    raise DispatchError(f"plan has no task {task_id}")


def test_node(run_cmd: str) -> tuple[str, str]:
    """PURE: (module path, function name) of the pytest node a run_cmd names, or ("", "")."""
    node = next((tok for tok in (run_cmd or "").split() if "::" in tok), "")
    if not node:
        return "", ""
    path, _, rest = node.partition("::")
    return path.replace("\\", "/"), rest.split("::")[-1].split("[")[0]


def test_source(module_text: str, func_name: str) -> str:
    """PURE: the source of one top-level test function out of its module, "" if absent.
    AST-based, so a decorator or a docstring never fools it (C-1.5)."""
    import ast
    try:
        tree = ast.parse(module_text)
    except SyntaxError:
        return ""
    lines = module_text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
            return "\n".join(lines[start:node.end_lineno])
    return ""


def packet(contract, scenarios, plan, task_id: str, *, files: dict | None = None,
           budget_chars: int = DEFAULT_BUDGET_CHARS, root: str = "",
           spec_sources: dict | None = None) -> dict:
    """PURE: the packet for one plan task (C-1.1, C-1.3, C-1.4). `files` is {path: text} the
    caller chose to inline (the task's files, read by the CLI). `root` is the absolute
    workspace path, named in the text: a local worker spent 31 Read calls on paths that did
    not exist because it guessed the root."""
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
                  "case": getattr(s, "case", ""),
                  "source": (spec_sources or {}).get(s.id, "")} for s in specs]
    task_row = {"id": task.id, "title": task.title, "files": list(task.files),
                "success_check": task.success_check}
    text = render_packet(task_row, clauses, spec_rows, checks, files or {}, root=root)
    return {
        "schema": SCHEMA, "task": task_row, "clauses": clauses, "specs": spec_rows,
        "checks": checks, "files": dict(files or {}), "text": text,
        "chars": len(text), "budget_chars": budget_chars, "over_budget": len(text) > budget_chars,
    }


def render_packet(task: dict, clauses: list, specs: list, checks: list, files: dict,
                  *, root: str = "") -> str:
    """PURE: the text an executor receives (C-1.2). The clauses are quoted whole; the done
    criterion is the commands; the executor is told its report does not count."""
    out = [f"# Task {task['id']} — {task['title']}", ""]
    if root:
        r = root.replace("\\", "/").rstrip("/")
        out += [f"Repository root, already your working directory: {r}",
                "Every path below is relative to it; use the absolute form with your tools "
                "and do not explore the tree — this task names its files.", ""]
    out.append("## The requirement (numbered clauses; never edit contract.md or scenarios.md)")
    for c in clauses:
        out.append(f"- **{c['id']}** — {c['text']}")
    out += ["", "## The specs that must go green (each is an executable command)"]
    for s in specs:
        how = f"case `{s['case']}`" if s.get("case") else f"`{s['run_cmd']}`"
        out.append(f"- {s['id']} verifies {s['clause']}: {how}")
    sources = [s for s in specs if s.get("source")]
    if sources:
        out += ["", "## The specs' own source (already read for you; do not Read the test files)"]
        for s in sources:
            out += [f"### {s['id']}", "```python", s["source"].rstrip("\n"), "```"]
    if task.get("files"):
        r = root.replace("\\", "/").rstrip("/") if root else ""
        out += ["", "## Files this task may touch",
                *[f"- {f}" + (f"  (absolute: {r}/{f})" if r else "") for f in task["files"]]]
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
    if unparsed_tool_call(claim):
        # C-2.5: the model answered the tool schema in a shape the server's parser did not
        # accept, so the call came back as prose and nothing ran. A known signature gets its name.
        reasons.append("tool-parser mismatch: the executor emitted a tool call as plain text "
                       "(the model's call format does not match the server's --tool-call-parser)")
    return {
        "landed": landed, "green": green, "passed": landed and green,
        "changed_files": changed, "deleted_files": deleted, "review_flags": flags,
        "red": [{"cmd": c.get("cmd"), "exit": c.get("exit")} for c in red],
        "red_full": [{"cmd": c.get("cmd"), "exit": c.get("exit"), "tail": str(c.get("tail", ""))[-300:]}
                     for c in red],
        "claim": (claim or "")[:400], "reason": "; ".join(reasons),
    }


_TOOL_AS_TEXT = ("<tool_call>", "<function=", '"function":', '"tool_calls":', "<|tool_call|>")


def unparsed_tool_call(claim: str) -> bool:
    """PURE: does the executor's final text look like a tool call nobody parsed (C-2.5)?"""
    text = (claim or "").strip()
    if not text:
        return False
    return any(marker in text for marker in _TOOL_AS_TEXT)


def record(task_id: str, executor: str, result: dict, *, duration_ms: int, tokens: dict | None,
           ts: str) -> dict:
    """PURE: one line of the dispatch record (C-4.1)."""
    return {"schema": SCHEMA, "ts": ts, "task": task_id, "executor": executor,
            "landed": bool(result.get("landed")), "green": bool(result.get("green")),
            "passed": bool(result.get("passed")), "duration_ms": int(duration_ms),
            "tokens": {k: int(v) for k, v in (tokens or {}).items() if isinstance(v, int)},
            "changed": len(result.get("changed_files", [])),
            "review_flags": list(result.get("review_flags", []))}


# --- iterations with checkpoints: a small window is enough (C-5.*) --------------------

TASK_KEY_PREFIX = "athena"


def checkpoint(task_id: str, iteration: int, result: dict, *, claim: str = "") -> dict:
    """PURE: what the next iteration needs to know (C-5.1): the files changed so far, the
    red commands with their tails, the executor's last words. Never the conversation."""
    return {
        "task": task_id, "iteration": int(iteration),
        "files": list(result.get("changed_files", [])) + [f"{p} (deleted)" for p in result.get("deleted_files", [])],
        "red": [{"cmd": r.get("cmd"), "exit": r.get("exit"), "tail": (r.get("tail") or "")[-300:]}
                for r in result.get("red_full", result.get("red", []))],
        "last_words": (claim or "").strip()[-400:],
        "passed": bool(result.get("passed")),
    }


def render_checkpoint(cp: dict) -> str:
    """PURE: the checkpoint as the section the next packet carries."""
    out = [f"## Checkpoint from iteration {cp['iteration']} (task {cp['task']})",
           "The workspace already holds the changes below; continue from this state, do not redo them."]
    out.append("Files changed so far: " + (", ".join(cp["files"]) if cp["files"] else "none"))
    if cp["red"]:
        out.append("Still red:")
        for r in cp["red"]:
            tail = f" -> {r['tail']}" if r.get("tail") else ""
            out.append(f"  - `{r['cmd']}` (exit {r.get('exit')}){tail}")
    else:
        out.append("Still red: nothing ran green yet")
    if cp["last_words"]:
        out.append(f"Last words of the previous attempt: {cp['last_words']}")
    return "\n".join(out) + "\n"


def packet_with_checkpoint(pk: dict, cp: dict) -> dict:
    """PURE: the packet for the next iteration (C-5.2): the same clauses, specs and files,
    plus the checkpoint section; nothing of the previous conversation, so the executor
    starts with a fresh context and the same window."""
    text = pk["text"].rstrip("\n") + "\n\n" + render_checkpoint(cp)
    return {**pk, "text": text, "chars": len(text), "over_budget": len(text) > pk["budget_chars"],
            "iteration": cp["iteration"] + 1}


def bd_checkpoint_command(slug: str, task_id: str, cp: dict) -> list:
    """PURE: append the checkpoint to the task's notes in the task graph (C-5.4)."""
    key = f"{TASK_KEY_PREFIX}:{slug}:{task_id}"
    return ["bd", "update", key, "--append-notes", render_checkpoint(cp).rstrip("\n")]


def run_iterations(pk: dict, attempt, *, budget: int = 1) -> dict:
    """PURE given `attempt`: the loop (C-5.3, C-5.5). `attempt(iteration, packet) -> (verdict,
    claim)`; the executor is started afresh by the caller inside `attempt`. Stops on the first
    green iteration; a spent budget keeps the last checkpoint and reports red."""
    checkpoints: list[dict] = []
    current = dict(pk)
    result: dict = {}
    for i in range(1, max(1, budget) + 1):
        result, claim = attempt(i, current)
        if result.get("passed"):
            return {"passed": True, "iterations": i, "checkpoints": checkpoints, "verdict": result,
                    "last_checkpoint": checkpoints[-1] if checkpoints else None}
        cp = checkpoint(pk["task"]["id"], i, result, claim=claim)
        checkpoints.append(cp)
        current = packet_with_checkpoint(pk, cp)
    return {"passed": False, "iterations": max(1, budget), "checkpoints": checkpoints,
            "verdict": result, "last_checkpoint": checkpoints[-1] if checkpoints else None}


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
