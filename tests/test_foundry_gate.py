"""v3.16 the foundry — mutation as a gate (C-1) and drafted specs admitted, not trusted (C-2).

Each test is the executable spec of one clause in features/foundry-layer/contract.md.
"""
from __future__ import annotations

CLAUSE_MAP = {"clauses": {
    "C-2.1": {"lib/refinery.py": [10, 11, 12, 13], "tests/test_refinery.py": [50]},
    "C-2.3": {"lib/refinery.py": [30, 31]},
    "C-2.5": {"lib/refinery.py": [12, 60, 61], "lib/other.py": [5]},
}}


def test_the_sweep_is_restricted_to_changed_lines_mapped_to_their_clauses():
    """C-1.1 — changed lines become per-clause targets through the map, test files are not
    targets, a line two clauses own goes to both, and unowned changed lines are reported."""
    from lib.mutgate import changed_targets
    diff = {"lib/refinery.py": [11, 12, 31, 99], "tests/test_refinery.py": [50], "lib/new.py": [1, 2]}
    targets, unowned = changed_targets(diff, CLAUSE_MAP)
    assert targets == {"C-2.1": {"lib/refinery.py": [11, 12]}, "C-2.3": {"lib/refinery.py": [31]},
                       "C-2.5": {"lib/refinery.py": [12]}}
    assert unowned == {"lib/new.py": [1, 2], "lib/refinery.py": [99]}
    assert changed_targets({}, CLAUSE_MAP) == ({}, {})


def test_a_per_clause_mutation_score_is_computed_over_owned_lines_with_survivors_listed():
    """C-1.2 — score = killed / total per clause over its target lines; survivors carry path,
    line and kind; a clause with no mutants has no score, not zero."""
    from lib.mutgate import clause_scores
    targets = {"C-2.1": {"lib/refinery.py": [11, 12]}, "C-2.3": {"lib/refinery.py": [31]}, "C-2.5": {"lib/refinery.py": [12]}}
    results = [{"path": "lib/refinery.py", "line": 11, "kind": "compare", "killed": True},
               {"path": "lib/refinery.py", "line": 11, "kind": "constant", "killed": False},
               {"path": "lib/refinery.py", "line": 12, "kind": "boolop", "killed": True},
               {"path": "lib/refinery.py", "line": 31, "kind": "compare", "killed": True}]
    scores = clause_scores(results, targets)
    assert scores["C-2.1"] == {"score": 2 / 3, "killed": 2, "total": 3,
                               "survivors": [{"path": "lib/refinery.py", "line": 11, "kind": "constant"}]}
    assert scores["C-2.3"] == {"score": 1.0, "killed": 1, "total": 1, "survivors": []}
    assert scores["C-2.5"] == {"score": 1.0, "killed": 1, "total": 1, "survivors": []}
    assert "C-9.9" not in clause_scores(results, {"C-9.9": {"lib/refinery.py": [500]}})


def test_the_offer_is_refused_at_the_mutation_stage_on_added_lines_only():
    """C-1.3 — under threshold on added lines, or any survivor on an added line: refused with
    the clause and the first survivor; under threshold on untouched lines: advisory."""
    from lib.mutgate import mutation_verdict
    scores = {"C-2.1": {"score": 0.5, "killed": 1, "total": 2,
                        "survivors": [{"path": "lib/refinery.py", "line": 11, "kind": "constant"}]},
              "C-2.3": {"score": 1.0, "killed": 1, "total": 1, "survivors": []}}
    v = mutation_verdict(scores, threshold=0.7, added={"lib/refinery.py": [11]})
    assert v["ok"] is False and v["stage"] == "mutation" and v["clause"] == "C-2.1"
    assert v["survivor"] == {"path": "lib/refinery.py", "line": 11, "kind": "constant"}
    v = mutation_verdict(scores, threshold=0.7, added={"lib/refinery.py": [31]})
    assert v["ok"] is True and v["advisory"] == ["C-2.1"] and v["clause"] is None
    v = mutation_verdict(scores, threshold=0.4, added={"lib/refinery.py": [12]})
    assert v["ok"] is True and v["advisory"] == []
    assert mutation_verdict({}, threshold=0.7, added={"lib/x.py": [1]})["ok"] is True


