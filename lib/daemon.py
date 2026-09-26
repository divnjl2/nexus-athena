"""C-3 — foundry daemon selects tasks and releases stale claims."""
from datetime import datetime
from collections import defaultdict

# Priority levels
READY = 100


def next_task(priority, slug, running):
    """C-3.1 — select the ready task of highest priority that no lane is running.
    
    Args:
        priority: list of {"id": task_id, "priority": level, "created_at": ts}
        slug: debugging slug to extract task IDs
        running: set of task_ids currently running (just the short form T1.1, etc.)
    
    Returns:
        task_id (short form like "T1.1") or "" if none
    
    Sorting order: priority ascending (lower number = higher level), then oldest created_at.
    """
    if not isinstance(priority, list) or len(priority) == 0:
        return ""
    
    # Filter matching tasks for this slug
    matching_tasks = [t for t in priority if f":{slug}:" in t["id"]]
    
    # Build set of running full-format IDs (tasks are like "athena:{slug}:{id}")
    running_ids = set()
    for tid in running:
        if ":" in tid:
            running_ids.add(tid)
        else:
            # Short form "T1.1" -> full form "athena:{slug}:T1.1"
            running_ids.add(f"athena:{slug}:{tid}")
    
    # Sort by: priority ascending (lower number wins), then created_at ascending
    def key(item):
        return (item["priority"], item["created_at"], item["id"])
    
    sorted_tasks = sorted(matching_tasks, key=key)
    
    # Filter out running candidates
    candidates = [t for t in sorted_tasks if t["id"] not in running_ids]
    
    if not candidates:
        return ""
    
    winner = candidates[0]["id"]
    return winner.rsplit(":", 1)[-1]


def worktree_name(task_id, packet_digest):
    """C-3.1 — name the worktree by task id and packet digest, stable across restarts.
    
    Args:
        task_id: short task id like "T1.1"
        packet_digest: hex string (40 chars for SHA256)
    
    Returns:
        worktree name string (e.g., "T1.1-aaaa...") max 24 chars
    """
    base = f"{task_id}-{packet_digest}"
    if len(base) > 24:
        digits = 24 - len(task_id) - 1
        base = f"{task_id}-{packet_digest[:digits]}"
    return base


def parse_ts(ts_str):
    """Parse ISO timestamp string to datetime."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def stale_claims(claims, now, lease_s):
    """C-3.2 — release claims older than the lease and count crashed attempts.
    
    Args:
        claims: dict of task_id -> {"heartbeat": ISO string, "pid": int, "attempts": int}
        now: current timestamp string
        lease_s: lease duration in seconds
    
    Returns:
        list of {"task": task_id, "pid": pid, "attempts": new_attempts, "reason": "..."}
    """
    now_dt = parse_ts(now)
    stale = []
    
    for task_id, claim in claims.items():
        heartbeat_dt = parse_ts(claim["heartbeat"])
        age_s = (now_dt - heartbeat_dt).total_seconds()
        
        if age_s > lease_s:
            new_attempts = claim["attempts"] + 1
            stale.append({
                "task": task_id,
                "pid": claim["pid"],
                "attempts": new_attempts,
                "reason": f"heartbeat {int(age_s)}s old, lease {lease_s}s"
            })
    
    return stale


def resume_plan(priority_map, records):
    """C-3.3 — on restart, offer tasks where last record is green, run others.
    
    Args:
        priority_map: dict of task_id -> worktree_name (for known tasks)
        records: list of {"task": task_id, "workspace": worktree_name, "green": bool}
    
    Returns:
        dict {"offer": [task_ids], "run": [task_ids]}
    """
    offer_list = []
    run_list = []
    
    if not isinstance(records, list):
        return {"offer": [], "run": []}
    
    grouped = defaultdict(list)
    for rec in records:
        grouped[rec["task"]].append(rec)
    
    for task_id, worktree_name in priority_map.items():
        task_records = grouped.get(task_id, [])
        if not task_records:
            run_list.append(task_id)
            continue
        
        # Get the last record for this worktree_name
        matching_records = [r for r in task_records if r["workspace"] == worktree_name]
        if not matching_records:
            run_list.append(task_id)
            continue
        
        last_records = matching_records[-1:]
        if last_records[0]["green"]:
            offer_list.append(task_id)
        else:
            run_list.append(task_id)
    
    return {"offer": offer_list, "run": run_list}


def ledger_line(tick, task, action, reason, ts):
    """C-3.4 — create a ledger line entry.
    
    Args:
        tick: int, current tick number
        task: str, task identifier
        action: str, action performed
        reason: str, reason for the action
        ts: ISO timestamp string
    
    Returns:
        dict with keys tick, task, action, reason, ts
    """
    return {
        "tick": tick,
        "task": task,
        "action": action,
        "reason": reason,
        "ts": ts
    }


def action_allowed(rows, task, now, cap_per_hour):
    """C-3.4 — check if another action is allowed within the cap per hour.
    
    Args:
        rows: list of ledger line entries (dicts with "ts" key)
        task: str, task identifier
        now: ISO timestamp string, current time
        cap_per_hour: max actions allowed for this task in the hour
    
    Returns:
        bool, True if action is allowed, False if cap is reached
    """
    if cap_per_hour <= 0:
        return True
    
    now_dt = parse_ts(now)
    
    recent_count = 0
    for row in rows:
        # Only count rows for the specified task
        if row.get("task", "") != task:
            continue
        ts_str = row.get("ts", "")
        if not ts_str:
            continue
        
        row_dt = parse_ts(ts_str)
        diff_s = (now_dt - row_dt).total_seconds()
        
        if 0 <= diff_s < 3600:  # Within the last hour
            recent_count += 1
    
    return recent_count < cap_per_hour