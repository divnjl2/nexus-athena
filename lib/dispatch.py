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


EXCERPT_FULL_UNDER = 6000


def spec_imports(spec_sources: dict, rel_path: str) -> list:
    """PURE (C-1.8): the names the task's specs import from the module at `rel_path`."""
    import re
    p = rel_path.replace("\\", "/")
    if not p.endswith(".py"):
        return []
    mod = p[:-3].replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    names: list = []
    pat = re.compile(r"^\s*from\s+" + re.escape(mod) + r"\s+import\s+\(?([^)\n]+)", re.M)
    for src in (spec_sources or {}).values():
        for m in pat.finditer(src or ""):
            for n in m.group(1).split(","):
                n = n.strip().split(" as ")[0].strip()
                if n and n not in names:
                    names.append(n)
    return names


def excerpt(module_text: str, names: list, *, full_under: int = EXCERPT_FULL_UNDER) -> str:
    """PURE (C-1.8): what of a module a small-window executor needs to see. A short module
    goes whole. A long one goes as its header (everything above the first definition), the
    definitions the specs import in full, the signatures of the rest with their bodies
    omitted, and the imported names the module does not define yet, said plainly. Measured:
    the whole of a 20k-char module in the packet was eleven attempts by two lanes without a
    green; the model read, summarised, asked what to do, or rewrote what was already there."""
    import ast
    text = module_text or ""
    if len(text) <= full_under or not names:
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    lines = text.splitlines()
    top = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if not top:
        return text
    first = min((n.decorator_list[0].lineno if n.decorator_list else n.lineno) for n in top) - 1
    out = lines[:first]
    defined: set = set()
    want = set(names)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
            end = node.end_lineno
            defined.add(node.name)
            if node.name in want:
                out += [""] + lines[start:end]
            else:
                sig_end = node.lineno - 1
                while sig_end < end - 1 and not lines[sig_end].rstrip().endswith(":"):
                    sig_end += 1
                out += [""] + lines[node.lineno - 1: sig_end + 1] + [
                    f"    ...  # body omitted ({end - sig_end - 1} lines), not this task's"]
        elif node.lineno - 1 >= first:
            out += [""] + lines[node.lineno - 1: node.end_lineno]
    missing = [n for n in names if n not in defined]
    if missing:
        out += ["", f"# NOT DEFINED YET — the specs import {', '.join(missing)} from this module: "
                    "define them here."]
    return "\n".join(out) + "\n"


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
    # C-1.8: a long module goes in as what the task needs of it, not whole
    shown = {p: excerpt(t, spec_imports(spec_sources or {}, p)) for p, t in (files or {}).items()}
    excerpted = sorted(p for p, t in shown.items() if t != (files or {})[p])
    text = render_packet(task_row, clauses, spec_rows, checks, shown, root=root)
    return {
        "schema": SCHEMA, "task": task_row, "clauses": clauses, "specs": spec_rows,
        "checks": checks, "files": dict(files or {}), "excerpted": excerpted, "text": text,
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


def packet_with_status(pk: dict, checks: list, *, output_tokens: int = 0) -> dict:
    """PURE: the packet plus the CURRENT verdict of each spec command, taken before the
    executor starts (C-1.6). A red spec with its tail is what tells an executor the task is
    not done yet; without it a model looked at a complete-looking file and called finish."""
    rows = []
    for c in checks:
        ok = c.get("exit", 1) == 0
        tail = (c.get("tail") or "").strip()
        line = f"- {'green' if ok else 'RED'}: `{c.get('cmd')}`"
        if not ok and tail:
            line += "\n  " + tail[-400:].replace("\n", "\n  ")
        rows.append(line)
    red = sum(1 for c in checks if c.get("exit", 1) != 0)
    head = (f"## Current state of the specs, before you start ({red} red of {len(checks)})\n"
            "A RED spec below is the work: the task is not done until it is green. Do not answer "
            "that the code is already complete while any of these is RED.\n")
    text = pk["text"].rstrip("\n") + "\n\n" + head + "\n".join(rows) + "\n"
    text += "\n" + closing_order(pk.get("task") or {}, red=red, output_tokens=output_tokens)
    return {**pk, "text": text, "chars": len(text), "over_budget": len(text) > pk["budget_chars"],
            "status": {"red": red, "total": len(checks)}}


def closing_order(task: dict, *, red: int = 1, output_tokens: int = 0) -> str:
    """PURE: the last lines of a packet (C-1.7). After 270 inlined lines a 27B answered
    "Would you like me to continue reading the file?" — the end of the window is what the
    model takes to be its situation, so the end is the order: edit this file now, nobody is
    here to ask."""
    files = list(task.get("files") or [])
    first = files[0] if files else "the file this task names"
    lines = ["## Now act",
             "There is no user in this conversation and no question will be answered. "
             f"Your first action is an Edit or Write call on `{first}`"
             + (f" (the task's files: {', '.join(files)})" if len(files) > 1 else "") + ".",
             "Do not summarise the files above, do not offer options, do not ask how to proceed."]
    if output_tokens:
        # the model thinks before it acts and the thinking is billed to the same cap; a
        # budget it is not told about is a cliff it walks off (measured: three iterations
        # cut mid-Edit at 1024). Tell it, and ask for a short think per turn.
        lines.append(f"Your output per turn is capped at {int(output_tokens)} tokens and your "
                     "thinking counts against it; a turn that thinks past the cap lands nothing. "
                     "Think briefly, then call the tool.")
    if red:
        lines.append(f"{red} spec{'s are' if red != 1 else ' is'} RED above: make the edit that "
                     "turns them green, then answer with one line: DONE.")
    else:
        lines.append("Every spec above is green: answer with one line: DONE.")
    return "\n".join(lines) + "\n"


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


def pytest_outcome(tail: str) -> dict:
    """PURE (C-1.1): the counts pytest prints in its last line — passed, failed, skipped,
    errors — from a check's output tail; zeros when the tail is not pytest's. "seen" says
    whether any pytest count was there at all."""
    import re
    out = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "seen": False}
    text = tail or ""
    for m in re.finditer(r"(\d+)\s+(passed|failed|skipped|errors?)\b", text):
        key = m.group(2)
        key = "errors" if key.startswith("error") else key
        out[key] += int(m.group(1))
        out["seen"] = True
    if re.search(r"\bno tests ran\b", text):
        out["seen"] = True
    return out


