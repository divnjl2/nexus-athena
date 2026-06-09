"""
Athena internal Plan AST — the single contract between front parsers and the compiler.

Both parsers (`plan_parser` for the canonical fallback, `speckit_parser` for Spec-Kit
`tasks.md`) emit this; `plan2beads.compile()` consumes ONLY this. The toggle
(`ATHENA_SPECKIT`) is just a choice of parser — the AST and the compiler never change.
This is the point where the 3-layer <-> 2-layer switch costs nothing (invariant §2).
"""
from __future__ import annotations

from dataclasses import dataclass


class ParseError(ValueError):
    """A front parser rejected its input before it could become a Plan."""


@dataclass(frozen=True)
class Task:
    id: str                       # stable, from the source (T1.1 / T001)
    title: str
    success_check: str            # mandatory, non-empty
    files: tuple[str, ...] = ()
    parallel: bool = False        # from Spec-Kit [P] / "P" in the canonical format
    autonomy: str = "default"     # routing for the (deferred) executor: high -> OpenHands


@dataclass(frozen=True)
class Phase:
    key: str                      # "US1" / "setup" / "phase1"
    title: str
    goal: str
    depends_on: tuple[str, ...] = ()   # keys of other phases
    checkpoint: str = ""          # phase-level gate command (Spec-Kit Checkpoint), optional
    tasks: tuple[Task, ...] = ()


@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    phases: tuple[Phase, ...]