def test_a_sealed_run_is_reduced_to_pass_or_fail_per_test_id():
    """C-1.4 — what the executor or a checkpoint sees of a sealed run is the outcome per test
    id and the counts; assertion messages, diffs and tracebacks are gone."""
    from lib.mutgate import sealed_summary
    tail = ("tests/sealed/test_acc.py::test_a PASSED\n"
            "tests/sealed/test_acc.py::test_b FAILED\n"
            "=================================== FAILURES ===================================\n"
            "____ test_b ____\n"
            "    assert merge(a, b) == 3\n"
            "E   AssertionError: expected 3 got 2\n"
            "E   +  where 2 = merge(1, 1)\n"
            "FAILED tests/sealed/test_acc.py::test_b - AssertionError: expected 3 got 2\n"
            "========================= 1 failed, 1 passed in 0.12s ==========================\n")
    out = sealed_summary(tail)
    assert out.splitlines() == ["FAIL tests/sealed/test_acc.py::test_b", "PASS tests/sealed/test_acc.py::test_a",
                                "1 failed, 1 passed"]
    assert "AssertionError" not in out and "expected 3" not in out and "merge(" not in out
    assert sealed_summary("") == "no tests ran"


def test_a_drafted_test_is_admitted_only_when_red_at_base_green_at_head_and_covering_owned_lines():
    """C-2.1 — fail-before, pass-after, covers an owned line; each refusal names its reason."""
    from lib.drafts import admit_draft
    owned = {"lib/refinery.py": [10, 11, 12]}
    assert admit_draft(base_exit=1, head_exit=0, covered={"lib/refinery.py": [11, 40]}, owned=owned) == (True, "admitted")
    assert admit_draft(base_exit=0, head_exit=0, covered={"lib/refinery.py": [11]}, owned=owned) == (False, "green at base")
    assert admit_draft(base_exit=1, head_exit=1, covered={"lib/refinery.py": [11]}, owned=owned) == (False, "red at head")
    assert admit_draft(base_exit=1, head_exit=0, covered={"lib/refinery.py": [40]}, owned=owned) == (False, "covers no owned line")
    assert admit_draft(base_exit=1, head_exit=0, covered={}, owned=owned) == (False, "covers no owned line")


def test_a_clause_draft_is_accepted_only_in_an_ears_shape_with_one_shall():
    """C-2.2 — the six EARS shapes are recognised; zero or two SHALLs, no shape, or nothing
    after SHALL are named defects."""
    from lib.drafts import ears_shape, validate_clause
    assert ears_shape("THE SYSTEM SHALL keep the ledger append-only.") == "ubiquitous"
    assert ears_shape("WHEN a verdict is red THE SYSTEM SHALL append a lesson.") == "event"
    assert ears_shape("WHILE a lane is cooling THE SYSTEM SHALL route around it.") == "state"
    assert ears_shape("WHERE the sandbox flag is on THE SYSTEM SHALL wrap every command.") == "optional"
    assert ears_shape("IF the heartbeat is stale THEN THE SYSTEM SHALL release the claim.") == "unwanted"
    assert ears_shape("WHILE the daemon runs WHEN a task is ready THE SYSTEM SHALL claim it.") == "complex"
    assert ears_shape("The system keeps the ledger.") is None
    assert validate_clause("WHEN a verdict is red THE SYSTEM SHALL append a lesson.") == ()
    assert validate_clause("The system keeps the ledger.") == ("no SHALL", "no EARS shape")
    assert validate_clause("WHEN x THE SYSTEM SHALL do a AND SHALL do b.") == ("more than one SHALL",)
    assert validate_clause("WHEN x THE SYSTEM SHALL") == ("no response after SHALL",)


def test_acceptance_is_kept_per_drafting_model_and_rendered_as_a_rate():
    """C-2.3 — drafted, admitted, accepted-without-edit per model; rates over drafted; the
    render names the model and both rates."""
    from lib.drafts import acceptance, render_acceptance
    events = [{"model": "pi-9b", "admitted": True, "accepted": True},
              {"model": "pi-9b", "admitted": True, "accepted": False},
              {"model": "pi-9b", "admitted": False, "accepted": False},
              {"model": "pi-3b", "admitted": False, "accepted": False}]
    table = acceptance(events)
    assert table["pi-9b"] == {"drafted": 3, "admitted": 2, "accepted": 1, "admitted_rate": 2 / 3, "accepted_rate": 1 / 3}
    assert table["pi-3b"] == {"drafted": 1, "admitted": 0, "accepted": 0, "admitted_rate": 0.0, "accepted_rate": 0.0}
    text = render_acceptance(table)
    assert "pi-9b" in text and "67%" in text and "33%" in text and "pi-3b" in text
    assert acceptance([]) == {}


