"""
Athena hooks — what the harness tells the agent before an edit, and what it refuses (v3.11).

`athena contract owners <file:line>` answered "which clauses may I break by editing this",
but nothing told the agent at the moment it mattered. A PreToolUse hook on Edit/Write execs
`athena hook pre-edit`; the decision is computed here (ADR-0005):

  * the clauses of every contract whose map owns lines in the target file, as additional
    context (C-5.1) — the blast radius arrives with the edit, not in the review;
  * a DERIVED artifact (ledger, clause map, exported index) is refused with the command that
    rebuilds it (C-5.2); the bypass variable allows it and says so (C-5.3).

Freeze-line: PURE. Reading the maps and the payload is the CLI's job.
"""
from __future__ import annotations

from lib.gate import BYPASS_VAR

#: derived file name -> the command that rebuilds it. A derived artifact is never edited by
#: hand (CORE.md): a hand-patched ledger is a claim wearing the clothes of evidence.
DERIVED = {
    "spec_ledger.json": "athena spec run <scenarios.md> --contract <contract.md> -o <this file>",
    "clause_map.json": "athena contract map <contract.md> --source <pkg> -o <this file>",
    "clauses.needs.json": "athena contract export <contract.md> -o <this file>",
    "judge_decisions.json": "python evals/judge_local.py --out <this file>",
}


#: How many owning clauses the pre-edit context names per contract; the rest are counted.
MAX_OWNERS_SHOWN = 12


def _norm(path) -> str:
    return str(path).replace("\\", "/")


def is_derived(path) -> str:
    """PURE: the rebuild command when `path` is a derived artifact, else ""."""
    return DERIVED.get(_norm(path).rsplit("/", 1)[-1], "")


def owners_for(path, maps: dict) -> dict:
    """PURE: {contract label: [(clause id, owned lines)]} for the file at `path`, across every
    map given (C-5.1). Paths match on their repository-relative tail."""
    p = _norm(path)
    out: dict = {}
    for label, cmap in maps.items():
        rows = []
        for cid, files in (cmap.get("clauses") or {}).items():
            for f, lines in files.items():
                fn = _norm(f)
                if p == fn or p.endswith("/" + fn):
                    rows.append((cid, len(lines)))
        if rows:
            out[label] = sorted(rows)
    return out


def pre_edit_decision(path, maps: dict, *, bypassed: bool = False) -> dict | None:
    """PURE: the PreToolUse payload, or None when there is nothing to say (C-5.1..C-5.3)."""
    name = _norm(path).rsplit("/", 1)[-1]
    rebuild = is_derived(path)
    if rebuild and not bypassed:
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{name} is a DERIVED artifact and is never edited by hand (CORE.md). "
                f"Rebuild it instead: {rebuild}. Bypass with {BYPASS_VAR}=1 only on the "
                f"operator's word."),
        }}
    context: list[str] = []
    if rebuild and bypassed:
        context.append(f"bypassed: hand edit of derived {name} allowed by {BYPASS_VAR}; "
                       f"rebuild afterwards with: {rebuild}")
    owners = owners_for(path, maps)
    if owners:
        context.append("clauses whose owned lines this edit touches (athena contract owners):")
        for label, rows in owners.items():
            # C-5.7: the heaviest owners are named, the rest counted — forty-one ids in a
            # row is noise, not context
            shown = sorted(rows, key=lambda r: (-r[1], r[0]))[:MAX_OWNERS_SHOWN]
            line = ", ".join(f"{cid} ({n} lines)" for cid, n in shown)
            if len(rows) > MAX_OWNERS_SHOWN:
                line += f", +{len(rows) - MAX_OWNERS_SHOWN} more"
            context.append(f"  {label}: {line}")
        context.append("their specs must stay green; new behaviour needs a clause and a spec, "
                       "and a requirement that changes is superseded, never edited.")
    if not context:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "additionalContext": "\n".join(context),
    }}