def skip_reason(check: dict) -> str:
    """PURE (C-1.1): why an exit-zero check is red anyway, or "" when it is green. A skipped
    test, or a pytest run with nothing passed, is not proof."""
    if check.get("exit", 1) != 0:
        return ""
    o = pytest_outcome(str(check.get("tail", "")))
    if not o["seen"]:
        return ""
    if o["skipped"]:
        return f"{o['skipped']} skipped: a skipped test is not proof"
    if o["passed"] == 0:
        return "no test passed: nothing ran is not proof"
    return ""


def verdict(before: dict, after: dict, checks: list, *, claim: str = "",
            spec_files=()) -> dict:
    """PURE: the decision (C-2.1..C-2.4, C-2.7). `checks` is [{cmd, exit, tail}] from the
    spec commands run AFTER the executor. The claim is kept for the record and ignored.
    `spec_files` are the test modules the task's specs live in: a change there is not the
    task, it is the question being rewritten, and it cannot be green."""
    changed = sorted(p for p, sig in after.items() if before.get(p) != sig)
    deleted = sorted(p for p in before if p not in after)
    touched = changed + deleted
    landed = bool(touched)
    red = [c for c in checks if c.get("exit", 1) != 0 or skip_reason(c)]
    spec_set = {str(s).replace("\\", "/") for s in spec_files}
    spec_touched = [p for p in touched if p.replace("\\", "/") in spec_set]
    green = bool(checks) and not red and not spec_touched
    flags = [p for p in touched
             if is_derived(p) or p.rsplit("/", 1)[-1] in HAND_WRITTEN or "/docs/adr/" in f"/{p}"
             or p in spec_touched]
    reasons: list[str] = []
    if spec_touched:
        reasons.append("the spec's own test file was edited: " + ", ".join(spec_touched)
                       + " — a spec made to pass is not a requirement met")
    if not landed:
        reasons.append("no file changed: the executor's answer is a claim, not an edit")
    if not checks:
        reasons.append("no check was run: silence is not proof")
    for c in red:
        why = skip_reason(c)
        reasons.append(f"{c.get('cmd')} exit {c.get('exit')}: "
                       + (why if why else str(c.get('tail', ''))[-300:]))
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


def pick_winner(results: list) -> int | None:
    """PURE: which fanned attempt the iteration keeps (C-5.6, C-5.7). `results` are the
    attempts' verdicts in completion order. The first green wins. Short of green, the
    attempt that landed with the fewest red checks, the quicker one on a tie — the
    lower-overthinking trajectory, which the measured literature says to prefer. None when
    nothing landed: there is nothing to carry forward."""
    for i, r in enumerate(results):
        if r.get("green") and r.get("landed"):
            return i
    landed = [(len(r.get("red") or []), int(r.get("duration_ms") or 0), i)
              for i, r in enumerate(results) if r.get("landed")]
    if not landed:
        return None
    return min(landed)[2]


