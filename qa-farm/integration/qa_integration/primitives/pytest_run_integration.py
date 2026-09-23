"""L0: run a pytest node set against a live dependency stack → a structured result. The
subprocess runner and clock are injected so the primitive is deterministic and unit-testable
without spawning pytest or real containers."""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass

# pytest exit codes we care about: 0 = all passed, 1 = tests failed, 5 = no tests collected.
NO_TESTS = 5


@dataclass(frozen=True)
class IntegrationRunResult:
    passed: bool
    exit_code: int
    ran: bool           # False when nothing was collected (exit 5) — not the same as "passed"
    duration_s: float
    nodes: tuple[str, ...]
    dependencies: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def pytest_run_integration(nodes, *, dependencies=(), cwd: str = ".", run=None, clock=None) -> IntegrationRunResult:
    run = run or _default_run
    clock = clock or _default_clock
    t0 = clock()
    proc = run(["python", "-m", "pytest", *nodes, "-q"], cwd)
    dt = clock() - t0
    code = int(proc.returncode)
    return IntegrationRunResult(
        passed=(code == 0),
        exit_code=code,
        ran=(code != NO_TESTS),
        duration_s=round(dt, 4),
        nodes=tuple(nodes),
        dependencies=tuple(dependencies),
    )


def _default_run(argv, cwd):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def _default_clock() -> float:
    import time
    return time.monotonic()
