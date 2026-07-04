"""L2: turn a failed dependency-health probe into a concrete fix target (compose service, env
var, or config key) with file+line, ready for the fix generator."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvIssue:
    dependency: str
    target_kind: str      # "compose_service" | "env_var" | "config_key"
    file: str
    line: int
    detail: str


def find_issue(gate_result, *, locator=None) -> list[EnvIssue]:
    """`gate_result` is a DependencyGateResult (or a dict with a `failing` key). `locator` maps
    a failing dependency name -> {kind, file, line, detail} — injected; a real implementation
    greps docker-compose.yml / .env for the service's block."""
    locator = locator or _default_locator
    failing = gate_result.failing if hasattr(gate_result, "failing") else gate_result["failing"]
    issues = []
    for dep in failing:
        loc = locator(dep)
        issues.append(EnvIssue(dependency=dep, target_kind=loc["kind"], file=loc["file"],
                               line=loc["line"], detail=loc["detail"]))
    return issues


def _default_locator(dep):
    raise RuntimeError("wire a real compose/env locator in production; inject `locator` in tests")
