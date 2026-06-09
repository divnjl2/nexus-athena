"""
Athena plan_parser — strict, deterministic plan.md -> dataclasses.

Line-oriented state-machine parser. Stdlib only. The canonical plan.md format is
the only contract with the LLM planning front (see skills/plan-format/SKILL.md);
any deviation is rejected HERE, before compilation, never "fixed" downstream.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class PlanParseError(ValueError):
    """Canonical format violated — reject BEFORE compilation."""


@dataclass(frozen=True)
class Task:
    id: str                       # "T1.2" — stable, from the document
    title: str
    success_check: str            # mandatory and non-empty
    files: tuple[str, ...] = ()
    autonomy: str = ""            # optional routing hint: "high" -> OpenHands


@dataclass(frozen=True)
class Phase:
    index: int                    # 1-based, from "## Phase N:"
    title: str
    goal: str
    depends_on: tuple[int, ...]   # phase indices
    tasks: tuple[Task, ...]


@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    phases: tuple[Phase, ...]


_PHASE_RE = re.compile(r"^##\s+Phase\s+(\d+):\s*(.+?)\s*$")
# both `- [ ]` and `- [x]` match: checkbox state is cosmetic, bd owns completion state
_TASK_RE = re.compile(r"^-\s*\[[ x]\]\s*(T\d+\.\d+)\s+(.+?)\s*$")
_KV_RE = re.compile(r"^\s+-\s*(success_check|files|autonomy):\s*`?(.+?)`?\s*$")
_DEP_RE = re.compile(r"^\*\*Depends on:\*\*\s*(.+?)\s*$")
_GOAL_RE = re.compile(r"^\*\*Goal:\*\*\s*(.+?)\s*$")
# autonomy is a closed routing vocabulary — reject anything else (argument-injection guard)
_AUTONOMY_ALLOWED = frozenset({"high", "low", ""})


def parse(text: str) -> Plan:
    """Line-oriented state-machine parser. Deterministic, dependency-free."""
    lines = text.splitlines()
    title = ""
    overview_lines: list[str] = []
    out_of_scope: list[str] = []
    phases: list[Phase] = []

    section = "preamble"            # preamble|overview|scope|phase
    cur_idx: int | None = None
    cur_title = ""
    cur_goal = ""
    cur_deps: tuple[int, ...] = ()
    cur_tasks: list[Task] = []
    cur_task: dict | None = None

    def flush_task():
        nonlocal cur_task
        if cur_task is None:
            return
        if not cur_task.get("success_check", "").strip():
            raise PlanParseError(f"task {cur_task['id']} missing success_check")
        autonomy = cur_task.get("autonomy", "").strip()
        if autonomy not in _AUTONOMY_ALLOWED:
            raise PlanParseError(
                f"task {cur_task['id']}: autonomy must be 'high', 'low', or absent (got {autonomy!r})"
            )
        cur_tasks.append(Task(
            id=cur_task["id"],
            title=cur_task["title"],
            success_check=cur_task["success_check"],
            files=tuple(f.strip() for f in cur_task.get("files", "").split(",") if f.strip()),
            autonomy=autonomy,
        ))
        cur_task = None

    def flush_phase():
        nonlocal cur_idx
        if cur_idx is None:
            return
        flush_task()
        phases.append(Phase(cur_idx, cur_title, cur_goal, cur_deps, tuple(cur_tasks)))
        cur_idx = None

    for raw in lines:
        if raw.startswith("# Plan:"):
            title = raw[len("# Plan:"):].strip()
            continue
        if raw.startswith("## Overview"):
            flush_phase(); section = "overview"; continue
        if raw.startswith("## Out of Scope"):
            flush_phase(); section = "scope"; continue

        m = _PHASE_RE.match(raw)
        if m:
            flush_phase()
            section = "phase"
            cur_idx = int(m.group(1)); cur_title = m.group(2)
            cur_goal = ""; cur_deps = (); cur_tasks = []; cur_task = None
            continue

        if section == "overview" and raw.strip():
            overview_lines.append(raw.strip()); continue
        if section == "scope" and raw.strip().startswith("-"):
            out_of_scope.append(raw.strip()[1:].strip()); continue

        if section == "phase":
            mg = _GOAL_RE.match(raw)
            if mg:
                cur_goal = mg.group(1); continue
            md = _DEP_RE.match(raw)
            if md:
                dep = md.group(1).strip()
                if dep.lower() != "none":
                    cur_deps = tuple(
                        int(x) for x in re.findall(r"Phase\s+(\d+)", dep)
                    )
                continue
            mt = _TASK_RE.match(raw)
            if mt:
                flush_task()
                cur_task = {"id": mt.group(1), "title": mt.group(2)}
                continue
            mk = _KV_RE.match(raw)
            if mk and cur_task is not None:
                cur_task[mk.group(1)] = mk.group(2)
                continue

    flush_phase()

    if not title:
        raise PlanParseError("missing '# Plan:' title")
    if not phases:
        raise PlanParseError("no phases parsed")

    # duplicate task ids across the whole plan
    seen: set[str] = set()
    for ph in phases:
        for t in ph.tasks:
            if t.id in seen:
                raise PlanParseError(f"duplicate task id {t.id}")
            seen.add(t.id)

    return Plan(title, " ".join(overview_lines), tuple(out_of_scope), tuple(phases))
