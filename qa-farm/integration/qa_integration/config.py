"""Policy for the Integration-QA microservice. Thresholds, and the compose/shared-fixture
path classes live here (L1 reads them); the L0 primitives stay policy-free. Defaults mirror
../design.md's config block (`qa_integration.toml`)."""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class Config:
    boundary_coverage_threshold: float = 0.75
    health_timeout_s: float = 5.0
    budget_seconds: int = 600
    slow_test_budget_s: float = 30.0
    rerun: int = 2
    compose_fixture_globs: tuple[str, ...] = (
        "docker-compose.yml", "docker-compose.override.yml", "**/conftest.py", ".env.test",
        "pytest.ini",
    )


def _match(path: str, pattern: str) -> bool:
    """Glob match with '**' meaning any-depth. Deterministic, stdlib-only."""
    p = path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return p == base or p.startswith(base + "/")
    if pattern.startswith("**/"):
        suffix = pattern[3:]
        return p == suffix or p.endswith("/" + suffix)
    return fnmatch(p, pattern.replace("**", "*"))


def is_compose_or_fixture_change(path: str, cfg: Config) -> bool:
    """EC-2/R1.3: a docker-compose or shared integration-fixture edit invalidates impact
    analysis and must force the full run — under-selection, not over-selection, is the risk."""
    return any(_match(path, pat) for pat in cfg.compose_fixture_globs)
