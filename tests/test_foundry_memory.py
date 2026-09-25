"""v3.16 the foundry — memory in the packet (C-7) and regeneration from the spec (C-8).

Each test is the executable spec of one clause in features/foundry-layer/contract.md.
"""
from __future__ import annotations


INDEX = {"lib/a.py": ["def admit(records, task, workspace)", "def conflicts_from(output)"],
         "lib/b.py": ["def rebase(run, cwd, onto)", "def fast_forward(run, cwd, target, head)"],
         "lib/c.py": ["def unrelated()"] * 40,
         "tests/test_a.py": ["def test_x()"]}


def test_a_repo_map_seeded_from_the_tasks_files_fits_the_budget_after_the_prefix():
    """C-7.1 — seed files come first with all their signatures, then the rest until the
    budget; the map is placed after the static prefix, never before it."""
    from lib.memory import place_after_prefix, repo_map_for
    text = repo_map_for(INDEX, seeds=["lib/b.py"], budget_tokens=60)
    assert text.index("lib/b.py") < text.index("lib/a.py") and "fast_forward" in text
    assert len(text) <= 60 * 4 + 40 and text.rstrip().endswith("...")
    full = repo_map_for(INDEX, seeds=["lib/a.py"], budget_tokens=10000)
    assert "lib/c.py" in full and not full.rstrip().endswith("...")
    packet = "STATIC PREFIX\n## The requirement\nbody\n## Order\nDONE\n"
    out = place_after_prefix(packet, "## Repository map\n" + text, marker="## The requirement")
    assert out.index("STATIC PREFIX") < out.index("## Repository map") < out.index("## The requirement")


def test_a_red_verdict_becomes_a_lesson_with_a_failure_class_and_a_rule_never_the_diff():
    """C-7.2 — clause id, file, failure class from the tail, a one-line rule, the verdict id;
    a green verdict yields none; no diff text travels."""
    from lib.memory import lesson_from
    v = {"id": "v-17", "task": "T2.2", "clauses": ["C-2.2"], "green": False, "changed_files": ["lib/refinery.py"],
         "checks": [{"cmd": "python -m pytest tests/t.py::test_r -q", "exit": 1,
                     "tail": "E   ImportError: cannot import name 'rebase' from 'lib.refinery'"}],
         "diff": "+def rebase(): pass"}
    lesson = lesson_from(v)
    assert lesson["clause"] == "C-2.2" and lesson["file"] == "lib/refinery.py" and lesson["verdict"] == "v-17"
    assert lesson["failure"] == "import" and "rebase" in lesson["rule"] and chr(10) not in lesson["rule"]
    assert "+def" not in str(lesson)
    assert lesson_from({**v, "checks": [{"cmd": "c", "exit": 1, "tail": "E   assert 1 == 2"}]})["failure"] == "assertion"
    assert lesson_from({**v, "checks": [{"cmd": "c", "exit": 1, "tail": "SyntaxError: invalid syntax"}]})["failure"] == "syntax"
    assert lesson_from({**v, "checks": [{"cmd": "c", "exit": 124, "tail": ""}]})["failure"] == "timeout"
    assert lesson_from({**v, "green": True}) is None


def test_lessons_are_selected_by_exact_clause_and_file_capped_and_retired_after_ten_green_rides():
    """C-7.3 — exact clause id or file match, at most n, each rule capped; a lesson that rode in
    ten green packets is retired."""
    from lib.memory import decay, select_lessons
    lessons = [{"id": 1, "clause": "C-2.2", "file": "lib/refinery.py", "rule": "r1 " * 100},
               {"id": 2, "clause": "C-2.4", "file": "lib/refinery.py", "rule": "r2"},
               {"id": 3, "clause": "C-9.9", "file": "lib/other.py", "rule": "r3"},
               {"id": 4, "clause": "C-2.2", "file": "lib/x.py", "rule": "r4"}]
    chosen = select_lessons(lessons, clause_ids=["C-2.2"], files=["lib/refinery.py"], n=2, cap_chars=60)
    assert [l["id"] for l in chosen] == [1, 2] and all(len(l["rule"]) <= 60 for l in chosen)
    assert [l["id"] for l in select_lessons(lessons, clause_ids=["C-2.2"], files=[], n=5, cap_chars=60)] == [1, 4]
    assert select_lessons(lessons, clause_ids=["C-1.1"], files=["lib/none.py"], n=5, cap_chars=60) == []
    kept = decay(lessons, green_rides={1: 10, 2: 9, 3: 11}, limit=10)
    assert [l["id"] for l in kept] == [2, 4]


