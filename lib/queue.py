import json

from lib.daemon import task_key_of


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
    slug_tasks = [t for t in data if task_key_of(t)[0] == slug]   # review: the key is a label in beads
    if not slug_tasks:
        return ""
    
    # Sort by priority ascending, created_at ascending (string comparison)
    sorted_tasks = sorted(slug_tasks, key=lambda t: (t.get("priority", float('inf')), t.get("created_at", "")))
    first = sorted_tasks[0]
    return task_key_of(first)[1]

def claim_command(slug, task_id):
    """Generate command to claim a task."""
    return ["bd", "update", f"athena:{slug}:{task_id}", "--claim"]
