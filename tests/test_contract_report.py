"""v3.3 the three questions — coverage / todo / drift.

Each test is the executable spec of one C-4.* clause in features/contract-layer/contract.md.
Pure inputs (contract x scenarios x ledger), pure outputs — no I/O anywhere.
"""
from __future__ import annotations

from lib.ast import Scenario
from lib.contract import parse as parse_contract
from lib.contract_report import coverage, drift, render, todo
from lib.spec_runner import SpecResult, make_ledger

CONTRACT = parse_contract("""# Contract: Demo

## C-1 — Core

- **C-1.1** — WHEN it starts THE SYSTEM SHALL do the first thing.
- **C-1.2** — WHEN it starts THE SYSTEM SHALL do the second thing.
- **C-1.3** *(draft)* — WHEN it starts THE SYSTEM SHALL maybe do a third thing.
- **C-1.4** *(superseded-by C-1.5)* — WHEN it stops THE SYSTEM SHALL log the old way.
- **C-1.5** — WHEN it stops THE SYSTEM SHALL log the new way.
- **C-1.6** *(withdrawn)* — THE SYSTEM SHALL play a sound.
""")


def _scen(sid, clause, *, cmd="pytest -q", pin=""):
    return Scenario(id=sid, requirement_key=clause, gwt_text="G/W/T", run_cmd=cmd,
                    clause_version=pin)


def _pin(cid):
    return CONTRACT.by_id(cid).version


def test_a_live_clause_with_no_spec_is_uncovered():
    """C-4.1 — the "which requirements have no executable spec" answer."""
    rep = coverage(CONTRACT, (_scen("S1", "C-1.1"),))
    assert rep["uncovered"] == ["C-1.2", "C-1.5"]
    assert rep["covered"] == ["C-1.1"]
    assert rep["live_clauses"] == 3          # C-1.1, C-1.2, C-1.5 (draft/superseded/withdrawn excluded)
    assert rep["passed"] is False


def test_a_spec_naming_an_unknown_or_withdrawn_clause_is_an_orphan():
    """C-4.2 — a rotted reference is surfaced, never silently ignored."""
    rep = coverage(CONTRACT, (_scen("S1", "C-9.9"), _scen("S2", "C-1.6")))
    assert rep["orphan_specs"] == [
        {"scenario": "S1", "clause": "C-9.9", "reason": "unknown_clause"},
        {"scenario": "S2", "clause": "C-1.6", "reason": "withdrawn_clause"},
    ]
    assert rep["passed"] is False


def test_a_spec_on_a_superseded_clause_is_redirected_and_does_not_credit_the_successor():
    """C-4.3 — the reference resolves forward, but the successor still needs its own proof."""
    rep = coverage(CONTRACT, (_scen("S1", "C-1.1"), _scen("S2", "C-1.2"),
                              _scen("S3", "C-1.4")))
    assert rep["redirected_specs"] == [{"scenario": "S3", "clause": "C-1.4", "now": ["C-1.5"]}]
    assert "C-1.5" in rep["uncovered"]        # NOT credited by the old spec
    assert "C-1.4" not in rep["covered"]      # superseded clauses are not owed a proof


def test_draft_clauses_are_exempt_from_coverage():
    """C-4.4 — `draft` is how a requirement is written down before it is owed a proof."""
    rep = coverage(CONTRACT, (_scen("S1", "C-1.1"), _scen("S2", "C-1.2"), _scen("S3", "C-1.5")))
    assert rep["uncovered"] == [] and rep["draft_uncovered"] == ["C-1.3"]
    assert rep["passed"] is True and rep["coverage_rate"] == 1.0


def test_todo_splits_live_clauses_into_unspecified_red_unrun_stale_done():
    """C-4.13 — the "what is left" answer, and a stale-proof clause counts as work."""
    scenarios = (_scen("S1", "C-1.1", pin=_pin("C-1.1")),
                 _scen("S2", "C-1.2", cmd="pytest -q -k two"),
                 _scen("S3", "C-1.5"))
    ledger = make_ledger((SpecResult("S1", "C-1.1", True, 0, 5, clause_version=_pin("C-1.1")),
                          SpecResult("S2", "C-1.2", False, 1, 7)),
                         contract=CONTRACT, ts="T")
    rep = todo(CONTRACT, scenarios, ledger)
    assert rep["counts"] == {"unspecified": 0, "red": 1, "unrun": 1, "stale": 0,
                             "done": 1, "draft": 1}
    assert rep["red"][0]["clause"] == "C-1.2"
    assert rep["red"][0]["run_cmds"] == ["pytest -q -k two"]
    assert rep["unrun"][0] == {"clause": "C-1.5", "specs": ["S3"]}
    assert rep["done"] == [{"clause": "C-1.1"}]
    assert rep["remaining"] == 2

    # the requirement moves under a passing spec: green, but no longer 'done'
    drifted = (_scen("S1", "C-1.1", pin="0" * 16),) + scenarios[1:]
    stale = todo(CONTRACT, drifted, ledger)
    assert stale["stale"] == [{"clause": "C-1.1", "text": CONTRACT.by_id("C-1.1").text,
                               "stale_specs": ["S1"]}]
    assert stale["counts"]["done"] == 0 and stale["remaining"] == 3

    # with no ledger at all, everything specified is simply 'unrun'
    none_run = todo(CONTRACT, scenarios)
    assert none_run["counts"]["unrun"] == 3 and none_run["counts"]["red"] == 0


