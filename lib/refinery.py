import pathlib
import json


def admit(records: list, task: str, workspace: str = "") -> dict:
    """C-2.1: admit an offer only when the last record for the task is green. With a
    workspace named, only the records written from that workspace count - a benchmark of
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


def merge_metrics(dispatches: list, merges: list) -> dict:
    """PURE (C-2.6): per executor - the distinct tasks that went green in the dispatch
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
    lines = ["# merge - per executor, from the merge record"]
    if not rep:
        lines.append("  (no merge recorded yet)")
    for ex, row in rep.items():
        refused = ", ".join(f"{k}={v}" for k, v in sorted(row["refused"].items())) or "none"
        lines.append(f"  {ex:12} green={row['green']}  merged={row['merged']}  refused: {refused}")
    return chr(10).join(lines)


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
    target is its ancestor - a compare-and-set on the ref, never a merge commit. When the
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

        # Get worktree list in simple format
        code, worktrees = run(["git", "worktree", "list"], workspace)
        if code == 0 and worktrees:
            from lib.refinery import checked_out_at
            checked = checked_out_at(worktrees, target)
            if checked:
                code, reset_out = run(["git", "-C", checked, "read-tree", "-m", "-u", old or head, head], checked)
                if code != 0:
                    # Failed to reset, move ref back with both old and new commits
                    argv_back = ["git", "update-ref", f"refs/heads/{target}", old, head]
                    code2, out2 = run(argv_back, workspace)
                    if code2 != 0:
                        return {"ok": False, "head": head, "old": old,
                                "reason": f"update-ref failed to move ref back: {out2.strip()[-200:] or 'unknown'}"}
                    return {"ok": False, "head": head, "old": old, "synced": checked,
                            "reason": f"failed to keep reset at {checked}: {reset_out and reset_out.strip()[-200:] or 'error'}; ref {checked} moved back"}
                else:
                    return {"ok": True, "head": head, "old": old, "reason": f"{target} -> {head[:12]}",
                            "synced": checked}	
        
        # No worktree checked out at target, proceed with update-ref
        pass

    # Move the ref
    argv = ["git", "update-ref", f"refs/heads/{target}", head] + ([old] if old else [])
    code, out = run(argv, workspace)
    if code != 0:
        return {"ok": False, "head": head, "old": old, "reason": f"update-ref failed: {out.strip()[-200:]}"}
    return {"ok": True, "head": head, "old": old, "reason": f"{target} {old[:12] or '(new)'} -> {head[:12]}",
            "synced": ""}


def checked_out_at(text: str, branch: str) -> str:
    """C-2.9: parse worktree list in simple format and find the worktree
    checked out at the given branch. Returns the path or empty string."""
    lines = (text or "").splitlines()
    # Simple format:
    # worktree <path>
    # HEAD <commit>
    # branch <ref>    or "detached"
    # blank or "------" or other worktree entry
    i = 0
    while i < len(lines):
        line = lines[i] if lines[i].strip() else ""
        parts = line.split()
        if not parts or parts[0] != "worktree":
            i += 1
            continue
        path = parts[1] if len(parts) > 1 else ""
        i += 1
        if i >= len(lines):
            continue
        head_line = lines[i] if lines[i].strip() else ""
        parts = head_line.split()
        i += 1
        if i >= len(lines):
            continue
        status_line = lines[i] if lines[i].strip() else ""
        status_parts = status_line.split()
        # Check for detached
        is_detached = False
        is_checked = False
        if status_parts and status_parts[0] == "detached":
            is_detached = True
        elif status_parts and status_parts[0] == "branch":
            branch_obj = status_parts[1] if len(status_parts) > 1 else ""
            # Compare with full refnorm or short name
            if branch_obj == branch or branch_obj.endswith(f"/{branch}"):
                is_checked = True
        if is_detached:
            i += 1
            continue
        elif is_checked:
            # Return just the path part from the worktree line
            return path.split()[0] if path.split() else ""
        # Not matched - finish this entry
        i += 1
    return ""


VERIFY_EXECUTOR = "verify"


def verify_verdict(changed_files: list, checks: list, *, spec_files=()) -> dict:
    """PURE (C-2.7): the verdict of a workspace against its target - landed when the diff
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


SEALED_DIR = "sealed"


def sealed_dirs(root: str) -> list:
    """EFFECTFUL (directory walk): every features/*/sealed directory, relative, sorted."""
    base = pathlib.Path(root) / "features"
    out = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            s = d / SEALED_DIR
            if s.is_dir():
                out.append(str(s.relative_to(root)).replace("\\", "/"))
    return out


def sealed_checks(dirs) -> list:
    """PURE: one pytest per sealed directory - what the refinery runs and nothing else does."""
    return [f"python -m pytest {d} -q" for d in dirs]


def sealed_touched(changed) -> list:
    """PURE: the changed paths that lie under a sealed directory."""
    return [p for p in changed if f"/{SEALED_DIR}/" in ("/" + str(p).replace("\\", "/"))]


# --- C-11.2: the mutation stage of the merge queue ------------------------------------------

STAGES = ("admit", "rebase", "check", "scan", "mutation", "policy", "fast-forward")   # C-3.3


def changed_lines_from_diff(diff_text: str) -> dict:
    """PURE (C-11.2): {path: [new-side line numbers added or changed]} out of a unified diff
    (`git diff --unified=0 target...HEAD`). Deleted-only hunks add nothing."""
    import re as _re
    out: dict = {}
    path = None
    for line in (diff_text or "").splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            path = None if name == "/dev/null" else (name[2:] if name.startswith("b/") else name)
            continue
        m = _re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            start = int(m.group(1)); count = int(m.group(2)) if m.group(2) is not None else 1
            if path and count > 0:
                out.setdefault(path, []).extend(range(start, start + count))
            continue
    return {k: sorted(set(v)) for k, v in out.items()}


def mutation_stage(changed: dict, clause_map: dict, results: list, *, threshold: float = 0.7) -> dict:
    """PURE (C-11.2): the stage's verdict — the changed lines mapped to the clauses that own them
    (lib.mutgate), the sweep's results scored per clause, refused on a survivor on an added line
    or a clause under the threshold there; `unowned` names changed lines no clause owns."""
    from lib.mutgate import changed_targets, clause_scores, mutation_verdict
    targets, unowned = changed_targets(changed or {}, clause_map or {})
    scores = clause_scores(list(results or []), targets)
    v = mutation_verdict(scores, threshold=threshold, added=changed or {})
    v["stage"] = "mutation"
    v["scores"] = scores
    v["unowned"] = unowned
    return v
