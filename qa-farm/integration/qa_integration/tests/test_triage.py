"""Proves slow/flaky integration triage (plan T4.2 · scenarios S5.1/S5.2/S5.3)."""
from qa_integration.tools.slow_flaky_triage import build_status, classify, quarantine_if_slow


def test_slow_test_quarantined_not_blocking():
    q = quarantine_if_slow("tests/test_slow.py::t", 45.0, budget_s=30.0)
    assert q is not None and q.reason == "slow"
    status = build_status([classify("tests/test_slow.py::t", "c1", [True])])
    assert status["build_passed"] is True        # quarantine does not block the run


def test_same_commit_pass_fail_is_flaky():
    v = classify("tests/test_x.py::t", "abc123", [True, False, True])
    assert v.kind == "flaky"


def test_consistent_failure_stays_red():
    verdicts = [
        classify("t_flaky", "c", [True, False]),
        classify("t_real", "c", [False, False]),
    ]
    status = build_status(verdicts)
    assert status["build_passed"] is False       # a real failure stays red
    assert status["flaky"] == ["t_flaky"]
    assert status["failures"] == ["t_real"]
