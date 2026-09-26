"""C-3 — foundry daemon selects tasks and releases stale claims."""
from datetime import datetime

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
