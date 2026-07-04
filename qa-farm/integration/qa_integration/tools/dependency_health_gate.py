"""L1: dependency-health gate. Probes every declared dependency BEFORE any integration test
result is trusted; a down or timed-out dependency fails the gate loudly and names itself —
never a silent skip of the tests that depend on it."""
from __future__ import annotations

from dataclasses import dataclass

from qa_integration.primitives.dependency_health_probe import probe_all


@dataclass(frozen=True)
class DependencyGateResult:
    passed: bool
    probed: tuple[str, ...]
    failing: tuple[str, ...]
    detail: str


def dependency_health_gate(dependencies, *, probe=None, clock=None, timeout_s: float = 5.0) -> DependencyGateResult:
    results = probe_all(dependencies, probe=probe, clock=clock, timeout_s=timeout_s)
    probed = tuple(r.name for r in results)                     # R2.1: ALL probed, always
    failing = tuple(r.name for r in results if not r.healthy)   # R2.2/R2.3: down or timeout = fail
    if failing:
        return DependencyGateResult(False, probed, failing,
                                    f"dependency unhealthy: {', '.join(failing)}")
    return DependencyGateResult(True, probed, (), "all dependencies healthy")