def test_a_task_is_judged_by_its_own_checks_and_regressions_from_a_red_base():
    """C-8.4 — a red base is not the task's fault: its own checks and regressions decide; an
    iteration that touched a spec file is never the one kept."""
    from lib.dispatch import regression, verdict
    own = "python -m pytest tests/t.py::own -q"
    other = "python -m pytest tests/t.py::other -q"
    third = "python -m pytest tests/t.py::third -q"
    before, after = {"lib/m.py": (1, 1)}, {"lib/m.py": (2, 2)}
    checks = [{"cmd": own, "exit": 0, "tail": "1 passed"}, {"cmd": other, "exit": 1, "tail": "1 failed"}]
    plain = verdict(before, after, checks)
    assert plain["green"] is False and other in plain["reason"]
    inherited = verdict(before, after, checks, base_red=[other], own=[own])
    assert inherited["green"] is True and inherited["inherited"] == [other]
    assert other in inherited["reason"] and "inherited" in inherited["reason"]
    # the task's own check is never inherited, even when it was red at the base
    own_red = verdict(before, after, [{"cmd": own, "exit": 1, "tail": "1 failed"}], base_red=[own], own=[own])
    assert own_red["green"] is False and own_red["inherited"] == []
    # a red the base did not have is a regression
    regressed = verdict(before, after, checks + [{"cmd": third, "exit": 1, "tail": "1 failed"}], base_red=[other], own=[own])
    assert regressed["green"] is False and third in regressed["reason"] and regressed["inherited"] == [other]
    # a radius batch cut differently than at the base is inherited when all its members were red there
    batch = {"cmd": "python -m pytest tests/t.py::other tests/t.py::more -q", "exit": 1, "tail": "2 failed",
             "members": ["python -m pytest tests/t.py::other -q", "python -m pytest tests/t.py::more -q"]}
    by_members = verdict(before, after, [checks[0], batch], base_red=[other, "python -m pytest tests/t.py::more -q"], own=[own])
    assert by_members["green"] is True and by_members["inherited"] == [batch["cmd"]]
    partly = verdict(before, after, [checks[0], batch], base_red=[other], own=[own])
    assert partly["green"] is False and partly["inherited"] == []
    # an iteration that edited a spec file is tainted: restored to the best before it though the counts tie
    tainted = verdict(before, {**after, "tests/t.py": (9, 9)}, checks, spec_files=["tests/t.py"], base_red=[other], own=[own])
    assert tainted["green"] is False and tainted["spec_touched"] == ["tests/t.py"]
    its = [checks, checks]
    assert regression(its) is None
    assert regression(its, tainted_last=True) == {"restore": 1, "from": 2, "green_before": 1, "green_after": 1, "tainted": True}
    assert regression([checks], tainted_last=True) is None   # nothing before it: the caller restores the base


def _sealed_gaps(root) -> list:
    """PURE over the tree: the features with a contract and no sealed second reading naming one of its clauses."""
    import ast
    import pathlib
    import re
    gaps = []
    for feature in sorted(p for p in (root / "features").iterdir() if (p / "contract.md").exists()):
        ids = set(re.findall(r"\*\*(C-\d+\.\d+)\*\*", (feature / "contract.md").read_text(encoding="utf-8")))
        ok = False
        for f in sorted((feature / "sealed").glob("test_*.py")) if (feature / "sealed").is_dir() else []:
            for node in ast.parse(f.read_text(encoding="utf-8")).body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_sealed_"):
                    doc = ast.get_docstring(node) or ""
                    named = re.findall(r"C-\d+\.\d+", doc.split("(sealed)")[0])
                    if named and all(n in ids for n in named):
                        ok = True
        if not ok:
            gaps.append(feature.name)
    return gaps


def test_every_feature_with_a_contract_carries_a_sealed_second_reading():
    """C-1.5 — the sealed tier is the norm: every feature with a contract has a second reading that
    names one of its own clauses, and the guard names a feature that lacks one."""
    import pathlib
    import tempfile
    assert _sealed_gaps(pathlib.Path(__file__).resolve().parents[1]) == []
    with tempfile.TemporaryDirectory() as td:
        fake = pathlib.Path(td) / "features" / "bare-layer"
        fake.mkdir(parents=True)
        (fake / "contract.md").write_text("- **C-1.1** — WHEN a THE SYSTEM SHALL b.", encoding="utf-8")
        assert _sealed_gaps(pathlib.Path(td)) == ["bare-layer"]
        (fake / "sealed").mkdir()
        (fake / "sealed" / "test_sealed_bare.py").write_text('def test_sealed_x():\n    """C-1.1 (sealed) — second reading."""\n', encoding="utf-8")
        assert _sealed_gaps(pathlib.Path(td)) == []
        (fake / "sealed" / "test_sealed_bare.py").write_text('def test_sealed_x():\n    """C-9.9 (sealed) — names a clause the contract does not have."""\n', encoding="utf-8")
        assert _sealed_gaps(pathlib.Path(td)) == ["bare-layer"]

