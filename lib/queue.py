import json


def ready_command(slug):
    """Command to prepare a slug's task list for readiness."""
    return ["bd", "ready", "--json"]


def pick_ready(bd_json, slug):
    """
    Pick the next ready task for a slug from bd.
    
    Selects the first task for the given slug from the task list,
    sorted by lowest priority number, then earliest created_at on tie.
    Tasks in this slug have ids like "athena:slug:task_id".
    
    Args:
        bd_json: JSON string containing the ready tasks list
        slug: The slug name to filter tasks for
        
    Returns:
        The task_id suffix (e.g., "T1.1") or empty string if none found
    """
    if not bd_json or not isinstance(bd_json, str):
        return ""
    try:
        data = json.loads(bd_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, list):
        return ""
    
    def get_typed_slug(tid):
        """Extract slug from id like 'athena:demo:T1.1' -> 'demo'"""
        if tid and ":" in tid:
            parts = tid.split(":")
            return parts[1] if len(parts) > 1 else ""
        return ""
    
    # Filter: tasks in this slug
    slug_tasks = [t for t in data if get_typed_slug(t.get("id")) == slug]
    if not slug_tasks:
        return ""
    
    # Sort by priority ascending, created_at ascending (string comparison)
    sorted_tasks = sorted(slug_tasks, key=lambda t: (t.get("priority", float('inf')), t.get("created_at", "")))
    first = sorted_tasks[0]
    task_id = first.get("id", "")
    if task_id:
        parts = task_id.split(":")
        return parts[-1] if len(parts) > 1 else ""  # Return the task suffix (e.g., "T1.1")
    return ""

def claim_command(slug, task_id):
    """Generate command to claim a task."""
    return ["bd", "update", f"athena:{slug}:{task_id}", "--claim"]
