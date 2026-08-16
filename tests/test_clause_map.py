"""v3.3 the per-clause file:line map — line-level ownership, derived and never annotated.

The reverse leg was stuck at FILE granularity, so a contract that claims `lib/seams.py` for
one gate looked like it claimed all of it. The map fixes that by using a binding that already
exists — clause -> spec -> run_cmd — and running each spec ALONE under coverage.

Each test is the executable spec of one C-9.* clause in features/contract-layer/contract.md.
The effectful collector takes an injected runner, so this suite never spawns coverage.
"""
from __future__ import annotations

import json

import pytest

from lib.ast import Scenario
from lib.clause_map import (SCHEMA, SpecLines, build, classify, collect, json_argv,
                            lines_from_json, owned_lines, owners, run_argv)


def _lines(sid, clause, files):
    return SpecLines(scenario_id=sid, clause_id=clause, files=files)


def test_a_clause_owns_the_union_of_the_lines_its_specs_execute():
    """C-9.1 — the map is DERIVED from the clause->spec binding, never authored by hand,
    so it cannot drift from the code the way an annotation would."""
    cmap = build((
        _lines("S1.1", "C-1.1", {"lib/a.py": (1, 2, 3)}),
        _lines("S1.2", "C-1.1", {"lib/a.py": (3, 4), "lib/b.py": (7,)}),
        _lines("S2.1", "C-2.1", {"lib/b.py": (7, 8)}),
    ), contract_version="cv1", scenario_version="sv1")

    assert cmap["schema"] == SCHEMA
    assert cmap["clauses"]["C-1.1"] == {"lib/a.py": [1, 2, 3, 4], "lib/b.py": [7]}
    assert cmap["clauses"]["C-2.1"] == {"lib/b.py": [7, 8]}
    assert cmap["specs"] == {"S1.1": "C-1.1", "S1.2": "C-1.1", "S2.1": "C-2.1"}
    # deterministic: same input -> byte-identical artifact
    assert json.dumps(cmap, sort_keys=True) == json.dumps(
        build((_lines("S2.1", "C-2.1", {"lib/b.py": (8, 7)}),
               _lines("S1.2", "C-1.1", {"lib/b.py": (7,), "lib/a.py": (4, 3)}),
               _lines("S1.1", "C-1.1", {"lib/a.py": (3, 2, 1)})),
              contract_version="cv1", scenario_version="sv1"), sort_keys=True)


def test_owners_answers_which_requirements_a_line_serves():
    """C-9.2 — "I am about to change this line; what am I allowed to break?" Shared code
    reports EVERY owner, because two requirements leaning on one line is normal."""
    cmap = build((_lines("S1", "C-1.1", {"lib/a.py": (1, 5)}),
                  _lines("S2", "C-2.1", {"lib/a.py": (5, 6)})))
    assert owners(cmap, "lib/a.py", 1) == ("C-1.1",)
    assert owners(cmap, "lib/a.py", 5) == ("C-1.1", "C-2.1")
    assert owners(cmap, "lib/a.py", 99) == ()
    assert owners(cmap, "lib\\a.py", 5) == ("C-1.1", "C-2.1")     # path separators normalize
    assert owned_lines(cmap)["lib/a.py"] == frozenset({1, 5, 6})


def test_the_map_runner_refuses_the_same_commands_the_spec_runner_refuses():
    """C-9.3 — this path executes run_cmds too, so it must not become a way around the
    shell-less rule; the interpreter is normalized so `coverage run -m` can take its place."""
    assert run_argv("python -m pytest tests/t.py::x -q", "d.cov", ("lib",)) == [
        "python", "-m", "coverage", "run", "--data-file=d.cov", "--source=lib",
        "-m", "pytest", "tests/t.py::x", "-q"]
    # a bare `pytest ...` is turned into `-m pytest ...` (a console script cannot be run
    # by `coverage run` on Windows)
    assert run_argv("pytest tests/t.py -q", "d.cov", ())[-3:] == ["pytest", "tests/t.py", "-q"]
    for bad in ("pytest -q; rm -rf /", "pytest -q | tee x", "pytest $(id)", ""):
        with pytest.raises(ValueError, match="refused"):
            run_argv(bad, "d.cov", ("lib",))
    assert json_argv("d.cov", "o.json")[:4] == ["python", "-m", "coverage", "json"]


