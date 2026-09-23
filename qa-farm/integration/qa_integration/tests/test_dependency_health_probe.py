"""Proves the dependency_health_probe L0 primitive (plan T1.4)."""
from qa_integration.primitives.dependency_health_probe import probe_all, probe_dependency


def test_healthy_dependency_reports_ok():
    r = probe_dependency("postgres", probe=lambda name, timeout_s: True, clock=lambda: 0.0)
    assert r.healthy is True and r.name == "postgres"


def test_unhealthy_dependency_reports_unhealthy():
    r = probe_dependency("redis", probe=lambda name, timeout_s: False, clock=lambda: 0.0)
    assert r.healthy is False and r.detail == "unhealthy"


def test_timeout_counts_as_failure_not_skip():
    def probe(name, timeout_s):
        raise TimeoutError()
    r = probe_dependency("service_b", probe=probe, clock=lambda: 0.0, timeout_s=3.0)
    assert r.healthy is False
    assert "timed out" in r.detail


def test_probe_all_probes_every_declared_dependency():
    results = probe_all(["postgres", "redis"], probe=lambda name, timeout_s: True, clock=lambda: 0.0)
    assert {r.name for r in results} == {"postgres", "redis"}
    assert all(r.healthy for r in results)
