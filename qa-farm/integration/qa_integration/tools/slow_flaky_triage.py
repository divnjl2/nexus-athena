"""L1: slow/flaky integration triage. An over-budget test is quarantined (never blocking); a
test is flaky ONLY when it both passes and fails on the SAME commit across reruns; a
consistent failure always stays red — flaky is a separate channel, never a mask."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuarantineEntry:
    test_id: str
    reason: str            # "slow" | "flaky"
    duration_s: float | None = None


def quarantine_if_slow(test_id, duration_s, *, budget_s: float) -> QuarantineEntry | None:
    """R5.1: over-budget → quarantined as slow; the rest of the run is not blocked by it."""
    if duration_s > budget_s:
        return QuarantineEntry(test_id=test_id, reason="slow", duration_s=duration_s)
    return None


@dataclass(frozen=True)
class Verdict:
    test_id: str
    kind: str              # "flaky" | "pass" | "fail"


def classify(test_id, commit, results) -> Verdict:
    """`results` = booleans (pass/fail) from reruns on ONE commit hash (R5.2)."""
    if not results:
        raise ValueError("classify requires at least one rerun result")
    passes = any(results)
    fails = any(not r for r in results)
    if passes and fails:
        return Verdict(test_id, "flaky")
    return Verdict(test_id, "pass" if passes else "fail")


def build_status(verdicts) -> dict:
    """R5.3: a consistent (real) failure still fails the build; flaky is tracked apart and
    never masks it."""
    flaky = [v.test_id for v in verdicts if v.kind == "flaky"]
    failures = [v.test_id for v in verdicts if v.kind == "fail"]
    return {"build_passed": not failures, "flaky": flaky, "failures": failures}
