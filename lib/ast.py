"""
Athena internal Plan AST — v3+v3.1 — the single contract between front parsers and the compiler.

v3: adds Provenance (spec_version, design_version, run_id) — the provenance graph layer.
v3.1: adds Scenario (EARS->GWT harness) + Task.verifies + Plan.scenarios.

Both parsers (`plan_parser` fallback, `speckit_parser` primary) emit this.
`plan2beads.compile()` consumes ONLY this.

Backward compat: provenance defaults to _EMPTY_PROVENANCE, scenarios defaults to ().
Existing code that builds Plan without provenance continues to work; provenance
graph nodes/edges in plan2beads are only emitted when spec_version is non-empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ParseError(ValueError):
    """A front parser rejected its input before it could become a Plan."""


@dataclass(frozen=True)
class Provenance:
    """Version pins for each LLM-hop output in the planning pipeline.

    spec_version:     sha-prefix of spec.md (the logical ROOT)
    scenario_version: sha-prefix of EARS->GWT output, pinned to spec_version (v3.1)
    design_version:   sha-prefix of design.md (QRSPI output)
    run_id:           unique run identifier (used as OTel trace_id)
    """
    spec_version: str
    scenario_version: str = ""
    design_version: str = ""
    run_id: str = ""


# Sentinel for Plans built without explicit provenance (v2 compat / tests).
_EMPTY_PROVENANCE = Provenance(spec_version="")


@dataclass(frozen=True)
class Scenario:
    """v3.1: Executable requirement scenario derived from EARS acceptance criteria.

    id:               e.g. "S1.2"
    requirement_key:  the spec requirement this verifies
    gwt_text:         human-readable Given-When-Then (versioned artifact)
    run_cmd:          executable command; exit 0 = requirement satisfied
    """
    id: str
    requirement_key: str
    gwt_text: str
    run_cmd: str


@dataclass(frozen=True)
class Task:
    id: str                       # stable, from the source (T1.1 / T001)
    title: str
    success_check: str            # mandatory, non-empty; in v3.1 = run_cmd of bound scenario(s)
    verifies: tuple[str, ...] = ()  # v3.1: scenario ids this task satisfies
    files: tuple[str, ...] = ()
    parallel: bool = False        # from Spec-Kit [P] / "P" in the canonical format
    autonomy: str = "default"     # routing for the (deferred) executor


@dataclass(frozen=True)
class Phase:
    key: str                      # "US1" / "setup" / "phase1"
    title: str
    goal: str
    depends_on: tuple[str, ...] = ()
    checkpoint: str = ""
    tasks: tuple[Task, ...] = ()


@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    phases: tuple[Phase, ...]
    provenance: Provenance = field(default_factory=lambda: _EMPTY_PROVENANCE)  # v3
    scenarios: tuple[Scenario, ...] = ()  # v3.1
