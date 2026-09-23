"""v3.11 intake — a failure becomes a draft clause and a red spec in one step.

Each test is the executable spec of one C-3.* clause in features/team-layer/contract.md.
`lib.intake` is pure: it takes texts and returns texts; the CLI writes them.
"""
from __future__ import annotations

import json

from lib.cases import parse_case, run_case
from lib.contract import parse as parse_contract
from lib.contract_report import coverage, todo
from lib.docrefs import check as refs_check
from lib.docrefs import fingerprint
from lib.intake import intake
from lib.scenario_parser import parse as parse_scenarios

CONTRACT = """# Contract: Funnel

## C-1 — Answers

- **C-1.1** — WHEN a lead asks the price THE SYSTEM SHALL answer with the price list.
- **C-1.2** — WHEN a lead asks twice THE SYSTEM SHALL not repeat the greeting.
"""
SCENARIOS = """# Scenarios: Funnel

### S1.1 — price
- **verifies:** C-1.1
- **run_cmd:** `python -m pytest tests/test_funnel.py::test_price -q`
- **Given** a lead
- **When** it asks the price
- **Then** the price list is sent

### S1.2 — greeting
- **verifies:** C-1.2
- **run_cmd:** `python -m pytest tests/test_funnel.py::test_greet -q`
- **Given** a lead
- **When** it asks twice
- **Then** no second greeting
"""
TRACE = '{"turn": 7, "user": "а сколько стоит доставка", "bot": "Здравствуйте! Чем помочь?"}\n'
TEXT = "WHEN a lead asks about delivery THE SYSTEM SHALL answer with the delivery terms."


def _do(**kw):
    args = dict(group="C-1", source="incident", text=TEXT,
                trace=("traces/2026-09-23-turn7.json", fingerprint(TRACE)),
                case_path="cases/C-1.3.json")
    args.update(kw)
    return intake(CONTRACT, SCENARIOS, **args)


def test_intake_appends_a_draft_clause_with_source_and_fresh_id():
    """C-3.1 — the failure enters the contract as a numbered draft with its origin on it."""
    out = _do()
    contract = parse_contract(out["contract_text"])
    assert [c.id for c in contract.clauses] == ["C-1.1", "C-1.2", "C-1.3"]
    new = contract.by_id("C-1.3")
    assert out["clause_id"] == "C-1.3"
    assert new.status == "draft" and new.source == "incident" and new.text == TEXT


def test_intake_binds_a_spec_so_coverage_and_todo_see_it():
    """C-3.2 — a clause without a spec would be invisible to the reports; intake binds one
    so coverage counts it and todo lists it as backlog."""
    out = _do()
    contract = parse_contract(out["contract_text"])
    scenarios = parse_scenarios(out["scenarios_text"])
    assert [s.id for s in scenarios] == ["S1.1", "S1.2", "S1.3"]
    assert scenarios[2].requirement_key == "C-1.3" and scenarios[2].case == "cases/C-1.3.json"
    cov = coverage(contract, scenarios)
    assert cov["draft_uncovered"] == [] and cov["passed"]
    rep = todo(contract, scenarios, ledger=None)
    assert rep["backlog"] == 1 and [d["clause"] for d in rep["draft"]] == ["C-1.3"]
    for bucket in ("unspecified", "red", "unrun", "stale"):
        assert "C-1.3" not in [row["clause"] for row in rep[bucket]], bucket


def test_intake_cites_the_failure_record_with_its_fingerprint():
    """C-3.3 — the trace the clause came from is a citation that goes suspect when it moves."""
    out = _do()
    contract = parse_contract(out["contract_text"])
    ref = f"traces/2026-09-23-turn7.json@{fingerprint(TRACE)}"
    assert contract.by_id("C-1.3").refs == (ref,)
    rep = refs_check(contract, {"traces/2026-09-23-turn7.json": TRACE})
    assert rep["passed"] and rep["ok"][0]["clause"] == "C-1.3"


def test_intake_never_writes_an_active_clause():
    """C-3.4 — promotion is a human reading the wording and the red spec, never the intake."""
    for kw in ({}, {"run_cmd": "python -m pytest tests/test_funnel.py::test_delivery -q"}):
        out = _do(**kw)
        contract = parse_contract(out["contract_text"])
        assert contract.by_id("C-1.3").status == "draft"
        assert "C-1.3" not in [c.id for c in contract.live()]


def test_an_intake_skeleton_is_red_until_the_then_is_written():
    """C-3.5 — the failing spec exists before the fix, by construction."""
    out = _do()
    skeleton = json.loads(out["case_text"])
    assert skeleton["clause"] == "C-1.3"
    res = run_case(parse_case(skeleton))
    assert not res.passed and "pending" in res.message.lower()
    real = {**skeleton, "given": {"text": "# Contract: Y\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n"},
            "when": {"call": "lib.contract:parse", "args": ["$text"]},
            "then": [{"path": "clauses", "length": 1}]}
    assert run_case(parse_case(real)).passed
    out2 = _do(run_cmd="python -m pytest tests/test_funnel.py::test_delivery -q")
    assert out2["case_text"] is None and "test_delivery" in out2["scenarios_text"]
