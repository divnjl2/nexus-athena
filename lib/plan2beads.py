"""
Athena plan2beads — DETERMINISTIC compiler: Plan AST -> bd commands.

Invariants (do not break):
  * No LLM calls. Pure AST -> commands transformation.
  * Pure core (compile): no I/O, no time, no randomness. Idempotency via existing_keys.
  * Strict deterministic order: document order + explicit sorted() for edges.
  * External keys (athena:<slug>:...) = upsert mechanism over Beads hash-IDs.

Consumes ONLY lib.ast.Plan — it knows nothing about which parser produced it (toggle §6).
The effectful boundary lives in lib/bd_client.py (the only subprocess site).
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from lib.ast import Plan, Task  # noqa: F401  (Task used for type hints)

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


def _epic_key(slug: str, phase_key: str) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:{phase_key}"


def _task_key(slug: str, t: Task) -> str:
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:{t.id}"


def _issue_body(t: Task) -> str:
    lines = [t.title, "", f"success_check: {t.success_check}"]
    if t.files:
        lines.append("files: " + ", ".join(t.files))
    return "\n".join(lines)


def compile(plan: Plan, *, existing_keys: frozenset[str] = frozenset()) -> CompileResult:
    """
    Pure function: Plan AST (+ set of already-existing external keys) -> deterministic
    list of bd commands. existing_keys empty on first compile; on replan the effectful
    layer fills it so creates/edges already in the graph are skipped (idempotent upsert).

    Idempotency tracks NODE labels only, not edge presence. If a prior run crashed between
    node creates and `bd dep add`, a re-run skips the edge (both endpoints already exist) —
    recover with a manual `bd dep add`. (bd has no edge-existence query to close this.)
    """
    # --- hard validation ---
    phase_keys = {ph.key for ph in plan.phases}
    if len(phase_keys) != len(plan.phases):
        raise CompileError("duplicate phase key")
    for ph in plan.phases:
        if not ph.tasks:
            raise CompileError(f"phase {ph.key!r} has no tasks — dangling epic")
        for d in ph.depends_on:
            if d not in phase_keys:
                raise CompileError(f"phase {ph.key} depends on missing phase {d}")
        for t in ph.tasks:
            if not t.success_check.strip():
                raise CompileError(f"task {t.id} missing success_check")

    slug = _slugify(plan.title)
    if not slug:
        raise CompileError("plan title produces an empty slug — add alphanumeric characters")

    cmds: list[Command] = []
    epic_keys: list[str] = []
    issue_count = 0

    # --- epics + issues, strict document order ---
    for ph in plan.phases:
        ekey = _epic_key(slug, ph.key)
        epic_keys.append(ekey)
        if ekey not in existing_keys:
            desc = ph.goal
            if ph.checkpoint:
                desc = f"{ph.goal}\n\ncheckpoint: {ph.checkpoint}"
            cmds.append(Command((
                "bd", "create", "--type", "epic",
                "--title", ph.title,
                "--label", ekey, "--label", EXTERNAL_KEY_PREFIX,
                "--description", desc,
            )))
        for t in ph.tasks:
            issue_count += 1
            tkey = _task_key(slug, t)
            if tkey in existing_keys:
                continue
            argv = [
                "bd", "create", "--parent", ekey,
                "--title", f"{t.id} {t.title}",
                "--label", tkey, "--label", EXTERNAL_KEY_PREFIX,
            ]
            if t.autonomy and t.autonomy != "default":
                argv += ["--label", f"autonomy:{t.autonomy}"]
            argv += ["--description", _issue_body(t)]
            cmds.append(Command(tuple(argv)))

    # --- intra-phase task ordering: sequential (non-[P]) tasks chain; [P] siblings unordered ---
    for ph in plan.phases:
        prev_seq: str | None = None
        for t in ph.tasks:
            if t.parallel:
                continue  # parallel tasks get no intra-phase edge
            tkey = _task_key(slug, t)
            if prev_seq is not None and not (tkey in existing_keys and prev_seq in existing_keys):
                cmds.append(Command(("bd", "dep", "add", tkey, "--blocked-by", prev_seq)))
            prev_seq = tkey

    # --- inter-phase dependency edges (epic level), CANONICAL sorted order ---
    for ph in plan.phases:
        ekey = _epic_key(slug, ph.key)
        for d in sorted(ph.depends_on):
            dkey = _epic_key(slug, d)
            if ekey in existing_keys and dkey in existing_keys:
                continue
            cmds.append(Command(("bd", "dep", "add", ekey, "--blocked-by", dkey)))

    return CompileResult(tuple(cmds), tuple(epic_keys), issue_count)
