"""
Athena plan_parser — strict canonical plan.md -> Plan AST (the FALLBACK front, §2/§6).

Used when ATHENA_SPECKIT=off. Emits the shared `lib.ast.Plan`; the compiler knows only
the AST. Stdlib only, line-oriented state machine. Any deviation is rejected HERE.
Canonical format documented in skills/plan-format/SKILL.md.
"""
from __future__ import annotations

import re

from lib.ast import Task, Phase, Plan, ParseError


class PlanParseError(ParseError):
    """Canonical plan.md format violated — reject BEFORE compilation."""


_PHASE_RE = re.compile(r"^##\s+Phase\s+(\d+):\s*(.+?)\s*$")
# `- [ ] T1.1 [P] title`  — [P] optional parallel marker; both [ ] and [x] match
_TASK_RE = re.compile(r"^-\s*\[[ x]\]\s*(T\d+\.\d+)\s+(.+?)\s*$")
_KV_RE = re.compile(r"^\s+-\s*(success_check|files|autonomy):\s*`?(.+?)`?\s*$")
_DEP_RE = re.compile(r"^\*\*Depends on:\*\*\s*(.+?)\s*$")
_GOAL_RE = re.compile(r"^\*\*Goal:\*\*\s*(.+?)\s*$")
_AUTONOMY_ALLOWED = frozenset({"high", "low", "default"})


def parse(text: str) -> Plan:
    """Line-oriented state-machine parser. Deterministic, stdlib-only."""
    lines = text.splitlines()
    title = ""
    overview_lines: list[str] = []
    out_of_scope: list[str] = []
    phases: list[Phase] = []

    section = "preamble"            # preamble|overview|scope|phase
    cur_idx: int | None = None
    cur_title = ""
    cur_goal = ""
    cur_deps: tuple[str, ...] = ()
    cur_tasks: list[Task] = []
    cur_task: dict | None = None

    def flush_task():
        nonlocal cur_task
        if cur_task is None:
            return
        if not cur_task.get("success_check", "").strip():
            raise PlanParseError(f"task {cur_task['id']} missing success_check")
        autonomy = cur_task.get("autonomy", "").strip() or "default"
        if autonomy not in _AUTONOMY_ALLOWED:
            raise PlanParseError(
                f"task {cur_task['id']}: autonomy must be high/low/default (got {autonomy!r})"
            )
        cur_tasks.append(Task(
            id=cur_task["id"],
            title=cur_task["title"],
            success_check=cur_task["success_check"],
            files=tuple(f.strip() for f in cur_task.get("files", "").split(",") if f.strip()),
            parallel=cur_task.get("parallel", False),
            autonomy=autonomy,
        ))
        cur_task = None

    def flush_phase():
        nonlocal cur_idx
        if cur_idx is None:
            return
        flush_task()
        phases.append(Phase(
            key=f"phase{cur_idx}",
            title=cur_title,
            goal=cur_goal,
            depends_on=cur_deps,
            tasks=tuple(cur_tasks),
        ))
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
                    cur_deps = tuple(f"phase{x}" for x in re.findall(r"Phase\s+(\d+)", dep))
                continue
            mt = _TASK_RE.match(raw)
            if mt:
                flush_task()
                remainder = mt.group(2)
                parallel = False
                mp = re.match(r"^\[P\]\s*(.*)$", remainder)   # [P] only as the FIRST marker (fallback path)
                if mp:
                    parallel = True
                    remainder = mp.group(1)
                task_title = remainder.strip()    # NOT `title` — that is the plan title in this scope
                if not task_title:
                    raise PlanParseError(f"task {mt.group(1)}: empty title")
                cur_task = {"id": mt.group(1), "title": task_title, "parallel": parallel}
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
