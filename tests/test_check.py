"""v3.5 the one-command loop — one verdict, one exit code, the failing LEG named.

Each test is the executable spec of one C-11.* clause in features/contract-layer/contract.md.
`lib.check` is pure: it folds reports into a verdict, so the verdict itself is golden-testable
without running a single spec.
"""
from __future__ import annotations

import pathlib

from lib.check import LEGS, build, render

GREEN = dict(
    lint_issues=(), critique_warnings=(),
    coverage={"passed": True, "live_clauses": 3, "uncovered": [], "orphan_specs": []},
    ledger_totals={"passed": 3, "total": 3, "failed": 0},
    todo={"remaining": 0, "counts": {"done": 3}, "backlog": 0},
    drift={"in_sync": True, "counts": {}},
    gates={"contract_bound": {"passed": True, "issues": []},
           "map_fresh": {"passed": True, "issues": []}},
)


def test_the_loop_answers_with_one_verdict_and_names_the_failing_leg():
    """C-11.1 — eight commands in a remembered order is a library; one verdict is a product."""
    ok = build(**GREEN)
    assert ok["passed"] and ok["failed"] == [] and ok["first_cause"] == ""
    assert set(ok["legs"]) == set(LEGS) and all(ok["legs"].values())

    broken = dict(GREEN, drift={"in_sync": False, "counts": {"spec_drift": 2}})
    rep = build(**broken)
    assert not rep["passed"] and "drift" in rep["failed"]
    assert rep["legs"]["specs_to_code"] is False
    assert rep["legs"]["contract"] is True, "an unrelated leg stays green"


def test_the_first_cause_is_the_most_upstream_failure_not_the_loudest():
    """C-11.2 — a broken contract makes every downstream report meaningless, so it is
    reported as the cause instead of the ten consequences it produces."""
    rep = build(**dict(GREEN, lint_issues=("C-1: supersedes unknown clause C-9",),
                       drift={"in_sync": False, "counts": {"missing_spec": 4}},
                       coverage={"passed": False, "uncovered": ["C-2"], "orphan_specs": []}))
    assert rep["first_cause"] == "contract.lint"
    assert rep["failed"][0] == "contract.lint"


def test_a_leg_with_no_evidence_is_incomplete_never_green():
    """C-11.3 — silence must not read as proof. The first cut computed `all()` over an EMPTY
    list of steps, so a leg that never ran was True and a run with a mis-typed --map printed
    `verdict: PASS` having checked nothing. An audit reproduced exactly that."""
    rep = build(lint_issues=(), critique_warnings=())
    names = [s["step"] for s in rep["steps"]]
    assert "spec.run" not in names and "drift" not in names
    assert not rep["passed"], "nothing ran, so nothing is proved"
    assert rep["legs"]["specs_to_code"] == "incomplete"
    assert rep["legs"]["code_to_specs"] == "incomplete"
    assert rep["incomplete"] == ["specs_to_code", "code_to_specs"]
    assert "no evidence" in rep["first_cause"]
    assert "INCOMPLETE" in render(rep)

    # a fast lane that KNOWINGLY skips a leg says so explicitly
    partial = build(lint_issues=(), critique_warnings=(), allow_partial=True)
    assert partial["passed"] and partial["incomplete"] == []


def test_a_named_but_absent_input_fails_instead_of_vanishing():
    """C-11.13 — a path the user typed and the tool cannot find is a mistake, not a choice;
    it used to make its whole step disappear and the verdict read PASS."""
    rep = build(**dict(GREEN, missing_inputs=(".athena/NO_SUCH_MAP.json",)))
    assert not rep["passed"] and rep["first_cause"] == "input.missing"
    step = next(s for s in rep["steps"] if s["step"] == "input.missing")
    assert step["detail"]["path"] == ".athena/NO_SUCH_MAP.json" and step["blocking"]


def test_wording_and_mutation_are_advisory_until_asked_to_block():
    """C-11.4 — a linter that fails the build on style, or on a partial mutation sweep,
    gets switched off; both become gates only on --strict."""
    warn = build(**dict(GREEN, critique_warnings=("C-1.1: not_atomic",)))
    assert warn["passed"] and "contract.wording" in warn["advisory"]

    strict = build(**dict(GREEN, critique_warnings=("C-1.1: not_atomic",), strict_wording=True))
    assert not strict["passed"] and "contract.wording" in strict["failed"]

    mut = build(**dict(GREEN, mutation={"mutants": 4, "killed": 3, "survived": 1,
                                        "undetermined": 0, "unowned": 0,
                                        "survivors": [{"path": "lib/a.py", "line": 7}]}))
    assert mut["passed"] and "mutation" in mut["advisory"]
    mut_strict = build(**dict(GREEN, mutation={"mutants": 4, "killed": 3, "survived": 1,
                                               "survivors": [], "blocking": True}))
    assert not mut_strict["passed"] and "mutation" in mut_strict["failed"]