def test_classification_separates_owned_code_from_another_features_code():
    """C-9.4 — code the wider suite tests but no clause of THIS contract demands is not a
    gap; conflating the two is what made the file-level report unreadable."""
    cmap = build((_lines("S1", "C-1.1", {"lib/seams.py": (10, 11, 12)}),))
    suite = {"lib/seams.py": range(1, 21)}
    rep = classify(cmap, suite)
    assert rep["lib/seams.py"]["owned"] == [10, 11, 12]
    assert rep["lib/seams.py"]["owned_count"] == 3
    assert 1 in rep["lib/seams.py"]["other_coverage"]
    assert 10 not in rep["lib/seams.py"]["other_coverage"]
    assert rep["lib/seams.py"]["other_coverage_count"] == 17


def test_a_spec_that_produces_no_coverage_data_is_skipped_not_fatal():
    """C-9.5 — a partial map still answers most queries; aborting the whole collection
    because one spec misbehaved would make the map unbuildable on any real repo."""
    calls = []

    def runner(argv, cwd):
        calls.append(argv)
        return 0                       # never writes the json file

    scenarios = (Scenario("S1", "C-1.1", "G/W/T", "python -m pytest t.py::a -q"),
                 Scenario("S2", "C-1.2", "G/W/T", "pytest -q; rm -rf /"))
    got = collect(scenarios, sources=("lib",), workdir="D:/tmp/claude/na", runner=runner, jobs=2)
    assert [s.scenario_id for s in got] == ["S1", "S2"]
    assert all(s.files == {} for s in got)
    # the refused command never reached the runner
    assert all("rm" not in " ".join(a) for a in calls)


def test_the_map_pins_the_versions_it_was_built_from():
    """C-9.6 — a map is a proof artifact: without pins nobody can tell it went stale."""
    cmap = build((_lines("S1", "C-1.1", {"lib/a.py": (1,)}),),
                 contract_version="abc", scenario_version="def")
    assert cmap["contract_version"] == "abc" and cmap["scenario_version"] == "def"


def test_lines_from_json_reads_coverage_output():
    """C-9.7 — the collector reads coverage.py's own JSON, so no coverage import leaks into
    lib/ and the module stays stdlib-only like the rest of the freeze-line."""
    text = json.dumps({"files": {
        "lib\\a.py": {"executed_lines": [3, 1, 2], "missing_lines": [9]},
        "lib/b.py": {"executed_lines": []},
    }})
    assert lines_from_json(text) == {"lib/a.py": (1, 2, 3)}


# --- the gate: a derived artifact nobody re-derives is worse than none ----------

from lib.contract import parse as parse_contract          # noqa: E402
from lib.clause_map import digests, merge, staleness, stale_clauses  # noqa: E402
from lib.seams import seam_map_fresh                      # noqa: E402

GATE_CONTRACT = parse_contract("""# Contract: Gate

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
- **C-1.2** — WHEN asked twice THE SYSTEM SHALL answer twice.
""")


def _fresh_map():
    return build((_lines("S1", "C-1.1", {"lib/a.py": (1,)}),
                  _lines("S2", "C-1.2", {"lib/a.py": (2,)})),
                 contract_version=GATE_CONTRACT.version, scenario_version="scv1")


def test_a_map_pinned_to_another_version_is_stale():
    """C-9.8 — the pins are the cheap check: a map built before the last edit describes a
    contract that no longer exists, and says nothing about it."""
    cmap = _fresh_map()
    fresh = staleness(cmap, GATE_CONTRACT, (), scenario_version="scv1")
    assert fresh["is_fresh"] and not fresh["contract_drift"] and not fresh["spec_drift"]

    moved = dict(cmap, contract_version="0" * 16)
    assert staleness(moved, GATE_CONTRACT, (), scenario_version="scv1")["contract_drift"]
    assert staleness(cmap, GATE_CONTRACT, (), scenario_version="other")["spec_drift"]


def test_a_clause_added_since_the_map_was_built_is_unmapped():
    """C-9.9 — `owners()` would answer "nobody owns this" for a clause that simply was not
    in the world yet; the gate must call that stale, not empty."""
    grown = parse_contract("""# Contract: Gate

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
- **C-1.2** — WHEN asked twice THE SYSTEM SHALL answer twice.
- **C-1.3** — WHEN asked thrice THE SYSTEM SHALL answer thrice.
""")
    rep = staleness(_fresh_map(), grown, (), scenario_version="scv1")
    assert rep["unmapped"] == ["C-1.3"] and not rep["is_fresh"]


