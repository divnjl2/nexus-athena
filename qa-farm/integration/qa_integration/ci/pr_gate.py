"""CI: aggregate the tool results into a single blocking status. Any FAIL → non-zero exit,
which is what prevents the merge (R7.1)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateStatus:
    passed: bool
    exit_code: int
    failing: tuple[str, ...]


def aggregate(results) -> GateStatus:
    """`results` = iterable of (name, passed_bool)."""
    failing = tuple(name for name, ok in results if not ok)
    passed = not failing
    return GateStatus(passed=passed, exit_code=0 if passed else 1, failing=failing)
