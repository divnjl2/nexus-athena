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
