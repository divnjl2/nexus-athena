"""Proves the integration coverage gate (plan T2.4 · scenarios S3.1/S3.2)."""
from qa_integration.tools.integration_coverage_gate import integration_coverage_gate


def test_below_boundary_threshold_blocks():
    cov = {"boundary_a": {"line": 0.55, "branch": 0.5, "delta": None}}
    r = integration_coverage_gate(cov)
    assert r.passed is False
    assert r.failing_boundary == "boundary_a"


def test_zero_coverage_new_boundary_blocks():
    cov = {"boundary_new": {"line": 0.0, "branch": 0.0, "delta": None}}
    r = integration_coverage_gate(cov)
    assert r.passed is False
    assert r.failing_boundary == "boundary_new"
    assert "hard block" in r.detail


def test_passes_when_all_boundaries_meet_threshold():
    cov = {"boundary_a": {"line": 0.9, "branch": 0.8, "delta": 0.01},
           "boundary_b": {"line": 0.8, "branch": 0.7, "delta": 0.0}}
    assert integration_coverage_gate(cov).passed is True