def test_a_map_entry_for_a_deleted_clause_is_stale():
    """C-9.10 — territory owned by a requirement that no longer exists is a lie about scope."""
    shrunk = parse_contract("""# Contract: Gate

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
""")
    rep = staleness(_fresh_map(), shrunk, (), scenario_version="scv1")
    assert rep["stale_entries"] == ["C-1.2"] and not rep["is_fresh"]


def test_the_gate_fails_closed_when_the_map_is_absent_or_foreign():
    """C-9.11 — "no map" must never read as "nothing to check"."""
    for empty in ({}, {"schema": "something/else", "clauses": {"C-1.1": {}}},
                  {"schema": SCHEMA, "clauses": {}}):
        r = seam_map_fresh(empty, GATE_CONTRACT, (), scenario_version="scv1")
        assert not r.passed
        assert any("absent" in i for i in r.issues)

    ok = seam_map_fresh(_fresh_map(), GATE_CONTRACT, (), scenario_version="scv1")
    assert ok.passed and ok.issues == ()


def test_the_gate_hash_moves_when_the_map_goes_stale():
    """C-9.12 — the seam's artifact hash fingerprints the pins and the id deltas."""
    a = seam_map_fresh(_fresh_map(), GATE_CONTRACT, (), scenario_version="scv1")
    b = seam_map_fresh(dict(_fresh_map(), contract_version="0" * 16), GATE_CONTRACT, (),
                       scenario_version="scv1")
    assert a.artifact_hash != b.artifact_hash


def test_only_the_clauses_whose_lines_moved_go_stale():
    """C-9.15 — the pin covers the lines a clause OWNS, so an edit elsewhere in the same
    file costs nothing; whole-file pinning made the map unkeepable on an active file."""
    src = {"lib/a.py": "one\ntwo\nthree\nfour\n"}
    shape = (_lines("S1", "C-1.1", {"lib/a.py": (2,)}),
             _lines("S2", "C-1.2", {"lib/a.py": (3,)}))
    cmap = build(shape, contract_version=GATE_CONTRACT.version, scenario_version="scv1")
    cmap = build(shape, contract_version=GATE_CONTRACT.version, scenario_version="scv1",
                 clause_digests=digests(cmap, src))

    untouched = digests(cmap, {"lib/a.py": "one\ntwo\nthree\nEDITED\n"})
    assert stale_clauses(cmap, untouched) == ()          # line 4 belongs to no clause

    one_moved = digests(cmap, {"lib/a.py": "one\ntwo\nEDITED\nfour\n"})
    assert stale_clauses(cmap, one_moved) == ("C-1.2",)  # only the owner of line 3

    shifted = digests(cmap, {"lib/a.py": "NEW\none\ntwo\nthree\nfour\n"})
    assert stale_clauses(cmap, shifted) == ("C-1.1", "C-1.2")   # everything moved

    r = seam_map_fresh(cmap, GATE_CONTRACT, (), scenario_version="scv1",
                       clause_digests=one_moved)
    assert not r.passed
    assert any("C-1.2" in i and "owns changed" in i for i in r.issues)
    # the contract and the specs never moved: without the line pin this reads as fresh
    rep = staleness(cmap, GATE_CONTRACT, (), scenario_version="scv1",
                    clause_digests=one_moved)
    assert not rep["contract_drift"] and not rep["spec_drift"]


def test_a_line_that_no_longer_exists_counts_as_moved():
    """C-9.16 — a clause whose file shrank past its lines must not digest as unchanged."""
    src = {"lib/a.py": "one\ntwo\nthree\n"}
    shape = (_lines("S1", "C-1.1", {"lib/a.py": (3,)}),)
    cmap = build(shape)
    cmap = build(shape, clause_digests=digests(cmap, src))
    assert stale_clauses(cmap, digests(cmap, {"lib/a.py": "one\ntwo\n"})) == ("C-1.1",)
    assert stale_clauses(cmap, digests(cmap, {})) == ("C-1.1",)      # file gone entirely


