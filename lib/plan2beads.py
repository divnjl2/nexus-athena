"""
Athena plan2beads — DETERMINISTIC compiler: Plan -> bd commands.

Invariants (do not break):
  * No LLM calls. Pure AST -> commands transformation.
  * Pure core (compile): no I/O, no time, no randomness. Idempotency is injected
    via the existing_keys parameter.
  * Strict deterministic order: document order + explicit sorted() for edges.
  * External keys (athena:<slug>:...) = upsert mechanism over Beads hash-IDs.

The effectful boundary lives in lib/bd_client.py (the only subprocess site).
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from lib.plan_parser import Plan, Task

EXTERNAL_KEY_PREFIX = "athena"


class CompileError(ValueError):
    """Compile error (not a warning) — the plan is invalid for the graph."""


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]

    def __str__(self) -> str:
        return " ".join(shlex.quote(a) for a in self.argv)


@dataclass(frozen=True)
class CompileResult:
    commands: tuple[Command, ...]
    epic_keys: tuple[str, ...]
    issue_count: int


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _epic_key(slug: str, idx: int) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:epic{idx}"


def _task_key(slug: str, t: Task) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:{t.id}"


def _issue_body(t: Task) -> str:
    lines = [t.title, "", f"success_check: {t.success_check}"]
    if t.files:
        lines.append("files: " + ", ".join(t.files))
    return "\n".join(lines)


def compile(plan: Plan, *, existing_keys: frozenset[str] = frozenset()) -> CompileResult:
    """
    Pure function: Plan (+ set of already-existing external keys) -> deterministic
    list of bd commands. existing_keys is empty on first compile; on replan the
    effectful layer fills it from `bd list --label athena:*`, and we skip create
    for anything already in the graph (idempotent upsert). The core stays pure.
    """
    # --- hard validation ---
    phase_indices = {ph.index for ph in plan.phases}
    for ph in plan.phases:
        for d in ph.depends_on:
            if d not in phase_indices:
                raise CompileError(f"phase {ph.index} depends on missing phase {d}")
        for t in ph.tasks:
            if not t.success_check.strip():
                raise CompileError(f"task {t.id} missing success_check")

    slug = _slugify(plan.title)
    cmds: list[Command] = []
    epic_keys: list[str] = []
    issue_count = 0

    # --- epics + issues, strict document order ---
    for ph in plan.phases:
        ekey = _epic_key(slug, ph.index)
        epic_keys.append(ekey)
        if ekey not in existing_keys:
            cmds.append(Command((
                "bd", "create", "--type", "epic",
                "--title", f"Phase {ph.index}: {ph.title}",
                "--label", ekey,
                "--description", ph.goal,
            )))
        for t in ph.tasks:
            issue_count += 1
            tkey = _task_key(slug, t)
            if tkey in existing_keys:
                continue  # idempotent — already in the graph
            argv = [
                "bd", "create", "--parent", ekey,
                "--title", f"{t.id} {t.title}",
                "--label", tkey, "--label", EXTERNAL_KEY_PREFIX,
            ]
            if t.autonomy:
                argv += ["--label", f"autonomy:{t.autonomy}"]
            argv += ["--description", _issue_body(t)]
            cmds.append(Command(tuple(argv)))

    # --- dependency edges (epic level), CANONICAL sorted order ---
    for ph in plan.phases:
        for d in sorted(ph.depends_on):
            cmds.append(Command((
                "bd", "dep", "add", _epic_key(slug, ph.index),
                "--blocked-by", _epic_key(slug, d),
            )))

    return CompileResult(tuple(cmds), tuple(epic_keys), issue_count)
