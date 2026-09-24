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