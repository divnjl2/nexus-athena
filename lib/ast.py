"""
Athena internal Plan AST — v3+v3.1+v3.3 — the single contract between front parsers and the compiler.

v3: adds Provenance (spec_version, design_version, run_id) — the provenance graph layer.
v3.1: adds Scenario (EARS->GWT harness) + Task.verifies + Plan.scenarios.
v3.3: adds Clause/Contract — numbered, immutable-id contract clauses as the spec ROOT.
      A clause is the unit a scenario proves; clause ids branch (supersedes /
      superseded_by) so an OLD reference keeps resolving after the requirement changes.

Both parsers (`plan_parser` fallback, `speckit_parser` primary) emit this.
`plan2beads.compile()` consumes ONLY this.

Backward compat: provenance defaults to _EMPTY_PROVENANCE, scenarios defaults to (),
contract defaults to None. Existing code that builds Plan without provenance continues
to work; provenance graph nodes/edges in plan2beads are only emitted when spec_version
is non-empty, and clause nodes only when a contract is attached.
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
    contract_version: str = ""    # v3.3: structural pin of the clause registry


# Sentinel for Plans built without explicit provenance (v2 compat / tests).
_EMPTY_PROVENANCE = Provenance(spec_version="")


CLAUSE_ACTIVE = "active"
CLAUSE_DRAFT = "draft"            # authored, not yet required to be covered by a spec
CLAUSE_SUPERSEDED = "superseded"  # replaced by >=1 successor; old refs still resolve
CLAUSE_WITHDRAWN = "withdrawn"    # requirement dropped; refs resolve but coverage is dead


@dataclass(frozen=True)
class Clause:
    """v3.3: one numbered contract clause — the atom of the requirement contract.

    The id is IMMUTABLE and never reused. A requirement never changes in place: it is
    superseded by one or more successors, so a reference written months ago
    (`verifies: C-3.2`) still resolves — to C-3.2 itself, or forward to whatever
    replaced it.

    id:             "C-3.2" — stable forever (grammar: <PREFIX><n>(.<n>)*)
    text:           the normative sentence (EARS-shaped: WHEN <event> THE SYSTEM SHALL ...)
    version:        sha16 of THIS clause's normative text — per-clause pin, so editing
                    one clause does not invalidate the pins of every other clause
    status:         active | draft | superseded | withdrawn
    superseded_by:  successor ids (>1 = the clause BRANCHED)
    supersedes:     predecessor ids
    parent:         derived from the id ("C-3.2" -> "C-3"); "" for a top-level clause
    group:          nearest heading text — human grouping only, never identity
    """
    id: str
    text: str
    version: str = ""
    status: str = CLAUSE_ACTIVE
    superseded_by: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    parent: str = ""
    group: str = ""
    tags: tuple[str, ...] = ()
    #: `- see:` targets — other DOCUMENTS this clause leans on (an ADR, a runbook, a note),
    #: each optionally carrying the fingerprint of the version that was reviewed. Kept OUT
    #: of `version`: a reference is context, not the obligation, so citing a design note
    #: must not invalidate the spec that proves the rule.
    refs: tuple[str, ...] = ()
    source_line: int = 0

    @property
    def is_live(self) -> bool:
        """Live = must be proved by >=1 passing executable spec today."""
        return self.status == CLAUSE_ACTIVE


@dataclass(frozen=True)
class Contract:
    """v3.3: the ordered clause registry — the logical root of the provenance graph.

    Immutable + hashable-by-content. `version` pins the STRUCTURE (id+version pairs), so
    it changes when any clause text changes or a clause is added/removed/superseded.
    """
    title: str
    clauses: tuple[Clause, ...] = ()
    version: str = ""

    def __post_init__(self) -> None:
        # frozen dataclass: build the id index once, without breaking immutability
        object.__setattr__(self, "_index", {c.id: c for c in self.clauses})

    def by_id(self, cid: str) -> Clause | None:
        return getattr(self, "_index", {}).get(cid.strip())

    def live(self) -> tuple[Clause, ...]:
        """Clauses that must be proved right now (active; not draft/superseded/withdrawn)."""
        return tuple(c for c in self.clauses if c.is_live)

    def resolve(self, cid: str) -> tuple[Clause, ...]:
        """Follow the supersede chain from an (possibly old) reference to its CURRENT
        clause(s). This is what keeps an old `verifies: C-3.2` working after the
        requirement was rewritten or split. Returns () for an unknown id; returns the
        clause itself when it is still current (or withdrawn — a dead end is still an
        answer, and the caller must be able to tell "gone" from "unknown")."""
        start = self.by_id(cid)
        if start is None:
            return ()
        out: list[Clause] = []
        seen: set[str] = set()
        stack = [start]
        while stack:
            c = stack.pop()
            if c.id in seen:            # cycle guard: a malformed chain must not hang
                continue
            seen.add(c.id)
            successors = [s for s in (self.by_id(x) for x in c.superseded_by) if s is not None]
            if not successors:
                out.append(c)
            else:
                stack.extend(successors)
        return tuple(sorted(out, key=lambda c: c.id))


@dataclass(frozen=True)
class Scenario:
    """v3.1: Executable requirement scenario derived from EARS acceptance criteria.

    id:               e.g. "S1.2"
    requirement_key:  the spec requirement / contract clause id this verifies
    gwt_text:         human-readable Given-When-Then (versioned artifact)
    run_cmd:          executable command; exit 0 = requirement satisfied
    clause_version:   v3.3 — the clause version this spec was written against. When it
                      drifts from the live clause.version, the requirement moved and the
                      executable spec did not follow (`athena contract drift`).
    """
    id: str
    requirement_key: str
    gwt_text: str
    run_cmd: str
    clause_version: str = ""


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
    contract: Contract | None = None      # v3.3 — attached by frontend.parse_with_provenance