def test_a_regeneration_packet_carries_clauses_specs_and_signatures_never_the_old_body():
    """C-8.1 — the packet names the module, its clauses, its specs and the public signatures;
    no line of the old body appears in it."""
    from lib.regen import regen_packet
    body = "def admit(records, task, workspace):\n    last = [r for r in records if r['task'] == task]\n    return bool(last and last[-1]['green'])\n"
    pk = regen_packet(module="lib/refinery.py", clauses_text="- **C-2.1** — WHEN a workspace is offered ...",
                      specs_text="### S2.1 ...", signatures=["def admit(records, task, workspace) -> dict"])
    assert "lib/refinery.py" in pk and "C-2.1" in pk and "S2.1" in pk and "def admit(records, task, workspace) -> dict" in pk
    assert "last = [r for r" not in pk and "return bool(last" not in pk
    assert "do not read the old" in pk.lower() or "from the clauses and specs" in pk.lower()


def test_the_behaviour_diff_runs_per_public_typed_function_and_records_counterexamples():
    """C-8.2 — one diffbehavior run per typed public function through the injected runner;
    counterexamples parsed out of its output; untyped or private functions are skipped."""
    from lib.regen import diff_report
    calls = []

    def runner(argv, cwd):
        calls.append(argv)
        if "new.admit" in argv[-1] or "old.admit" in argv[-1]:
            return 1, ("Given: (records=[], task='T1', workspace='w')\n"
                       "  old.admit : returns False\n  new.admit : returns True\n")
        return 0, "No differences found. (attempted 100 iterations)"
    sigs = {"admit": "def admit(records: list, task: str, workspace: str) -> bool",
            "first_failure": "def first_failure(items: list) -> str",
            "_helper": "def _helper(x: int) -> int",
            "untyped": "def untyped(a, b)"}
    rep = diff_report(sigs, old="old", new="new", runner=runner, cwd="w", timeout=20)
    assert [c["function"] for c in rep] == ["admit", "first_failure"]
    assert rep[0]["counterexamples"] == [{"given": "(records=[], task='T1', workspace='w')", "old": "returns False", "new": "returns True"}]
    assert rep[1]["counterexamples"] == []
    assert len(calls) == 2 and all(a[0] == "crosshair" and a[1] == "diffbehavior" for a in calls)
    assert any("--per_condition_timeout" in a and "20" in a for a in calls)


def test_equivalence_needs_green_specs_no_counterexample_and_mutation_score_not_under_the_original():
    """C-8.3 — three conditions; the first failing one is the reason; per clause the new score
    must not be under the old."""
    from lib.regen import equivalence_verdict
    assert equivalence_verdict(specs_green=True, counterexamples=[], score_new={"C-2.1": 0.8}, score_old={"C-2.1": 0.7}) == (True, "equivalent")
    assert equivalence_verdict(specs_green=False, counterexamples=[], score_new={}, score_old={}) == (False, "specs red")
    assert equivalence_verdict(specs_green=True, counterexamples=[{"function": "admit"}], score_new={}, score_old={}) == (False, "counterexample in admit")
    assert equivalence_verdict(specs_green=True, counterexamples=[], score_new={"C-2.1": 0.6}, score_old={"C-2.1": 0.7}) == (False, "C-2.1 mutation score 0.60 under 0.70")
    assert equivalence_verdict(specs_green=True, counterexamples=[], score_new={}, score_old={"C-2.1": 0.7}) == (False, "C-2.1 mutation score 0.00 under 0.70")