def test_the_judge_can_never_block_the_verdict():
    """C-11.5 — a local model's opinion is advisory by construction; the only door to a gate
    is a scored corpus, and it is not this file."""
    failing_judge = build(**dict(GREEN, judge={"passes": False, "recall": 0.42,
                                               "false_reject": 0.33}))
    assert failing_judge["passed"], "a judge below the bar must not fail the build"
    assert "judge" in failing_judge["advisory"]
    step = next(s for s in failing_judge["steps"] if s["step"] == "judge")
    assert step["blocking"] is False


def test_the_map_gate_belongs_to_the_reverse_leg():
    """C-11.6 — map freshness is a code->specs question; putting it under the forward leg
    would hide which direction actually broke."""
    rep = build(**dict(GREEN, gates={"contract_bound": {"passed": True, "issues": []},
                                     "map_fresh": {"passed": False, "issues": ["stale"]}}))
    assert rep["legs"]["code_to_specs"] is False
    assert rep["legs"]["specs_to_code"] is True
    assert "seam.map_fresh" in rep["failed"]


def test_the_text_view_shows_every_leg_and_the_verdict():
    """C-11.7 — the answer has to be readable in a terminal without a JSON parser."""
    out = render(build(**dict(GREEN, drift={"in_sync": False, "counts": {"stale_proof": 1}})))
    assert "[ok] contract" in out and "[FAIL] specs_to_code" in out
    assert "verdict: FAIL" in out and "first cause: drift" in out
    assert "PASS" in render(build(**GREEN))


def test_a_clean_map_means_the_deep_lane_has_nothing_to_do():
    """C-11.11 — with nothing drifted there is nothing new to re-prove. Falling back to a
    whole-repo sweep looked like diligence and cost 1541 owned lines at up to 129 specs per
    mutant; a sweep is an explicit choice, never a default."""
    idle = build(**dict(GREEN, mutation={"mutants": 0, "killed": 0, "survived": 0,
                                         "survivors": [], "scope": [],
                                         "note": "no clause drifted"}))
    assert idle["passed"]
    step = next(s for s in idle["steps"] if s["step"] == "mutation")
    assert step["ok"] and step["detail"]["mutants"] in (0, None)

    # and a sweep that DID run and found a survivor still reports it
    swept = build(**dict(GREEN, mutation={"mutants": 12, "killed": 11, "survived": 1,
                                          "survivors": [{"path": "lib/a.py", "line": 3}]}))
    assert "mutation" in swept["advisory"]
    assert swept["steps"][-1]["detail"]["survivors"] == ["lib/a.py:3"]


def test_every_mutation_outcome_reaches_the_report():
    """C-11.14 — the detail whitelist dropped `undetermined`, so a run of 20 mutants where
    NONE was decided rendered as a clean "ok mutation" row. All four states are shown."""
    rep = build(**dict(GREEN, mutation={"mutants": 20, "killed": 0, "survived": 0,
                                        "undetermined": 18, "unowned": 2, "survivors": [],
                                        "note": "budget exhausted"}))
    detail = next(s for s in rep["steps"] if s["step"] == "mutation")["detail"]
    assert detail["undetermined"] == 18 and detail["unowned"] == 2
    assert detail["note"] == "budget exhausted"
    assert "undetermined=18" in render(rep)


def test_default_paths_are_resolved_next_to_the_contract(tmp_path):
    """C-11.18 — an audit checked a scaffolded project from inside this repo and the reverse
    leg judged it against THIS repo's clause map. A gate answering about the wrong codebase
    is worse than one that does not run."""
    import athena

    (tmp_path / ".athena").mkdir()
    (tmp_path / ".athena" / "clause_map.json").write_text("{}", encoding="utf-8")
    ns = type("NS", (), {"contract": str(tmp_path / "contract.md"), "ledger": None, "map": None})
    here = pathlib.Path(ns.contract).resolve().parent
    assert here == tmp_path.resolve()
    guessed = str(here / ".athena" / "clause_map.json")
    assert guessed.startswith(str(tmp_path.resolve()))
    assert not guessed.startswith(str(pathlib.Path(athena.__file__).resolve().parent))
