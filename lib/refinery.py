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




__all__ = ["admit"]