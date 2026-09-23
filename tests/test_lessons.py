"""v3.10 lessons — a clause born from a failure signal, learned only while its proof passes.

Each test is the executable spec of one C-3.* clause in features/core-layer/contract.md.
"""
from __future__ import annotations

from lib.ast import Scenario
from lib.contract import parse
from lib.lessons import FAILURE_SOURCES, lessons, report, specs_for
from lib.spec_runner import SpecResult

TEXT = """# Contract: Lessons

## C-1 — Lessons

- **C-1.1** — WHEN a spec hangs THE SYSTEM SHALL record it as red.
  - source: incident
- **C-1.2** *(superseded-by C-1.3 C-1.4)* — WHEN the suite runs THE SYSTEM SHALL finish in five seconds.
  - source: ledger
- **C-1.3** *(supersedes C-1.2)* — WHEN the suite runs THE SYSTEM SHALL size the pool from the cores.
- **C-1.4** *(supersedes C-1.2)* — WHEN the suite runs THE SYSTEM SHALL let the caller pin the environment.
- **C-1.5** — WHEN a clause is drafted THE SYSTEM SHALL keep it out of coverage.
  - source: design
- **C-1.6** *(withdrawn)* — WHEN the sun sets THE SYSTEM SHALL play a sound.
  - source: review
- **C-1.7** — WHEN a mirror is dirty THE SYSTEM SHALL refuse to delete it.
  - source: audit
"""


def _s(sid, clause):
    return Scenario(id=sid, requirement_key=clause, gwt_text="g",
                    run_cmd=f"python -m pytest t.py::{sid} -q")


SCEN = (_s("S1.1", "C-1.1"), _s("S1.2", "C-1.2"), _s("S1.3", "C-1.3"),
        _s("S1.4", "C-1.4"), _s("S1.5", "C-1.5"))


def _r(sid, ok):
    return SpecResult(scenario_id=sid, clause_id="", passed=ok, exit_code=0 if ok else 1,
                      duration_ms=1)


def test_lessons_are_the_clauses_born_from_a_failure_signal():
    """C-3.1 — a lesson has a failure signal for a source; design intent and withdrawn text
    are not lessons."""
    got = lessons(parse(TEXT))
    assert [item["origin"] for item in got] == ["C-1.1", "C-1.2", "C-1.7"]
    assert {item["source"] for item in got} <= set(FAILURE_SOURCES)


def test_a_superseded_lesson_is_carried_to_its_live_successors():
    """C-3.2 — the wrong guess stays on the record; what is rerun is the proof of what
    replaced it."""
    by = {item["origin"]: item for item in lessons(parse(TEXT))}
    assert by["C-1.2"]["live"] == ("C-1.3", "C-1.4") and by["C-1.2"]["superseded"]
    assert by["C-1.1"]["live"] == ("C-1.1",) and not by["C-1.1"]["superseded"]


def test_a_rerun_runs_only_the_specs_of_lesson_clauses():
    """C-3.3 — the rerun set is exactly the specs bound to LIVE lesson clauses: not the spec
    of the superseded wording, not the design clause."""
    picked = specs_for(parse(TEXT), SCEN)
    assert [s.id for s in picked] == ["S1.1", "S1.3", "S1.4"]


def test_a_red_lesson_spec_reports_the_lesson_as_forgotten():
    """C-3.4 — a lesson whose proof went red was not learned, whatever the rest says."""
    rep = report(parse(TEXT), SCEN, (_r("S1.1", True), _r("S1.3", True), _r("S1.4", False)))
    by = {item["origin"]: item["status"] for item in rep["lessons"]}
    assert by["C-1.1"] == "kept" and by["C-1.2"] == "forgotten"
    assert not rep["passed"] and rep["counts"]["forgotten"] == 1


def test_a_lesson_without_a_spec_is_unproved_not_passed():
    """C-3.5 — silence is never proof: a lesson nothing runs cannot be kept."""
    rep = report(parse(TEXT), SCEN, (_r("S1.1", True), _r("S1.3", True), _r("S1.4", True)))
    by = {item["origin"]: item["status"] for item in rep["lessons"]}
    assert by["C-1.7"] == "unproved" and not rep["passed"]
    assert by["C-1.1"] == "kept" and by["C-1.2"] == "kept"
    assert rep["counts"] == {"kept": 2, "forgotten": 0, "unproved": 1, "skipped": 0}


def test_a_lesson_left_out_on_purpose_is_skipped_not_judged():
    """C-3.6 — a lane the caller chose is not silence, and it is not proof: it gets its own
    word, and it does not fail the report."""
    rep = report(parse(TEXT), SCEN, (_r("S1.3", True), _r("S1.4", True)), skipped={"S1.1"})
    by = {item["origin"]: item["status"] for item in rep["lessons"]}
    assert by["C-1.1"] == "skipped" and by["C-1.2"] == "kept"
    assert rep["counts"]["skipped"] == 1 and rep["counts"]["forgotten"] == 0
    assert not rep["passed"], "only C-1.7 (unproved) keeps this report from passing"
    # a spec that simply never ran, with nobody choosing that, is still forgotten
    silent = report(parse(TEXT), SCEN, (_r("S1.3", True), _r("S1.4", True)))
    assert {i["origin"]: i["status"] for i in silent["lessons"]}["C-1.1"] == "forgotten"
    # and a red verdict is forgotten even when the lane skipped a sibling spec
    red = report(parse(TEXT), SCEN, (_r("S1.3", False),), skipped={"S1.4"})
    assert {i["origin"]: i["status"] for i in red["lessons"]}["C-1.2"] == "forgotten"
