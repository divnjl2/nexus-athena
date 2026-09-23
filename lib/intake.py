"""
Athena intake — a failure from the world becomes a draft clause and a red spec (v3.11).

`source: incident` was a word with no path behind it. This is the path (ADR-0004): a trace,
a log line or a failed run is handed in with the wording of the requirement it revealed,
and the contract gets a DRAFT clause with a fresh id from the allocator, the citation of
the trace by fingerprint, and a bound spec: the caller's run command, or a case skeleton
whose `then` is `pending`, which the runner keeps red until the assertion is written.

The clause is never written active (C-3.4): promotion is a human reading the wording and
the red spec. `coverage` sees the clause covered, `todo` lists it as backlog, `lessons`
picks it up the moment it goes active.

Freeze-line: PURE. Texts in, texts out; the CLI writes them.
"""
from __future__ import annotations

import json
import re

from lib.allocate import next_id
from lib.contract import parse as parse_contract
from lib.scenario_parser import parse as parse_scenarios

_SCEN_ID = re.compile(r"^S(\d+)\.(\d+)$")


def _short(text: str, n: int = 60) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _after_shall(text: str) -> str:
    _, _, tail = text.partition("SHALL")
    return tail.strip().rstrip(".") or text


def _insert_clause(contract_text: str, group: str, block: list[str]) -> str:
    lines = contract_text.splitlines()
    heading = re.compile(rf"^##\s+{re.escape(group)}(?:\s|$)")
    start = next((i for i, ln in enumerate(lines) if heading.match(ln)), None)
    if start is None:
        tail = ["", f"## {group} — Intake", ""] + block
        return "\n".join(lines + tail) + "\n"
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    new = lines[:end] + block + ([""] if end < len(lines) else []) + lines[end:]
    return "\n".join(new) + ("\n" if contract_text.endswith("\n") or end == len(lines) else "")


def intake(contract_text: str, scenarios_text: str, *, group: str, source: str, text: str,
           lane: int = 0, trace: tuple[str, str] | None = None, run_cmd: str = "",
           case_path: str = "") -> dict:
    """PURE: append a draft clause + a bound spec (+ a case skeleton) for one failure.

    Returns {contract_text, scenarios_text, clause_id, spec_id, case_path, case_text}.
    `trace` is (path relative to the contract, fingerprint) — the citation that goes
    suspect when the trace moves.
    """
    contract = parse_contract(contract_text)
    clause_id = next_id(contract, group, lane)

    block = [f"- **{clause_id}** *(draft)* — {text.strip()}", f"  - source: {source}"]
    if trace:
        path, pin = trace
        block.append(f"  - see: {path}@{pin}" if pin else f"  - see: {path}")
    new_contract = _insert_clause(contract_text, group, block)

    group_no = group.rsplit("-", 1)[-1].split(".")[0]
    existing = []
    try:
        for s in parse_scenarios(scenarios_text):
            m = _SCEN_ID.match(s.id)
            if m and m.group(1) == group_no:
                existing.append(int(m.group(2)))
    except Exception:                    # noqa: BLE001 — an empty scenarios file is legal here
        existing = []
    spec_id = f"S{group_no}.{(max(existing) + 1) if existing else 1}"

    case_text = None
    if not run_cmd:
        case_path = case_path or f"cases/{clause_id}.json"
        skeleton = {
            "clause": clause_id,
            "given": {"trace": trace[0] if trace else ""},
            "when": {"call": "builtins:str", "args": ["$trace"]},
            "then": [{"pending": f"write the check for {clause_id} from the trace"}],
        }
        case_text = json.dumps(skeleton, ensure_ascii=False, indent=2) + "\n"

    where = f"the failure recorded in {trace[0]}" if trace else "the reported failure"
    spec_block = [
        "", f"### {spec_id} — intake: {_short(text)}",
        f"- **verifies:** {clause_id}",
        (f"- **run_cmd:** `{run_cmd}`" if run_cmd else f"- **case:** `{case_path}`"),
        f"- **Given** {where}",
        f"- **When** the behaviour named by {clause_id} is exercised",
        f"- **Then** {_after_shall(text)}.",
    ]
    new_scenarios = scenarios_text.rstrip("\n") + "\n" + "\n".join(spec_block) + "\n"

    return {"contract_text": new_contract, "scenarios_text": new_scenarios,
            "clause_id": clause_id, "spec_id": spec_id,
            "case_path": case_path if not run_cmd else "", "case_text": case_text}
