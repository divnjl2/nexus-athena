"""v3.15 the test-writer — candidate reproduction tests are chosen by what they do: they must
be a test, they must fail on the code as it is, and the largest agreeing cluster wins.

Executable spec of C-8.1 in features/executor-layer/contract.md.
"""
from __future__ import annotations


def test_candidate_tests_are_kept_only_when_they_fail_on_the_current_code_and_agree():
    """C-8.1 — a candidate is admissible when it parses, defines exactly one test function
    that names the clause, and its run on the current code is red for a failure (not a
    collection error, not a skip); admissible candidates cluster by normalised source and the
    largest cluster's representative is chosen."""
    from lib.testwriter import admissible, choose_test, test_function_name
    good = ('def test_the_widget_counts_to_three():\n    """C-9.1 — three items count as three."""\n'
            '    from lib.widget import count\n    assert count(["a", "b", "c"]) == 3\n')
    same = ('def test_the_widget_counts_to_three():\n    """C-9.1 — three items count as three."""\n\n'
            '    from lib.widget import count\n    assert count(["a","b","c"]) == 3   # same\n')
    other = ('def test_the_widget_counts_to_three():\n    """C-9.1 — three items count as three."""\n'
            '    from lib.widget import count\n    assert count([]) == 0\n')
    two = good + "\n\ndef test_second():\n    assert True\n"
    noclause = 'def test_x():\n    """something"""\n    assert False\n'
    assert test_function_name(good) == "test_the_widget_counts_to_three"
    assert test_function_name(two) == ""

    failed = {"exit": 1, "tail": "AssertionError: assert 0 == 3\n1 failed in 0.02s"}
    errored = {"exit": 2, "tail": "ImportError: cannot import name 'count'\n1 error in 0.02s"}
    passed = {"exit": 0, "tail": "1 passed in 0.02s"}
    skipped = {"exit": 0, "tail": "1 skipped in 0.02s"}
    assert admissible(good, failed, clause="C-9.1") == ""
    assert "passes" in admissible(good, passed, clause="C-9.1")
    assert "skip" in admissible(good, skipped, clause="C-9.1")
    assert "error" in admissible(good, errored, clause="C-9.1")
    assert "one test" in admissible(two, failed, clause="C-9.1")
    assert "C-9.1" in admissible(noclause, failed, clause="C-9.1")
    assert "parse" in admissible("def (:\n", failed, clause="C-9.1")

    pick = choose_test([
        {"source": good, "run": failed}, {"source": same, "run": failed},
        {"source": other, "run": failed}, {"source": noclause, "run": failed},
        {"source": good, "run": passed},
    ], clause="C-9.1")
    assert pick["source"] == good and pick["cluster_size"] == 2 and pick["admissible"] == 3
    assert pick["rejected"] == 2 and len(pick["representatives"]) == 2
    assert choose_test([{"source": good, "run": passed}], clause="C-9.1")["source"] == ""
