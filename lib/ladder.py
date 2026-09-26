"""Ladder module — pre-dispatch feature logging (C-5.1) and escalation/handoff logic (C-5.2)."""


def features(packet_chars=None, files=None, clauses=None, specs=None, clause_map=None, prior_attempts=None):
    """C-5.1 — return pre-dispatch features for a task dispatch.

    packet_tokens: derived from packet_chars (4 chars per token).
    files_owned: count of files in the *task's* files list.
    clause_count: count of clauses in the task's clauses list.
    spec_count: count of specs in the task's specs list.
    lines_owned: sum of line counts from clause_map for files owned by the task.
    prior_attempts: prior attempt count passed in.
    """
    if files is None:
        files = []
    if clauses is None:
        clauses = []
    if specs is None:
        specs = []
    if clause_map is None:
        clause_map = {}
    if prior_attempts is None:
        prior_attempts = 0

    # packet_tokens: 4 chars → 1 token
    packet_tokens = max(packet_chars // 4, 0) if packet_chars is not None else 0

    files_owned = len(files)
    clause_count = len(clauses)
    spec_count = len(specs)

    # lines_owned: sum line counts from clause_map["clauses"] for files owned by this task
    lines_owned = 0
    clauses_map = clause_map.get("clauses", {})
    for clause_entry in clauses_map.values():
        for owned_file in files:
            if owned_file in clause_entry:
                lines_owned += len(clause_entry[owned_file])

    return {
        "packet_tokens": packet_tokens,
        "files_owned": files_owned,
        "clause_count": clause_count,
        "spec_count": spec_count,
        "lines_owned": lines_owned,
        "prior_attempts": prior_attempts,
    }


def should_escalate(attempts, signals):
    """C-5.2 — decide whether a rung's attempt warrants escalation to the next rung.

    Returns (bool, reason_string).

    Escalation triggers (any matching):
      1. Two or more red attempts on the same rung.
      2. Turns past the p90 threshold (signals["turns"] > signals["p90_turns"]).
      3. Same tool call repeated (signals["repeated_calls"] >= 4).
      4. No write after the median turn (writes == 0 and turns > median_turn).

    A single red does NOT escalate by itself.
    A green attempt never escalates regardless of signals.
    """
    # If any attempt is green, no escalation.
    for attempt in attempts:
        if attempt.get("green", True):
            return (False, "")

    # Check for two reds on the same rung
    reds_by_rung = {}
    for attempt in attempts:
        is_red = not attempt.get("green", False)
        if is_red:
            rung = attempt.get("rung", "?")
            reds_by_rung.setdefault(rung, []).append(attempt)

    for rung, red_list in reds_by_rung.items():
        if len(red_list) >= 2:
            return (True, f"red twice on {rung}")

    signals = signals or {}

    # Check p90 threshold
    if "turns" in signals and "p90_turns" in signals:
        if signals["turns"] > signals["p90_turns"]:
            return (True, f"turns {signals['turns']} past p90 {signals['p90_turns']}")

    # Check repeated same tool call
    if "repeated_calls" in signals:
        if signals["repeated_calls"] >= 4:
            return (True, f"same tool call repeated {signals['repeated_calls']} times")

    # Check no write after median turn
    if "median_turn" in signals and "writes" in signals:
        if signals["writes"] == 0 and signals["turns"] > signals["median_turn"]:
            return (True, f"no write after turn {signals['median_turn']}")

    return (False, "")


def handoff(attempt, cap=2000):
    """C-5.2 — produce a capped handoff text carrying files touched, last test output, and notes.

    Parameters:
        attempt: dict with keys changed_files, red (list of {cmd, tail}), last_words, rung.
        cap: maximum length of the returned string.

    Returns a string containing all relevant handoff information, capped at ``cap``.
    """
    parts = []

    # Files touched
    changed_files = attempt.get("changed_files", [])
    if changed_files:
        parts.append("Files touched: " + ", ".join(changed_files))

    # Last test output (from red attempts)
    reds = attempt.get("red", [])
    if reds:
        for r in reds:
            cmd = r.get("cmd", "")
            tail = r.get("tail", "")
            parts.append(f"Last test output — cmd: {cmd} — tail: {tail}")

    # Notes / last words
    last_words = attempt.get("last_words", "")
    if last_words:
        parts.append(f"Notes / last words: {last_words}")

    # Rung identifier
    rung = attempt.get("rung", "")
    if rung:
        parts.append(f"Rung: {rung}")

    text = "\n".join(parts)

    if len(text) > cap:
        text = text[:cap]

    return text


def rung_table(records):
    """C-5.3 — build a per-(rung, clause class) table with attempts, greens,
    win rate, and GPU minutes per green attempt. GPU minutes per green is None
    when green == 0.

    Parameters:
        records: list of dicts with keys rung, cls, green, duration_ms.

    Returns:
        dict keyed by (rung, cls) with {"n": N, "green": G,
        "win_rate": G/N, "gpu_min_per_green": total_gpu_min / G (or None)}.
    """
    table = {}
    for rec_entry in records:
        rung = rec_entry["rung"]
        cls = rec_entry["cls"]
        green = rec_entry.get("green", False)
        duration_ms = rec_entry.get("duration_ms", 0)
        key = (rung, cls)
        if key not in table:
            table[key] = {"n": 0, "green": 0, "total_gpu_min": 0.0}
        table[key]["n"] += 1
        if green:
            table[key]["green"] += 1
        table[key]["total_gpu_min"] += duration_ms / 60000.0

    result = {}
    for key, vals in table.items():
        result[key] = {
            "n": vals["n"],
            "green": vals["green"],
            "win_rate": vals["green"] / vals["n"] if vals["n"] > 0 else 0.0,
            "gpu_min_per_green": (
                vals["total_gpu_min"] / vals["green"]
                if vals["green"] > 0
                else None
            ),
        }
    return result


def enabled_rungs(rung_table, ladder, floor=0.0):
    """C-5.3 — for each clause class, return the list of rungs still enabled
    (win rate >= floor). A rung whose win rate for a class is under the floor
    is disabled for that class only.

    Parameters:
        rung_table: dict from rung_table() keyed by (rung, cls).
        ladder: iterable of rung identifiers to consider.
        floor: minimum win rate threshold; rungs below it are disabled per class.

    Returns:
        dict keyed by clause class, value = list of enabled rung names.
    """
    # Extract unique clause classes from rung_table keys
    classes = {cls for (_, cls) in rung_table.keys()}

    result = {}
    for cls in classes:
        enabled = []
        for rung in ladder:
            key = (rung, cls)
            if key not in rung_table:
                enabled.append(rung)
            else:
                wr = rung_table[key]["win_rate"]
                if wr >= floor:
                    enabled.append(rung)
        result[cls] = enabled
    return result
