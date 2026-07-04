"""L1: integration coverage gate. coverage_parse_integration output + config threshold →
PASS/FAIL naming the failing boundary. A boundary at 0% is ALWAYS a hard block, never "no
data → pass" (EC-3/R3.2). Policy lives here; the L0 primitive stays decision-free."""
from __future__ import annotations

from dataclasses import dataclass

from qa_integration.config import Config


@dataclass(frozen=True)
class CoverageGateResult:
    passed: bool
    failing_boundary: str | None
    detail: str


def integration_coverage_gate(boundaries_cov: dict, *, cfg=None) -> CoverageGateResult:
    cfg = cfg or Config()
    # Fail closed: no declared boundaries is a misconfiguration, never a silent "nothing to
    # check -> pass" — the same "silence never becomes trust" rule design.md applies to
    # declared dependencies applies here to declared boundaries.
    if not boundaries_cov:
        return CoverageGateResult(
            False, None, "no boundaries declared — cannot verify integration coverage")
    for boundary in sorted(boundaries_cov):
        cov = boundaries_cov[boundary]
        if cov["line"] == 0.0:                                                     # R3.2
            return CoverageGateResult(False, boundary,
                                      f"{boundary}: 0% integration coverage — hard block")
        if cov["line"] < cfg.boundary_coverage_threshold:                          # R3.1
            return CoverageGateResult(
                False, boundary,
                f'{boundary}: {cov["line"]:.0%} < {cfg.boundary_coverage_threshold:.0%}')
    return CoverageGateResult(True, None, "integration coverage gate passed")
