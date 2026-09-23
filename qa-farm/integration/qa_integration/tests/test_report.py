"""Proves reporting + metrics (plan T5.1/T5.2 · scenarios S6.1/S6.2)."""
import json
import os
import xml.etree.ElementTree as ET

from qa_integration.tools.report import REQUIRED_METRICS, build_metrics, write_report


def test_emits_junit_and_allure(tmp_path):
    cases = [
        {"name": "tests/test_a_integration.py::t1", "passed": True, "duration": 1.1},
        {"name": "tests/test_b_integration.py::t2", "passed": False, "duration": 2.2},
    ]
    metrics = build_metrics(passed=1, total=2, boundary_coverage={"boundary_a": 0.9},
                            dependency_health={"postgres": "healthy"}, runtime_s=3.3,
                            flaky=0, flaky_total=2)
    junit, allure = write_report(str(tmp_path / "out"), cases=cases, metrics=metrics)

    tree = ET.parse(junit)                              # JUnit well-formed + parseable
    assert tree.getroot().tag == "testsuite"
    results = [f for f in os.listdir(allure) if f.endswith("-result.json")]
    assert len(results) == 2
    json.load(open(os.path.join(allure, results[0]), encoding="utf-8"))   # valid JSON


def test_report_has_required_metrics():
    m = build_metrics(passed=8, total=10, boundary_coverage={"boundary_a": 0.85, "boundary_b": 0.7},
                      dependency_health={"postgres": "healthy", "redis": "unhealthy"},
                      runtime_s=120.5, flaky=1, flaky_total=100)
    for field in REQUIRED_METRICS:
        assert field in m
    assert m["pass_rate"] == 0.8
    assert m["flaky_rate"] == 0.01
    assert m["dependency_health"]["redis"] == "unhealthy"