def test_unspecified_clause_carries_its_text_so_an_agent_can_act():
    """C-4.6 — the todo entry is actionable without re-reading the contract."""
    rep = todo(CONTRACT, (_scen("S1", "C-1.1"),))
    ids = [e["clause"] for e in rep["unspecified"]]
    assert ids == ["C-1.2", "C-1.5"]
    assert rep["unspecified"][0]["text"].startswith("WHEN it starts")


def test_drift_flags_a_spec_pinned_to_an_older_clause_version():
    """C-4.7 — the requirement moved, the executable spec did not follow."""
    scenarios = (_scen("S1", "C-1.1", pin="0" * 16), _scen("S2", "C-1.2", pin=_pin("C-1.2")),
                 _scen("S3", "C-1.5", pin=_pin("C-1.5")))
    rep = drift(CONTRACT, scenarios)
    assert rep["spec_drift"] == [{"scenario": "S1", "clause": "C-1.1",
                                  "pinned": "0" * 16, "current": _pin("C-1.1")}]
    assert rep["in_sync"] is False
    assert rep["counts"]["missing_spec"] == 0 and rep["counts"]["extra_spec"] == 0


def test_drift_flags_a_green_earned_under_a_stale_clause_version():
    """C-4.8 — a passing spec can still be proving yesterday's requirement."""
    scenarios = (_scen("S1", "C-1.1", pin=_pin("C-1.1")), _scen("S2", "C-1.2", pin=_pin("C-1.2")),
                 _scen("S3", "C-1.5", pin=_pin("C-1.5")))
    ledger = make_ledger((SpecResult("S1", "C-1.1", True, 0, 5, clause_version="0" * 16),),
                         contract=CONTRACT, ts="T")
    rep = drift(CONTRACT, scenarios, ledger)
    assert rep["stale_proof"] == [{"scenario": "S1", "clause": "C-1.1",
                                   "proved_version": "0" * 16, "current": _pin("C-1.1")}]
    assert rep["in_sync"] is False


def test_unpinned_specs_are_instrumentation_not_divergence():
    """C-4.9 — a repo that never pinned must not look permanently broken."""
    scenarios = (_scen("S1", "C-1.1"), _scen("S2", "C-1.2"), _scen("S3", "C-1.5"))
    rep = drift(CONTRACT, scenarios)
    assert rep["counts"]["unpinned"] == 3
    assert rep["spec_drift"] == [] and rep["in_sync"] is True


def test_drift_reports_missing_and_extra_specs():
    """C-4.10 — "нет лишних и нет пропущенных" is one report, not two guesses."""
    rep = drift(CONTRACT, (_scen("S1", "C-1.1"), _scen("S9", "C-9.9")))
    assert rep["missing_spec"] == ["C-1.2", "C-1.5"]
    assert [o["clause"] for o in rep["extra_spec"]] == ["C-9.9"]
    assert rep["in_sync"] is False


def test_todo_lists_draft_clauses_as_backlog():
    """C-4.12 — a written-down-but-not-yet-owed requirement stays visible in the answer."""
    rep = todo(CONTRACT, (_scen("S1", "C-1.1"),))
    assert rep["draft"] == [{"clause": "C-1.3",
                             "text": CONTRACT.by_id("C-1.3").text}]
    assert rep["backlog"] == 1
    assert rep["counts"]["draft"] == 1
    # backlog is NOT live work: a "remaining == 0" gate must not trip on a draft
    assert "C-1.3" not in [e["clause"] for e in rep["unspecified"]]


def test_render_produces_a_readable_table_for_any_report():
    """C-4.11 — the same reports are consumable by a human, not only by JSON."""
    text = render(coverage(CONTRACT, (_scen("S1", "C-9.9"),)), title="coverage")
    assert "# coverage" in text and "uncovered" in text and "C-9.9" in text
    assert "passed: False" in text
