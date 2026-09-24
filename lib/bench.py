"""Bench module for planning and rendering execution matrices."""
from datetime import datetime
from statistics import mean


def plan_matrix(tasks, executors, base_path):
    """Plan runs of tasks across executors, each in its own workspace.

    Args:
        tasks: List of task identifiers
        executors: List of executor identifiers
        base_path: Base directory path

    Returns:
        List of run records with task, executor, and workspace
    """
    runs = []
    for executor in executors:
        for task in tasks:
            runs.append({
                "task": task,
                "executor": executor,
                "workspace": f"{base_path}-{executor}"
            })
    return runs


def matrix_table(records, tasks, executors):
    """Fold dispatch records into one table per (task, executor).

    Each (task, executor) cell contains:
        green_at: iteration at which it went green (None if never)
        attempts: total number of attempts
        landed: whether it landed (1 or 0)
        seconds: total duration in seconds
        input_tokens: sum of input tokens across all attempts
        output_tokens: sum of output tokens across all attempts

    Args:
        records: List of run records
        tasks: List of task identifiers to include
        executors: List of executor identifiers to include

    Returns:
        Dictionary: {task: {executor: {...} with stats}}
    """
    result = {
        task: {
            executor: {
                "green_at": None,
                "attempts": 0,
                "landed": 0,
                "seconds": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }
            for executor in executors
        }
        for task in tasks
    }

    # Sort records by task, then executor, then iteration
    sorted_records = sorted(records, key=lambda r: (r["task"], r["executor"], r.get("iteration", 0)))

    for record in sorted_records:
        task = record["task"]
        executor = record["executor"]
        iteration = record.get("iteration", 0)
        duration_ms = record.get("duration_ms", 0)
        tokens = record.get("tokens", {})
        green = record.get("green", False)
        landed = record.get("landed", False)

        if task not in result or executor not in result[task]:
            continue

        stats = result[task][executor]

        # Aggregate attempt counter
        stats["attempts"] += 1

        # Aggregate duration
        stats["seconds"] += int(duration_ms) / 1000

        # Aggregate tokens
        if "input_tokens" in tokens:
            stats["input_tokens"] += int(tokens["input_tokens"])
        if "output_tokens" in tokens:
            stats["output_tokens"] += int(tokens["output_tokens"])

        # Track green state - keep first green iteration as "green_at"
        if green:
            if stats["green_at"] is None or iteration < stats["green_at"]:
                stats["green_at"] = iteration

        # Track landed state - use last incidence
        if landed:
            stats["landed"] = 1
        else:
            stats["landed"] = 0

    return result


def render_matrix(table, tasks, executors):
    """Render matrix as text with task rows and executor columns.
    
    Args:
        table: Result from matrix_table()
        tasks: List of task identifiers
        executors: List of executor identifiers
    
    Returns:
        Text representation of the matrix
    """
    lines = []
    
    # Header line with executor names
    lines.append("Executors: " + " | ".join(executors))
    lines.append("=" * len(executors))
    
    # For each task, show a row with its data by executor
    for task in tasks:
        task_row = [f"{task:5}"]
        
        for executor in executors:
            stats = table[task][executor]
            
            # Determine green status display
            status = "RAN"
            if stats["green_at"] is not None:
                status = f"green@{stats['green_at']}"
            elif stats["attempts"] == 0:
                status = "not run"
            
            # Duration
            duration = stats["seconds"]
            
            # Tokens
            in_t = stats["input_tokens"]
            out_t = stats["output_tokens"]
            
            if in_t == 0 and out_t == 0:
                tok_str = ""
            elif out_t > 0:
                tok_str = f"({in_t}/{out_t})"
            else:
                tok_str = f"({in_t}/0)"
            
            task_row.append(f"- {status} ({duration}s) {tok_str}")
        
        lines.append(" | ".join(task_row))
    
    return "\n".join(lines)
