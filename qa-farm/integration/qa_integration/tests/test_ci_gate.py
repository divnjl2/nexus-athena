"""Proves the blocking PR gate + budget guard (plan T6.1/T6.2 · scenarios S7.1/S7.2)."""
from qa_integration.ci.budget import check_budget
from qa_integration.ci.pr_gate import aggregate


def test_pr_gate_blocks_on_fail():
    st = aggregate([("dependency_health", True), ("coverage", False)])
    assert st.passed is False
    assert st.exit_code != 0
    assert "coverage" in st.failing


def test_pr_gate_passes_when_all_green():
    st = aggregate([("dependency_health", True), ("coverage", True)])
    assert st.passed is True and st.exit_code == 0


def test_budget_breach_is_first_class():
    r = check_budget(start=0.0, now=650.0, budget_s=600)
    assert r.breached is True
    assert r.elapsed_s == 650.0          # inspectable result, not an exception or silent pass
