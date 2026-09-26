"""lib/drafts.py — Admission gate and EARS validator for clause drafts."""

import re


# ── C-2.2 helpers ──────────────────────────────────────────────────────────

def ears_shape(text: str) -> str | None:
    """Return the EARS shape of a clause draft, or None if it has none."""
    text = text.strip()

    # Detect trigger keywords that define the shape
    triggers: list[str] = []
    if re.search(r"\bWHEN\b", text, re.IGNORECASE):
        triggers.append("event")
    if re.search(r"\bWHILE\b", text, re.IGNORECASE):
        triggers.append("state")
    if re.search(r"\bWHERE\b", text, re.IGNORECASE):
        triggers.append("optional")
    if re.search(r"\bIF\b", text, re.IGNORECASE) and re.search(r"\bTHEN\b", text, re.IGNORECASE):
        triggers.append("unwanted")

    # Multiple triggers → complex
    if len(triggers) >= 2:
        return "complex"

    # No trigger words: check ubiquitous (THE SYSTEM SHALL …)
    if not triggers and re.search(r"THE SYSTEM SHALL", text, re.IGNORECASE):
        return "ubiquitous"

    # Single trigger → that shape
    if triggers:
        return triggers[0]

    # Neither trigger nor ubiquitous → no EARS shape
    return None


def validate_clause(text: str) -> tuple[str, ...]:
    """Validate a clause draft.

    Returns an empty tuple on success, or a tuple naming the defects otherwise:
      - ("no SHALL", "no EARS shape")        — zero SHALLs
      - ("more than one SHALL",)              — two or more SHALLs
      - ("no response after SHALL",)           — one SHALL but nothing follows it
    """
    defects: list[str] = []

    # Count SHALL occurrences
    shall_count = text.count("SHALL")
    if shall_count == 0:
        defects.extend(("no SHALL", "no EARS shape"))
        return tuple(defects)

    if shall_count > 1:
        return ("more than one SHALL",)

    # Exactly one SHALL — check EARS shape
    shape = ears_shape(text)
    if shape is None:
        defects.append("no EARS shape")
        return tuple(defects)

    # Check that there is a response after the SHALL keyword
    match = re.search(r"\bTHE SYSTEM SHALL", text, re.IGNORECASE)
    if match:
        after = text[match.end():]
        if not after.strip():
            return ("no response after SHALL",)

    return ()


# ── C-2.1 admission gate ───────────────────────────────────────────────────

def admit_draft(
    base_exit: int,
    head_exit: int,
    covered: dict[str, list[int]],
    owned: dict[str, list[int]],
) -> tuple[bool, str]:
    """Admit a test draft only when:

    1. It **fails at the base**   (base_exit == 1)
    2. It **passes at the head**  (head_exit == 0)
    3. It **covers at least one owned line**

    Otherwise return (False, reason).
    """
    reasons: list[str] = []

    if base_exit != 1:
        reasons.append("green at base")

    if head_exit != 0:
        reasons.append("red at head")

    # Check whether covered includes any line that the clause owns
    covers_owned = False
    for file_path, owned_lines in owned.items():
        if file_path in covered:
            covered_lines = covered[file_path]
            for ol in owned_lines:
                if ol in covered_lines:
                    covers_owned = True
                    break
            if covers_owned:
                break

    if not covers_owned:
        reasons.append("covers no owned line")

    if reasons:
        return (False, "; ".join(reasons))

    return (True, "admitted")


# ── C-2.3 acceptance per drafting model ────────────────────────────────────


def acceptance(events):
    """Compute acceptance statistics per drafting model.

    Keeps, per drafting model, the counts of drafted, admitted and accepted-
    without-edit, and renders the acceptance rates.

    Args:
        events: List of dicts with keys ``model``, ``admitted`` (bool), and
                ``accepted`` (bool).

    Returns:
        Dict keyed by model name with:
          drafted, admitted, accepted, admitted_rate, accepted_rate
    """
    table: dict[str, dict] = {}
    for event in events:
        model = event["model"]
        admitted = event["admitted"]
        accepted = event["accepted"]
        if model not in table:
            table[model] = {"drafted": 0, "admitted": 0, "accepted": 0}
        table[model]["drafted"] += 1
        if admitted:
            table[model]["admitted"] += 1
        if accepted:
            table[model]["accepted"] += 1

    for model in table:
        d = table[model]
        drafted = d["drafted"]
        table[model]["admitted_rate"] = d["admitted"] / drafted if drafted else 0.0
        table[model]["accepted_rate"] = d["accepted"] / drafted if drafted else 0.0

    return table


def render_acceptance(table):
    """Render acceptance statistics per drafting model as human-readable text.

    The rendered text names each model and both rates (admitted and accepted).
    """
    lines = []
    for model in sorted(table.keys()):
        stats = table[model]
        lines.append(
            f"{model}: drafted={stats['drafted']}, admitted={stats['admitted']}, "
            f"accepted={stats['accepted']}, admitted_rate={stats['admitted_rate']:.0%}, "
            f"accepted_rate={stats['accepted_rate']:.0%}"
        )
    return "\n".join(lines)
