import json

def admit(records: list, task: str, workspace: str = "") -> dict:
    """C-2.1: admit an offer only when the last record for the task is green. With a
    workspace named, only the records written from that workspace count — a benchmark of
    the same task on another executor elsewhere is not this offer's verdict."""
    ws = str(workspace).replace("\\", "/").rstrip("/") if workspace else ""
    mine = [r for r in records if r.get("task") == task
            and (not ws or not r.get("workspace") or str(r.get("workspace")).replace("\\", "/").rstrip("/") == ws)]
    if not mine:
        return {"ok": False, "reason": f"no record for task {task}" + (f" in {ws}" if ws else "")}
    last = mine[-1]
    if not last.get("green"):
        return {"ok": False, "reason": f"last record is not green for task {task}: "
                                       f"{last.get('executor', '?')} iteration {last.get('iteration', '?')}"}
    return {"ok": True, "reason": f"last record is green for task {task}: "
                                  f"{last.get('executor', '?')} iteration {last.get('iteration', '?')}"}


def first_failure(records: list[dict]) -> str:
    """C-2.3: over gate-shaped verdicts, empty when every contract holds,
    else the first failing contract and its first cause.

    Scans reports in order, skips any that passed, and returns a string
    like "features/b/contract.md: ledger has red specs" on the first failure,
    or "" when none fail."""
    for record in records:
        passed = record.get("report", {}).get("passed", True)
        if not passed:
            contract_path = record["contract"]
            cause = record["report"]["first_cause"]
            return f"{contract_path}: {cause}"

    return ""


# --- the record and the way back (C-2.5) -----------------------------------------------

MERGE_SCHEMA = "athena.merge/1"
TASK_KEY_PREFIX = "athena"


def merge_record(task: str, executor: str, stage: str, ok: bool, reason: str, *, ts: str) -> dict:
    """PURE: one line of the merge record (C-2.5): which task, typed by whom, ended at which
    stage, merged or refused, and why."""
    return {"schema": MERGE_SCHEMA, "ts": ts, "task": task, "executor": executor,
            "stage": stage, "ok": bool(ok), "reason": (reason or "")[:600]}


def parse_merges(text: str) -> list[dict]:
    """PURE: merge.jsonl -> records, in file order; a line that is not a JSON object is skipped."""
    out: list[dict] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def bd_return_command(slug: str, task: str, stage: str, reason: str) -> list:
    """PURE: the command that returns a refused task to the queue (C-2.5): reopen it and
    append the stage and the reason to its notes, so the next executor starts from the why."""
    key = f"{TASK_KEY_PREFIX}:{slug}:{task}"
    note = f"refinery refused at {stage}: {reason}"
    return ["bd", "update", key, "--status", "open", "--append-notes", note]


# --- what the refinery did with the green ones (C-2.6) ------------------------------------

def merge_metrics(dispatches: list, merges: list) -> dict:
    """PURE (C-2.6): per executor — the distinct tasks that went green in the dispatch
    record, how many of them the refinery merged, and the refusals by stage."""
    green_tasks: dict = {}
    for d in dispatches:
        if d.get("green"):
            green_tasks.setdefault(d.get("executor", "?"), set()).add(d.get("task"))
    rep: dict = {ex: {"green": len(tasks), "merged": 0, "refused": {}}
                 for ex, tasks in sorted(green_tasks.items())}
    for m in merges:
        ex = m.get("executor", "?")
        row = rep.setdefault(ex, {"green": 0, "merged": 0, "refused": {}})
        if m.get("ok"):
            row["merged"] += 1
        else:
            stage = str(m.get("stage") or "?")
            row["refused"][stage] = row["refused"].get(stage, 0) + 1
    return rep


def render_merge_metrics(rep: dict) -> str:
    lines = ["# merge — per executor, from the merge record"]
    if not rep:
        lines.append("  (no merge recorded yet)")
    for ex, row in rep.items():
        refused = ", ".join(f"{k}={v}" for k, v in sorted(row["refused"].items())) or "none"
        lines.append(f"  {ex:12} green={row['green']}  merged={row['merged']}  refused: {refused}")
    return chr(10).join(lines)


# --- rebase and fast-forward, through an injected runner (C-2.2, C-2.4) ------------------

