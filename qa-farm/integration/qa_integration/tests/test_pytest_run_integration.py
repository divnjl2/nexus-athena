"""Proves the pytest_run_integration L0 primitive (plan T1.1)."""
from qa_integration.primitives.pytest_run_integration import pytest_run_integration


class _Proc:
    def __init__(self, rc): self.returncode = rc


def test_passing_run_reports_passed_with_duration():
    ticks = iter([0.0, 2.5])
    r = pytest_run_integration(["tests/test_x.py"], dependencies=["postgres"],
                               run=lambda a, c: _Proc(0), clock=lambda: next(ticks))
    assert r.passed and r.ran and r.exit_code == 0
    assert r.duration_s == 2.5
    assert r.dependencies == ("postgres",)


def test_failing_run_reports_not_passed_but_ran():
    r = pytest_run_integration(["x"], run=lambda a, c: _Proc(1), clock=lambda: 0.0)
    assert r.passed is False and r.ran is True


def test_no_tests_collected_is_not_ran():
    r = pytest_run_integration(["x"], run=lambda a, c: _Proc(5), clock=lambda: 0.0)
    assert r.ran is False and r.passed is False
