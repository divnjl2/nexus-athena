"""Series aggregation and drift detection for benchmark runs."""

from typing import Mapping, Tuple, List, Any, Optional
from datetime import datetime
import hashlib
import json


def cusum_drop(series: list, min_points: int = 6, *, k: float = 0.05, h: float = 0.6, ref_points: int = 5) -> dict | None:
    """PURE (C-4.2): a one-sided CUSUM over a pass-rate series. The reference is the mean of the first
    `ref_points`; each point adds its deficit below the reference minus the slack `k`, floored at zero;
    a drop is declared when the accumulation passes `h`, and its start is the point where the
    accumulation last left zero. Fewer than `min_points` points is no verdict. One bad night (a single
    deficit under h) is not a drop; a dip that recovers drains the accumulation; a level held low is."""
    xs = [float(x) for x in (series or [])]
    if len(xs) < max(2, int(min_points)):
        return None
    n_ref = max(1, min(int(ref_points), len(xs)))
    ref = sum(xs[:n_ref]) / n_ref
    s = 0.0
    start = None
    for i, x in enumerate(xs):
        deficit = ref - x - k
        s = max(0.0, s + deficit)
        if s == 0.0:
            start = None
        elif start is None:
            start = i
        if s > h:
            return {"start": int(start if start is not None else i), "level": round(x, 4), "ref": round(ref, 4), "cusum": round(s, 4)}
    return None


def drift_bead_command(slug: str, finding: dict) -> list:
    """Build the bd create command for a drift finding."""
    title_parts = [
        f"athena:{slug}:drift:",
        str(finding.get("executor", "")),
        str(finding.get("model", "")),
        str(finding.get("runtime", "")),
        str(finding.get("ref", "")),
        str(finding.get("level", "")),
        str(finding.get("start_ts", ""))
    ]
    title_str = " ".join(title_parts)
    # cmd is a flat list: ['bd', 'create', <title_string>]
    return ["bd", "create", title_str]


def drift_once(s: list, seen: set, slug: str) -> list:
    """Emit the bd command once for a new finding."""
    if len(s) != 1:
        raise ValueError(f"drift_once expects 1 finding, got {len(s)}")
    finding = s[0]
    key = (slug, finding.get("start", ""))
    if key in seen:
        return []  # already seen
    seen.add(key)
    title_parts = [
        f"athena:{slug}:drift:",
        str(finding.get("executor", "")),
        str(finding.get("model", "")),
        str(finding.get("runtime", "")),
        str(finding.get("ref", "")),
        str(finding.get("level", "")),
        str(finding.get("start_ts", ""))
    ]
    title_str = " ".join(title_parts)
    # Return a list containing just the single result
    return [["bd", "create", title_str]]


def set_digest(tasks: list, packets: list) -> str:
    """
    Compute a digest of the task set as a JSON string.
    Order-independent and serializable.
    
    Args:
        tasks: list of task names/ids
        packets: list of packet data
    
    Returns:
        JSON string representation of the sorted task/packet set
    """
    given_tasks = sorted(tasks)
    given_packets = sorted(packets)
    return json.dumps([given_tasks, given_packets])


def series_rows(table: Mapping[str, dict], prov: Mapping[str, dict], ts: str, set_digest: str) -> list:
    """
    Build one row per executor with timestamp, model, runtime, set digest, tasks, green, rate.
    
    Args:
        table: dict of executor_id -> {tasks: int, green: int}
        prov: dict of executor_id -> {model: str, runtime: str}
        ts: timestamp string
        set_digest: JSON string digest of the task set (order-independent)
    
    Returns:
        list of dicts with keys: executor, ts, model, runtime, set_digest, tasks, green, rate
    """
    rows = []
    # Process executors in sorted order for determinism
    for executor in sorted(table.keys()):
        executor_data = table[executor]
        executor_prov = prov.get(executor, {}) if isinstance(prov, dict) else {}
        
        rate = executor_data.get("green", 0) / max(executor_data.get("tasks", 1), 1)
        
        row = {
            "executor": executor,
            "ts": ts,
            "model": executor_prov.get("model", ""),
            "runtime": executor_prov.get("runtime", ""),
            "set_digest": set_digest,
            "tasks": executor_data.get("tasks", 0),
            "green": executor_data.get("green", 0),
            "rate": rate
        }
        rows.append(row)
    return rows


def series_verdicts(rows: list, min_points: int) -> dict:
    """
    Compute verdicts per executor based on pass rate trends.
    
    Args:
        rows: list of benchmark rows from series_rows
        min_points: minimum points before verdict is ready
    
    Returns:
        dict of executor -> {drop: bool or None, verdict: str, set_changes: list}
        
    Verdicts:
        - "ok": good performance reached minimum points
        - "drop": performance dropped while same set (drop flag is True, no set changes)
        - "set changed": digest changed (drop flag is None, verdict is "set changed")
        - "too few points": not enough data, drop flag is None
    """
    executors = set(r["executor"] for r in rows)
    result = {}
    
    for executor in executors:
        executor_rows = [r for r in rows if r["executor"] == executor]
        rates = [r["rate"] for r in executor_rows]
        set_changes = []
        prev_digest = None
        digests = [row["set_digest"] for row in executor_rows]
        
        for i, row in enumerate(executor_rows):
            digest = row["set_digest"]
            
            if prev_digest is not None and digest != prev_digest:
                set_changes.append({
                    "from": str(prev_digest) if hasattr(prev_digest, 'hex') else str(prev_digest),
                    "to": str(digest) if hasattr(digest, 'hex') else str(digest)
                })
            
            prev_digest = digest
        
        # Check for verdict
        if len(rates) < min_points:
            # Not enough points yet
            drop = None
            verdict = "too few points"
        elif len(set_changes) > 0:
            # There were set changes - verdict is "set changed"
            # Circular deps don't read as a drop: the new set is not a drop, it's a change
            drop = None
            verdict = "set changed"
        else:
            # Use cusum_drop to check if there's a drop
            drop_result = cusum_drop(rates, min_points)
            
            if drop_result is not None:
                # There's a drop
                drop = drop_result
                verdict = "drop"
            else:
                drop = None
                verdict = "ok"
        
        result[executor] = {
            "drop": drop,
            "verdict": verdict,
            "set_changes": set_changes
        }
    
    return result
