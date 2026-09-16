"""
Athena gate — the three questions as the criterion of done, for every contract in reach (v3.10).

`check` answers about ONE contract. A repository has several, an agent session touches any
of them, and a Stop hook that judges only the first it finds is a gate with a hole. So the
gate scans, judges each contract with the cheap lane (committed ledger, no spec run, no clause
map) and folds the verdicts: one failing contract fails the gate, and the reason names it.

The decidable part lives here and is PURE, which is what makes it testable; the walk over the
tree, the check per contract and the nudge counter are the CLI's. The shell hook is a shim
that execs `athena gate --hook`.

Lessons this module already carries (each is a clause in features/core-layer/contract.md):

  * a contract is recognised by its CLAUSES, not its file name — the first cut fed
    commands/contract.md (a slash-command document) to the parser and died;
  * the gate script existed for a month and was registered nowhere — so the registration
    itself is a clause with a spec (C-5.1);
  * a gate that blocks forever gets disabled — two nudges per session, then it lets go
    and says so.
"""
from __future__ import annotations

import re

SCHEMA = "athena.gate/1"
BYPASS_VAR = "CONTRACT_CRITERION_BYPASS"
DEFAULT_NUDGES = 2

#: A clause bullet, the same grammar `lib.contract` parses. Fenced code is stripped first: a
#: document ABOUT contracts shows one in a code block, and a mention is not a contract.
_CLAUSE_BULLET = re.compile(r"^\s*-\s*\*\*[A-Z]{1,4}-?\d+(?:\.\d+)*\*\*", re.MULTILINE)
_FENCE = re.compile(r"```.*?```", re.DOTALL)

#: Directories the scan never enters: vendored code, scratch, and the tool's own mirrors.
SKIP_DIRS = frozenset({".git", "node_modules", ".athena", "vendor", "_shakedown", ".venv",
                       "venv", "__pycache__", ".beads", "thoughts"})


def is_contract(text: str) -> bool:
    """PURE: a requirement contract is recognised by its clause bullets (C-5.2)."""
    return bool(_CLAUSE_BULLET.search(_FENCE.sub("", text or "")))


def find_contracts(files: dict) -> tuple[str, ...]:
    """PURE: {path: text} -> the paths that are contracts, sorted. Walking is the CLI's job."""
    return tuple(sorted(p for p, t in files.items() if is_contract(t)))


def fold(verdicts, *, bypassed: bool = False, nudges_used: int = 0,
         max_nudges: int = DEFAULT_NUDGES) -> dict:
    """PURE: per-contract check reports -> one gate report (C-5.3, C-5.4, C-5.6, C-5.7).

    `verdicts` is an iterable of {"contract": path, "report": <lib.check report>, "error": str}.
    A contract whose check could not run is a FAILING contract, never a skipped one.
    """
    rows: list[dict] = []
    for v in verdicts:
        rep = v.get("report") or {}
        passed = bool(rep.get("passed"))
        if passed:
            verdict = "PASS"
        elif rep.get("incomplete") and not rep.get("failed"):
            verdict = "INCOMPLETE"
        else:
            verdict = "FAIL"
        rows.append({"contract": v["contract"], "passed": passed, "verdict": verdict,
                     "first_cause": rep.get("first_cause", ""),
                     "failed": list(rep.get("failed", [])),
                     "error": v.get("error", "")})
    failing = [r for r in rows if not r["passed"]]

    if bypassed:
        passed, reason = True, "bypassed"
    elif not rows:
        passed, reason = True, "no contract"
    elif failing and nudges_used >= max_nudges:
        passed, reason = True, "nudge budget spent"
    elif failing:
        passed, reason = False, "contract does not hold"
    else:
        passed, reason = True, "every contract holds"

    return {
        "schema": SCHEMA,
        "contracts": rows,
        "passed": passed,
        "reason": reason,
        "bypassed": bypassed,
        "failing": [r["contract"] for r in failing],
        "nudges_used": nudges_used,
        "max_nudges": max_nudges,
    }


def hook_decision(report: dict) -> dict | None:
    """PURE: the Stop-hook payload — a block whose reason names the contract and its first
    cause (C-5.5), or None when there is nothing to block."""
    if report["passed"]:
        return None
    failing = [r for r in report["contracts"] if not r["passed"]]
    first = failing[0]
    head = f"verdict: {first['verdict']}"
    if first["first_cause"]:
        head += f"  first cause: {first['first_cause']}"
    if first.get("error"):
        head += f"  ({first['error']})"
    lines = [f"The contract in {first['contract']} does not hold, so this work is not done.", head]
    if len(failing) > 1:
        lines.append("also failing: " + ", ".join(r["contract"] for r in failing[1:]))
    lines += [
        "",
        "The three questions are the criterion: `athena contract coverage` (which requirements "
        "have no spec), `todo` (what is left), `drift` (where requirement, spec and code parted). "
        "New behaviour needs a clause AND an executable spec; a wrong guess is superseded, never "
        f"edited. Bypass with {BYPASS_VAR}=1 only when the operator says so.",
    ]
    return {"decision": "block", "reason": "\n".join(lines)}


def render(report: dict) -> str:
    """PURE: one line per contract, then the gate's own verdict and why."""
    lines = []
    for r in report["contracts"]:
        tail = f"  first cause: {r['first_cause']}" if r["first_cause"] else ""
        if r.get("error"):
            tail += f"  ({r['error']})"
        lines.append(f"  {r['verdict']:10} {r['contract']}{tail}")
    if not report["contracts"]:
        lines.append("  (no contract under this directory)")
    lines.append(f"\ngate: {'PASS' if report['passed'] else 'FAIL'}  ({report['reason']})")
    return "\n".join(lines)
