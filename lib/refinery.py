import json

def admit(records: list[dict], task: str) -> dict:
    """C-2.1: admit an offer only when its last record for the task is green.

    Returns a dict with 'ok' and a 'reason' that includes 'green' if admitted,
    or 'not green'/'no record' if refused."""
    task_records = [r for r in records if r.get("task") == task]

    if not task_records:
        return {"ok": False, "reason": "no record"}

    last_record = task_records[-1]

    if not last_record.get("green"):
        return {"ok": False, "reason": "not green"}

    return {"ok": True, "reason": "green"}


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
