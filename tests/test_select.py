"""v3.15 selection — several attempts are chosen among by behaviour, not by order or text.

Executable spec of C-5.8 in features/executor-layer/contract.md.
"""
from __future__ import annotations


def test_attempts_are_clustered_by_behaviour_and_the_largest_green_cluster_wins():
    """C-5.8 — attempts group by (which checks passed, normalised patch); among green
    clusters the largest wins, the quicker representative on a tie; short of green the
    largest cluster with the most passed checks; one representative per cluster is kept for
    review; whitespace and comment differences do not split a cluster."""
    from lib.select import cluster_attempts, normalize_source, select_attempt
    a = "def f(x):\n    return x + 1  # add\n"
    b = "def f(x):\n\n    return x+1\n"                 # same program, different spacing/comment
    c = "def f(x):\n    return x + 2\n"
    assert normalize_source(a) == normalize_source(b) != normalize_source(c)
    assert normalize_source("def broken(:\n") == "def broken(:\n"      # unparsable stays as is

    checks_ok = [{"cmd": "t1", "exit": 0}, {"cmd": "t2", "exit": 0}]
    checks_half = [{"cmd": "t1", "exit": 0}, {"cmd": "t2", "exit": 1}]
    checks_none = [{"cmd": "t1", "exit": 1}, {"cmd": "t2", "exit": 1}]
    attempts = [
        {"index": 0, "landed": True, "green": True, "checks": checks_ok, "duration_ms": 90,
         "sources": {"lib/x.py": a}},
        {"index": 1, "landed": True, "green": True, "checks": checks_ok, "duration_ms": 50,
         "sources": {"lib/x.py": b}},                                  # same cluster as 0
        {"index": 2, "landed": True, "green": True, "checks": checks_ok, "duration_ms": 10,
         "sources": {"lib/x.py": c}},                                  # a different green program
        {"index": 3, "landed": True, "green": False, "checks": checks_half, "duration_ms": 40,
         "sources": {"lib/x.py": "def f(x):\n    return 0\n"}},
        {"index": 4, "landed": False, "green": False, "checks": checks_none, "duration_ms": 5,
         "sources": {}},
    ]
    clusters = cluster_attempts(attempts)
    sizes = sorted(len(cl["members"]) for cl in clusters)
    assert sizes == [1, 1, 1, 2]
    big = next(cl for cl in clusters if len(cl["members"]) == 2)
    assert set(big["members"]) == {0, 1} and big["green"] is True
    assert big["representative"] == 1, "the quicker member represents the cluster"

    pick = select_attempt(attempts)
    assert pick["index"] == 1 and pick["cluster_size"] == 2
    assert [r["index"] for r in pick["representatives"]] == [1, 2, 3, 4] or \
        set(r["index"] for r in pick["representatives"]) == {1, 2, 3, 4}
    assert pick["green_clusters"] == 2

    red_only = [x for x in attempts if not x["green"]]
    pick = select_attempt(red_only)
    assert pick["index"] == 3 and pick["green_clusters"] == 0
    assert select_attempt([attempts[4]])["index"] is None
    assert select_attempt([])["index"] is None
