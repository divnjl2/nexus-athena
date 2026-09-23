"""End-to-end (plan T7.1): change -> select -> dependency health -> coverage gate -> report,
over an in-memory fixture target stack (a real docker-compose up is simulated via injected
probes so the loop is deterministic)."""
import os

from qa_integration.ci.pr_gate import aggregate
from qa_integration.tools.dependency_health_gate import dependency_health_gate
from qa_integration.tools.integration_coverage_gate import integration_coverage_gate
from qa_integration.tools.report import build_metrics, write_report
from qa_integration.tools.run_changed_integration_tests import select_integration_tests


def test_e2e_change_select_health_gate_report(tmp_path):
    # 1) change -> select the boundary-scoped tests
    boundary_map = {"boundary_a": ["service_a/handler.py"]}
    test_map = {"boundary_a": ["tests/test_a_integration.py"]}
    sel = select_integration_tests(["service_a/handler.py"], boundary_map, test_map)
    assert sel.tests == ("tests/test_a_integration.py",)

    # 2) dependency health -- every declared dependency must be probed and healthy
    health = dependency_health_gate(["postgres", "redis"],
                                    probe=lambda name, timeout_s: True, clock=lambda: 0.0)
    assert health.passed is True

    # 3) coverage gate -- boundary_a coverage is below the bar -> FAIL, named
    cov = {"boundary_a": {"line": 0.55, "branch": 0.5, "delta": None}}
    gate = integration_coverage_gate(cov)
    assert gate.passed is False and gate.failing_boundary == "boundary_a"

    # 4) aggregate -> blocking status prevents merge even though deps were healthy
    status = aggregate([("dependency_health", health.passed), ("coverage", gate.passed)])
    assert status.passed is False and status.exit_code != 0

    # 5) the report is written regardless of the gate outcome
    metrics = build_metrics(passed=1, total=1, boundary_coverage={"boundary_a": 0.55},
                            dependency_health={"postgres": "healthy", "redis": "healthy"},
                            runtime_s=12.0, flaky=0, flaky_total=1)
    junit, allure = write_report(str(tmp_path / "out"),
                                 cases=[{"name": "tests/test_a_integration.py", "passed": True}],
                                 metrics=metrics)
    assert os.path.exists(junit) and os.path.isdir(allure)


def test_e2e_down_dependency_blocks_before_any_test_is_trusted(tmp_path):
    # a declared dependency is unreachable -> the gate fails loud, naming it, BEFORE coverage
    # is even consulted (R2.2) -- integration results are never trusted with a dep down.
    health = dependency_health_gate(["postgres", "redis"],
                                    probe=lambda name, timeout_s: name != "redis",
                                    clock=lambda: 0.0)
    assert health.passed is False and health.failing == ("redis",)

    status = aggregate([("dependency_health", health.passed)])
    assert status.passed is False and status.exit_code != 0