def test_an_incremental_rebuild_keeps_the_clauses_that_still_hold():
    """C-9.17 — re-deriving one clause must cost one spec run, not the whole suite; the
    untouched entries are carried over byte-for-byte."""
    base = build((_lines("S1", "C-1.1", {"lib/a.py": (1,)}),
                  _lines("S2", "C-1.2", {"lib/a.py": (2,)})),
                 contract_version="cv", scenario_version="sv",
                 clause_digests={"C-1.1": "d1", "C-1.2": "d2"})
    merged = merge(base, (_lines("S2", "C-1.2", {"lib/a.py": (7, 8)}),),
                   contract_version="cv", scenario_version="sv",
                   clause_digests={"C-1.2": "d2-new"}, rebuilt=("C-1.2",))
    assert merged["clauses"]["C-1.1"] == {"lib/a.py": [1]}          # untouched, carried over
    assert merged["clauses"]["C-1.2"] == {"lib/a.py": [7, 8]}       # replaced, not unioned
    assert merged["clause_digests"] == {"C-1.1": "d1", "C-1.2": "d2-new"}
    assert merged["specs"] == {"S1": "C-1.1", "S2": "C-1.2"}
    assert merged["schema"] == SCHEMA


def test_a_map_in_the_previous_schema_is_refused():
    """C-9.14 — a v1 map cannot prove source freshness at all, so it fails rather than
    passing on the strength of pins it does not carry."""
    old = dict(_fresh_map(), schema="athena.clause_map/1")
    r = seam_map_fresh(old, GATE_CONTRACT, (), scenario_version="scv1")
    assert not r.passed and any("absent" in i for i in r.issues)


def test_every_source_root_reaches_the_coverage_command():
    """C-9.18 - more than one coverage source root is passed as ONE option, because
    coverage.py lets the last repetition of the flag win."""
    argv = run_argv("python -m pytest t.py::x -q", "d.coverage", ("lib", "athena.py"))
    srcs = [a for a in argv if a.startswith("--source")]
    assert srcs == ["--source=lib,athena.py"], (
        "repeating the flag drops every root but the last: the real run measured athena.py "
        "alone, a module pytest never imports, and collected nothing for 26 specs")
    assert [a for a in run_argv("python -m pytest t.py -q", "d", ()) if "source" in a] == []
    dup = run_argv("python -m pytest t.py -q", "d", ("lib", "lib", "athena.py"))
    assert "--source=lib,athena.py" in dup, "argparse append over a default repeats the root"


def test_a_spec_that_ran_and_owns_nothing_is_not_a_failed_collection():
    """C-9.20 - the binding guard imports nothing from lib/, so owning no lines is its
    correct answer; owning no lines because coverage never ran is not an answer at all."""
    ran = build((_lines("S1", "C-1.1", {"lib/a.py": (1,)}),
                 SpecLines(scenario_id="S2", clause_id="C-1.2", files={}, collected=True)),
                contract_version=GATE_CONTRACT.version, scenario_version="scv1")
    assert ran["collected"] == ["C-1.1", "C-1.2"]
    assert staleness(ran, GATE_CONTRACT, (), scenario_version="scv1")["unmapped"] == []

    blind = build((_lines("S1", "C-1.1", {"lib/a.py": (1,)}),
                   SpecLines(scenario_id="S2", clause_id="C-1.2", files={}, collected=False)),
                  contract_version=GATE_CONTRACT.version, scenario_version="scv1")
    assert blind["collected"] == ["C-1.1"]
    assert staleness(blind, GATE_CONTRACT, (), scenario_version="scv1")["unmapped"] == ["C-1.2"]

    carried = merge(ran, (), contract_version=GATE_CONTRACT.version, scenario_version="scv1")
    assert carried["collected"] == ["C-1.1", "C-1.2"], "an untouched clause keeps its answer"


def test_merging_nothing_re_pins_the_map():
    """C-9.21 - an edit that owns no lines (a note, a draft clause) still moves the contract
    version, and an incremental rebuild that finds nothing to re-derive must re-pin anyway."""
    base = _fresh_map()
    same = merge(base, (), contract_version="new-contract-version", scenario_version="scv2")

    assert same["clauses"] == base["clauses"], "nothing was re-derived, so nothing may move"
    assert same["collected"] == base["collected"]
    assert (same["contract_version"], same["scenario_version"]) == ("new-contract-version",
                                                                    "scv2")
    assert staleness(same, GATE_CONTRACT, (), scenario_version="scv2")["spec_drift"] is False
