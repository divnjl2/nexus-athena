"""Proves the isolation manager (plan T4.1 · scenarios S4.1/S4.2/S4.3)."""
from qa_integration.tools.isolation_manager import (
    check_fingerprint, reset_after_test, schedule_boundary,
)


def test_rollback_or_recreate_between_tests():
    calls = []
    r = reset_after_test("tests/test_a.py::t1", reset=lambda: calls.append(1) or True)
    assert r.reset is True and calls == [1]
    assert r.strategy == "rollback"


def test_cross_test_bleed_detected_blocks():
    check = check_fingerprint(
        "tests/test_b.py::t2", expected_fingerprint="clean",
        actual_fingerprint="dirty:t1-leftover", prior_test_id="tests/test_a.py::t1")
    assert check.ok is False
    assert "tests/test_a.py::t1" in check.colliding_tests
    assert "tests/test_b.py::t2" in check.colliding_tests


def test_unresettable_dependency_forces_serial():
    d = schedule_boundary("boundary_sandbox", can_reset=False)
    assert d.serial is True
    d2 = schedule_boundary("boundary_a", can_reset=True)
    assert d2.serial is False
