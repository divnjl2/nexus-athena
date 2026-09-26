"""v3.16 the foundry — memory in the packet (C-7) and regeneration from the spec (C-8)."""

from typing import Optional, Sequence


def repo_map_for(index: dict, seeds: Optional[Sequence[str]] = None, budget_tokens: int = 1000) -> str:
    """C-7.1: Seed files first with all their signatures, then rest until budget."""
    if seeds is None:
        seeds = []
    seeds = list(seeds)
    
    items = []
    
    # Add seed files first with all their signatures
    for p in seeds:
        if p in index:
            items.append({"file": p, "sigs": list(index[p])})
    
    # Then add remaining files in sorted order
    sorted_keys = sorted(index.keys())
    for p in sorted_keys:
        if p not in seeds and p in index:
            items.append({"file": p, "sigs": list(index[p])})
    
    token_budget = budget_tokens * 4 + 40
    
    if not items:
        return "\n"
    
    # Collect all lines from all entries
    all_lines = []
    for entry in items:
        fl = entry["file"]
        sgs = entry["sigs"]
        all_lines.extend([fl] + sgs)
    
    full_text = "\n".join(all_lines)
    
    if len(full_text) <= token_budget:
        return full_text + "\n"
    else:
        # Truncate to fit within budget, using "...\n" as suffix
        content = full_text[:token_budget - 5]
        return content.rstrip() + "...\n"


def place_after_prefix(packet: str, insert_text: str, marker: Optional[str] = None) -> str:
    """Place insert_text after a marker in the packet."""
    if marker is None:
        marker = ""
    parts = packet.split("\n")
    m = next((i for i, p in enumerate(parts) if p.strip().lower() == marker.lower()), -1)
    if m < 0:
        return insert_text
    new_parts = insert_text.split("\n")
    result = []
    result.extend(parts[:m])
    result.extend(new_parts)
    if m < len(parts):
        result.extend(parts[m:])
    return "\n".join(result)


def lesson_from(verdict) -> Optional[dict]:
    if verdict.get("green", True):
        return None
    
    tail = verdict["checks"][0].get("tail", "")
    exit_code = verdict["checks"][0].get("exit", 0)
    
    # Determine failure type from tail and exit code
    if exit_code == 124 or (len(tail) == 0 and exit_code == 124):
        failure = "timeout"
    elif "ImportError" in tail:
        failure = "import"
    elif " SyntaxError" in tail or tail.startswith("SyntaxError"):
        failure = "syntax"
    elif "assert" in tail.lower() or "AssertionError" in tail:
        failure = "assertion"
    elif exit_code != 0:
        failure = "import"
    else:
        failure = "assertion"
    
    # Create a one-line rule from tail (strip newlines)
    rule = "" .join(tail.split("\\n"))
    
    return {
        "clause": verdict["clauses"][0] if verdict["clauses"] else "",
        "file": verdict["changed_files"][0] if verdict["changed_files"] else "",
        "verdict": verdict["id"],
        "failure": failure,
        "rule": rule
    }


def select_lessons(lessons, clause_ids=None, files=None, n=5, cap_chars=200):
    clause_ids = clause_ids or []
    files = files or []
    result = []
    for lesson in lessons:
        c = lesson.get("clause", "")
        f = lesson.get("file", "")
        rule = lesson.get("rule", "")
        if len(rule) > cap_chars:
            rule = rule[:cap_chars - 3] + "..."
        # Match if clause is in clause_ids OR file is in files
        if c in clause_ids or f in files:
            result.append({**lesson, "rule": rule})
            if len(result) >= n:
                break
    return result


def decay(lessons, green_rides=None, limit=10):
    green_rides = green_rides or {}
    return [l for l in lessons if green_rides.get(l.get("id", ""), 0) < limit]


def packet_with_memory(pk, repo_map="", lessons=None):
    """C-11.3 — the packet with a repository map and the selected lessons after the static
    prefix and before the requirement; nothing to add returns the packet itself. Review
    (Claude, 26.09): every other key of the packet is kept — the first version returned a
    dict of five keys and the dispatcher died on pk["checks"]."""
    lessons = list(lessons or [])
    if not (repo_map or "").strip() and not lessons:
        return pk
    text = pk["text"]
    parts = []
    if (repo_map or "").strip():
        parts.append("## Repository map" + chr(10) + repo_map.strip() + chr(10))
    if lessons:
        lines = ["## Lessons"]
        for les in lessons:
            lines.append(f"- {les.get('clause', '?')}: {str(les.get('rule', '')).strip()} ({les.get('file', '?')})")
        parts.append(chr(10).join(lines) + chr(10))
    insert = chr(10).join(parts)
    marker = "## The requirement"
    k = text.find(marker)
    new_text = (text[:k] + insert + chr(10) + text[k:]) if k >= 0 else (text.rstrip(chr(10)) + chr(10) + chr(10) + insert)
    out = dict(pk)
    out.update({"text": new_text, "chars": len(new_text), "map_chars": len((repo_map or "").strip()),
                "lesson_count": len(lessons)})
    return out
