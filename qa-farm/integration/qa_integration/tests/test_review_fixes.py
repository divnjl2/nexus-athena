"""Regression tests for bugs found by the code-reviewer pass on the first draft of
qa_integration: a dotfile glob bug, non-deterministic overlapping-boundary attribution, a
probe exception that skipped remaining dependencies, and a coverage gate that silently
passed with zero declared boundaries."""
from qa_integration.config import Config, is_compose_or_fixture_change
from qa_integration.primitives.coverage_parse_integration import parse_coverage_text
from qa_integration.primitives.dependency_health_probe import probe_all
from qa_integration.tools.integration_coverage_gate import integration_coverage_gate


def test_dotfile_compose_pattern_matches_despite_leading_dot():
    # `.env.test` is one of the four default compose_fixture_globs (R1.3/EC-2) — a naive
    # `str.lstrip("./")` treats its argument as a character set and strips the leading '.',
    # silently defeating the match. Must match exactly, unmodified.
    cfg = Config()
    assert is_compose_or_fixture_change(".env.test", cfg) is True
    assert is_compose_or_fixture_change("dir/.env.test", cfg) is False   # not the same glob


COBERTURA_OVERLAP = ('<coverage><packages><package><classes>'
                     '<class filename="services/billing/handler.py"><lines>'
                     '<line number="1" hits="1"/><line number="2" hits="1"/>'
                     '</lines></class></classes></package></packages></coverage>')


def test_overlapping_boundaries_attribute_to_the_most_specific_prefix():
    # "billing" ("services/billing/") is more specific than "core" ("services/"); the fully
    # covered file must be attributed to "billing", REGARDLESS of dict insertion order.
    core_first = {"core": ["services/"], "billing": ["services/billing/"]}
    billing_first = {"billing": ["services/billing/"], "core": ["services/"]}

    r1 = parse_coverage_text(COBERTURA_OVERLAP, core_first)
    r2 = parse_coverage_text(COBERTURA_OVERLAP, billing_first)

    for r in (r1, r2):
        assert r["boundaries"]["billing"]["line"] == 1.0
        assert r["boundaries"]["billing"]["has_tests"] is True
        assert r["boundaries"]["core"]["has_tests"] is False   # not double-credited


def test_probe_exception_other_than_timeout_is_recorded_unhealthy_not_raised():
    # A real prober can raise ConnectionError/OSError/etc, not just TimeoutError. That must
    # be recorded as an unhealthy result — and MUST NOT abort probing of the remaining
    # declared dependencies (R2.1: every dependency is probed, none skipped).
    def probe(name, timeout_s):
        if name == "redis":
            raise ConnectionError("connection refused")
        return True

    results = probe_all(["postgres", "redis", "service_b"], probe=probe, clock=lambda: 0.0)
    by_name = {r.name: r for r in results}
    assert set(by_name) == {"postgres", "redis", "service_b"}    # nothing skipped
    assert by_name["redis"].healthy is False
    assert "connection refused" in by_name["redis"].detail
    assert by_name["postgres"].healthy is True
    assert by_name["service_b"].healthy is True                  # probing continued past redis


def test_coverage_gate_fails_closed_on_zero_declared_boundaries():
    # An empty/missing boundary declaration must never be treated as "nothing to check ->
    # pass" (the same "silence never becomes trust" rule as the dependency-health gate).
    r = integration_coverage_gate({})
    assert r.passed is False
    assert r.failing_boundary is None
    assert "no boundaries declared" in r.detail
