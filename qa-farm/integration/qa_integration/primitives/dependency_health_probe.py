"""L0: probe each declared dependency's health endpoint → healthy/unhealthy + latency, under a
bounded timeout. The prober and clock are injected so the primitive is deterministic and
testable without real network calls or containers."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProbeResult:
    name: str
    healthy: bool
    latency_s: float
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def probe_dependency(name, *, probe=None, clock=None, timeout_s: float = 5.0) -> ProbeResult:
    """`probe(name, timeout_s) -> bool` (or raises `TimeoutError`) is injected — a real
    health-check HTTP/TCP call in production. A timeout is recorded as UNHEALTHY, never
    skipped (R2.3) — a bounded timeout is not the same as "no answer, assume fine"."""
    probe = probe or _default_probe
    clock = clock or _default_clock
    t0 = clock()
    try:
        ok = bool(probe(name, timeout_s))
        dt = clock() - t0
        return ProbeResult(name=name, healthy=ok, latency_s=round(dt, 4),
                           detail="ok" if ok else "unhealthy")
    except TimeoutError:
        dt = clock() - t0
        return ProbeResult(name=name, healthy=False, latency_s=round(dt, 4),
                           detail=f"timed out after {timeout_s}s")
    except Exception as e:
        # R2.1: every declared dependency MUST be probed — a connection error, DNS failure,
        # or any other real-world probe failure must be recorded as unhealthy and must NOT
        # abort probing of the remaining dependencies (probe_all iterates independently).
        dt = clock() - t0
        return ProbeResult(name=name, healthy=False, latency_s=round(dt, 4),
                           detail=f"probe error: {e}")


def probe_all(names, *, probe=None, clock=None, timeout_s: float = 5.0) -> tuple[ProbeResult, ...]:
    """R2.1: every declared dependency is probed — none is skipped, regardless of the others'
    outcome."""
    return tuple(probe_dependency(n, probe=probe, clock=clock, timeout_s=timeout_s) for n in names)


def _default_probe(name, timeout_s):
    raise RuntimeError("wire a real health-check prober in production; inject `probe` in tests")


def _default_clock() -> float:
    import time
    return time.monotonic()