def conflicts_from(output: str) -> list:
    """PURE: the paths git names in CONFLICT lines, in order, once each."""
    out: list = []
    for line in (output or "").splitlines():
        line = line.strip()
        if not line.startswith("CONFLICT"):
            continue
        _, _, detail = line.partition("): ")
        if not detail:
            continue
        if detail.startswith("Merge conflict in "):
            path = detail[len("Merge conflict in "):].strip()
        else:
            # "dir/b.py deleted in HEAD and modified in ..." / "a.txt added in ..."
            path = detail.split(" deleted in ", 1)[0].split(" added in ", 1)[0].split(" modified in ", 1)[0].strip()
        if path and path not in out:
            out.append(path)
    return out


def rebase(run, workspace: str, target: str) -> dict:
    """EFFECTFUL through `run` (C-2.2): rebase the workspace onto the target; a rebase that
    stops is aborted and the offer refused with the conflicting files named."""
    code, out = run(["git", "rebase", target], workspace)
    if code == 0:
        return {"ok": True, "conflicts": [], "reason": f"rebased onto {target}"}
    conflicts = conflicts_from(out)
    run(["git", "rebase", "--abort"], workspace)
    named = ", ".join(conflicts) if conflicts else out.strip()[-300:]
    return {"ok": False, "conflicts": conflicts,
            "reason": f"rebase onto {target} stopped, aborted; conflicts: {named}"}


def fast_forward(run, workspace: str, target: str) -> dict:
    """EFFECTFUL through `run` (C-2.4): move the target ref to the workspace head when the
    target is its ancestor — a compare-and-set on the ref, never a merge commit. When the
    target is checked out somewhere, that worktree's files stay where they were."""
    code, head = run(["git", "rev-parse", "HEAD"], workspace)
    head = head.strip()
    if code != 0 or not head:
        return {"ok": False, "head": "", "old": "", "reason": f"no head in {workspace}: {head[-200:]}"}
    code, old = run(["git", "rev-parse", "--verify", f"refs/heads/{target}"], workspace)
    old = old.strip() if code == 0 else ""
    if old:
        code, _ = run(["git", "merge-base", "--is-ancestor", old, head], workspace)
        if code != 0:
            return {"ok": False, "head": head, "old": old,
                    "reason": f"{target} cannot be fast-forwarded to {head[:12]}: it is not an ancestor "
                              f"(rebase first)"}
        if old == head:
            return {"ok": True, "head": head, "old": old, "reason": f"{target} already at {head[:12]}"}
    argv = ["git", "update-ref", f"refs/heads/{target}", head] + ([old] if old else [])
    code, out = run(argv, workspace)
    if code != 0:
        return {"ok": False, "head": head, "old": old, "reason": f"update-ref failed: {out.strip()[-200:]}"}
    return {"ok": True, "head": head, "old": old, "reason": f"{target} {old[:12] or '(new)'} -> {head[:12]}"}


# --- a verdict for a workspace nobody dispatched (C-2.7) ------------------------------------

VERIFY_EXECUTOR = "verify"


def verify_verdict(changed_files: list, checks: list, *, spec_files=()) -> dict:
    """PURE (C-2.7): the verdict of a workspace against its target — landed when the diff
    against the target is not empty, green when every check is green and no spec file is in
    the diff; the same reading dispatch gives an executor's run."""
    from lib.dispatch import skip_reason
    changed = [str(p).replace("\\", "/") for p in changed_files]
    spec_set = {str(s).replace("\\", "/") for s in spec_files}
    spec_touched = [p for p in changed if p in spec_set]
    red = [c for c in checks if c.get("exit", 1) != 0 or skip_reason(c)]
    landed = bool(changed)
    green = bool(checks) and not red and not spec_touched
    reasons = []
    if not landed:
        reasons.append("no difference against the target: nothing to merge")
    if not checks:
        reasons.append("no check was run: silence is not proof")
    for c in red:
        reasons.append(f"{c.get('cmd')} exit {c.get('exit')}: {skip_reason(c) or str(c.get('tail', ''))[-300:]}")
    if spec_touched:
        reasons.append("the spec's own test file differs from the target: " + ", ".join(spec_touched))
    return {"landed": landed, "green": green, "passed": landed and green, "changed_files": changed,
            "deleted_files": [], "review_flags": spec_touched,
            "red": [{"cmd": c.get("cmd"), "exit": c.get("exit")} for c in red],
            "reason": "; ".join(reasons)}
