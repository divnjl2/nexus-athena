"""Proves the dependency-health gate (plan T2.3 · scenarios S2.1/S2.2/S2.3)."""
from qa_integration.tools.dependency_health_gate import dependency_health_gate


def test_all_deps_probed_before_run():
    calls = []

    def probe(name, timeout_s):
        calls.append(name)
        return True

    r = dependency_health_gate(["postgres", "redis", "service_b"], probe=probe, clock=lambda: 0.0)
    assert set(calls) == {"postgres", "redis", "service_b"}     # every declared dep probed
    assert set(r.probed) == {"postgres", "redis", "service_b"}
    assert r.passed is True


def test_down_dependency_fails_loud():
    def probe(name, timeout_s):
        return name != "redis"

    r = dependency_health_gate(["postgres", "redis", "service_b"], probe=probe, clock=lambda: 0.0)
    assert r.passed is False
    assert r.failing == ("redis",)
    assert "redis" in r.detail
    # the healthy deps are still reported probed — nothing was silently skipped
    assert set(r.probed) == {"postgres", "redis", "service_b"}


def test_health_probe_timeout_is_failure():
    def probe(name, timeout_s):
        if name == "redis":
            raise TimeoutError()
        return True

    r = dependency_health_gate(["postgres", "redis"], probe=probe, clock=lambda: 0.0)
    assert r.passed is False
    assert "redis" in r.failing
