"""L1: isolation manager. Guarantees no test's dependency state survives into the next test:
reset (rollback/recreate) after each test, a pre-test fingerprint check that blocks the run on
cross-test bleed, and forced serial execution when a dependency cannot be reset."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResetResult:
    test_id: str
    strategy: str          # "rollback" | "recreate"
    reset: bool


def reset_after_test(test_id, *, reset=None, strategy: str = "rollback") -> ResetResult:
    """R4.1: `reset()` performs the actual rollback/recreate — injected (a real transaction
    rollback or fixture recreate in production)."""
    reset = reset or (lambda: True)
    ok = bool(reset())
    return ResetResult(test_id=test_id, strategy=strategy, reset=ok)


@dataclass(frozen=True)
class BleedCheck:
    ok: bool
    colliding_tests: tuple[str, ...]
    detail: str


def check_fingerprint(test_id, *, expected_fingerprint, actual_fingerprint, prior_test_id=None) -> BleedCheck:
    """R4.2/EC-5: compare the pre-test state fingerprint to the expected clean-state
    fingerprint. A mismatch blocks the run and names the colliding tests."""
    if expected_fingerprint == actual_fingerprint:
        return BleedCheck(True, (), "clean state")
    colliding = tuple(t for t in (prior_test_id, test_id) if t)
    return BleedCheck(False, colliding, f"fingerprint mismatch before {test_id}")


@dataclass(frozen=True)
class ScheduleDecision:
    boundary: str
    serial: bool
    detail: str


def schedule_boundary(boundary, *, can_reset: bool) -> ScheduleDecision:
    """R4.3: a boundary whose dependency cannot be reset between tests MUST run serially —
    never in parallel, which would mask bleed instead of preventing it."""
    if not can_reset:
        return ScheduleDecision(boundary, True, f"{boundary}: dependency cannot be reset -> serial")
    return ScheduleDecision(boundary, False, f"{boundary}: dependency resettable -> parallel ok")