def retarget(text: str, base_root: str, copy_root: str) -> str:
    """PURE (C-5.6): the packet names the workspace root absolutely, so a fanned attempt must
    be told ITS copy — measured: three copies, three workers, every edit written into the
    base workspace the packet named, and three verdicts of "nothing landed"."""
    base = str(base_root).replace("\\", "/").rstrip("/")
    copy = str(copy_root).replace("\\", "/").rstrip("/")
    if not base or base == copy:
        return text
    out = text.replace(base, copy)
    win_base = base.replace("/", "\\")
    if win_base != base:
        out = out.replace(win_base, copy.replace("/", "\\"))
    return out


def fan_names(workspace: str, n: int) -> list:
    """PURE: the sibling paths the fanned attempts work in, one copy of the workspace each."""
    base = str(workspace).replace("\\", "/").rstrip("/")
    return [f"{base}-fan{k}" for k in range(1, max(1, int(n)) + 1)]


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
    """PURE: per executor — attempts, landed rate, green rate, mean duration (C-4.2); per
    task — attempts and the iteration at which it went green, None when it never did (C-4.4).

    The per-task half was dispatched to the local 27b lane (three iterations): it wrote the
    grouping correctly, forgot the render, and broke the per-executor mean on the way — a
    regression its own spec could not see, which is what C-2.6 now runs for.
    """
    by: dict = {}
    by_task: dict = {}
    for r in records:
        row = by.setdefault(r.get("executor", "?"), {"attempts": 0, "landed": 0, "green": 0,
                                                     "duration_ms": 0})
        row["attempts"] += 1
        row["landed"] += bool(r.get("landed"))
        row["green"] += bool(r.get("green"))
        row["duration_ms"] += int(r.get("duration_ms", 0))
        task_id = r.get("task")
        if task_id:
            t = by_task.setdefault(task_id, {"attempts": 0, "green_at": None, "passed": False})
            t["attempts"] += 1
            if r.get("green") and t["green_at"] is None:
                t["green_at"] = int(r.get("iteration") or t["attempts"])
                t["passed"] = True
    out = {}
    for name, row in sorted(by.items()):
        n = row["attempts"]
        out[name] = {"attempts": n, "landed": row["landed"], "green": row["green"],
                     "landed_rate": round(row["landed"] / n, 2) if n else 0.0,
                     "green_rate": round(row["green"] / n, 2) if n else 0.0,
                     "mean_duration_ms": round(row["duration_ms"] / n) if n else 0}
    return {"schema": SCHEMA, "by_executor": out,
            "by_task": {k: by_task[k] for k in sorted(by_task)}, "attempts": len(records)}


def render_metrics(rep: dict) -> str:
    lines = ["# dispatch — per executor, from the record"]
    if not rep["by_executor"]:
        lines.append("  (no dispatch recorded yet)")
    for name, row in rep["by_executor"].items():
        lines.append(f"  {name:12} attempts={row['attempts']}  landed={row['landed_rate']}  "
                     f"green={row['green_rate']}  mean={row['mean_duration_ms']} ms")
    if rep.get("by_task"):
        lines.append("# dispatch — per task")
        for task, row in rep["by_task"].items():
            state = (f"green at iteration {row['green_at']}" if row["passed"]
                     else f"not green after {row['attempts']}")
            lines.append(f"  {task:8} attempts={row['attempts']}  {state}")
    return "\n".join(lines)


def batch_radius(cmds: list) -> list:
    """PURE (C-2.6): the radius commands grouped into one pytest invocation per test module,
    each batch remembering its members. Measured: a one-line change to lib/__init__.py owned
    288 radius commands, and 288 pytest processes in a row took the verdict past an hour."""
    groups: dict = {}
    order: list = []
    singles: list = []
    for c in cmds:
        path, func = test_node(c)
        toks = (c or "").split()
        if path and func and toks[:3] == ["python", "-m", "pytest"]:
            node = next(t for t in toks if "::" in t)
            if path not in groups:
                order.append(path)
            groups.setdefault(path, []).append((c, node))
        else:
            singles.append(c)
    out = [{"cmd": "python -m pytest " + " ".join(n for _, n in groups[p]) + " -q",
            "members": [c for c, _ in groups[p]]} for p in order]
    out += [{"cmd": c, "members": [c]} for c in singles]
    return out


def radius_checks(changed_files, maps: dict, scenarios_by_label: dict, *, already=()) -> list:
    """PURE: the spec commands of every clause whose map owns lines in a changed file, across
    every contract that has a map (C-2.6) — the blast radius the pre-edit hook shows the
    agent, run by the verdict. `maps` and `scenarios_by_label` are keyed by contract label.
    Commands already in the task's own checks are not repeated."""
    from lib.hooks import owners_for
    out: list = []
    seen = set(already)
    for path in changed_files:
        owners = owners_for(path, maps)
        for label, rows in owners.items():
            wanted = {cid for cid, _ in rows}
            for s in scenarios_by_label.get(label, ()):
                if s.requirement_key in wanted and s.run_cmd not in seen:
                    seen.add(s.run_cmd)
                    out.append(s.run_cmd)
    return out
