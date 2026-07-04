"""Proves change-scoped integration selection (plan T2.1/T2.2/T2.5 · scenarios S1.1/S1.2/S1.3)."""
from qa_integration.tools.run_changed_integration_tests import select_integration_tests

BOUNDARY_MAP = {"boundary_a": ["service_a/handler.py"], "boundary_b": ["service_b/handler.py"]}
TEST_MAP = {
    "boundary_a": ["tests/test_a_integration.py"],
    "boundary_b": ["tests/test_b_integration.py"],
}


def test_selects_boundary_scoped_only():
    sel = select_integration_tests(["service_a/handler.py"], BOUNDARY_MAP, TEST_MAP)
    assert sel.tests == ("tests/test_a_integration.py",)
    assert sel.boundaries == ("boundary_a",)
    assert sel.reason == "affected"
    assert "tests/test_b_integration.py" not in sel.tests


def test_no_relevant_change_runs_nothing():
    sel = select_integration_tests(["README.md", "docs/x.md"], BOUNDARY_MAP, TEST_MAP)
    assert sel.tests == ()
    assert sel.reason == "no_relevant_change"
    assert sel.full_run is False


def test_compose_change_full_fallback():
    sel = select_integration_tests(["docker-compose.yml"], BOUNDARY_MAP, TEST_MAP)
    assert sel.full_run is True
    assert sel.reason == "compose_change_full_run"
    assert set(sel.tests) == {"tests/test_a_integration.py", "tests/test_b_integration.py"}
