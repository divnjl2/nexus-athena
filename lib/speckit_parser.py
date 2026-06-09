"""
Athena speckit_parser — Spec-Kit tasks.md -> Plan AST (the PRIMARY front, §5).

Used when ATHENA_SPECKIT=on. Reads the tasks.md the Athena preset emits (strict
checklist with [P]/[US] markers + Checkpoint + per-task success_check) into the shared
lib.ast.Plan. Schema is documented in skills/speckit-tasks-format/SKILL.md and pinned by
a golden test (test_speckit_parser.py::test_golden_ast) so Spec-Kit format drift fails
loudly (v2 §10 top risk).

Mapping (§5):
  ## Phase N: <name>     -> Phase; key: "User Story k" -> "USk", else slugified name
  - [ ] T001 [P] [US1] d -> Task(id=T001, parallel=[P] present, title=d w/o markers)
    - success_check: `c` -> Task.success_check  (from the preset; falls back to Checkpoint)
  **Checkpoint:** `c`    -> Phase.checkpoint
  Setup/Foundational phases block every US phase; Polish blocks on all US phases.
"""
from __future__ import annotations

import re

from lib.ast import Task, Phase, Plan, ParseError


class SpecKitParseError(ParseError):
    """Spec-Kit tasks.md schema violated — reject BEFORE compilation."""


_TITLE_RE = re.compile(r"^#\s+Tasks?:\s*(.+?)\s*$")
_PHASE_RE = re.compile(r"^##\s+Phase\s+\d+:\s*(.+?)\s*$")
_TASK_RE = re.compile(r"^-\s*\[[ x]\]\s*(T\d+)\s+(.+?)\s*$")
_GOAL_RE = re.compile(r"^\*\*Goal:\*\*\s*(.+?)\s*$")
_CHECKPOINT_RE = re.compile(r"^\*\*Checkpoint:\*\*\s*`?(.+?)`?\s*$")
_SC_RE = re.compile(r"^\s+-\s*success_check:\s*`?(.+?)`?\s*$")
_MARKER_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")   # \s* so a bare trailing [P] is still consumed
_US_RE = re.compile(r"US\d+")


def _phase_key(name: str) -> str:
    m = re.search(r"user\s+story\s+(\d+)", name, re.I)
    if m:
        return f"US{m.group(1)}"
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "phase"


def parse(text: str) -> Plan:
    title = ""
    phases_raw: list[dict] = []
    cur: dict | None = None
    cur_task: dict | None = None

    def flush_task():
        nonlocal cur_task
        if cur_task is not None and cur is not None:
            cur["tasks"].append(cur_task)
        cur_task = None

    def flush_phase():
        nonlocal cur
        if cur is not None:
            flush_task()
            phases_raw.append(cur)
        cur = None

    for raw in text.splitlines():
        mt = _TITLE_RE.match(raw)
        if mt and not title:
            title = mt.group(1); continue
        mp = _PHASE_RE.match(raw)
        if mp:
            flush_phase()
            name = mp.group(1)
            cur = {"name": name, "key": _phase_key(name), "goal": "", "checkpoint": "", "tasks": []}
            continue
        if cur is None:
            continue
        mg = _GOAL_RE.match(raw)
        if mg:
            cur["goal"] = mg.group(1); continue
        mc = _CHECKPOINT_RE.match(raw)
        if mc:
            cur["checkpoint"] = mc.group(1); continue
        mk = _TASK_RE.match(raw)
        if mk:
            flush_task()
            rest = mk.group(2)
            parallel = False
            while True:
                mm = _MARKER_RE.match(rest)
                if not mm:
                    break
                if mm.group(1).strip() == "P":
                    parallel = True
                rest = mm.group(2)            # strip [P]/[US1]/[Story] markers from the title
            task_title = rest.strip()    # NOT `title` — that is the feature title in this scope
            if not task_title:
                raise SpecKitParseError(f"task {mk.group(1)}: empty title after stripping markers")
            cur_task = {"id": mk.group(1), "title": task_title, "parallel": parallel, "sc": ""}
            continue
        ms = _SC_RE.match(raw)
        if ms and cur_task is not None:
            cur_task["sc"] = ms.group(1); continue

    flush_phase()

    if not title:
        raise SpecKitParseError("missing '# Tasks: <feature>' title")

    # build Tasks (success_check from preset, else phase Checkpoint fallback)
    seen: set[str] = set()
    built: list[dict] = []
    for p in phases_raw:
        tasks: list[Task] = []
        for td in p["tasks"]:
            sc = (td["sc"].strip() or p["checkpoint"].strip())
            if not sc:
                raise SpecKitParseError(
                    f"task {td['id']}: no success_check (preset) and phase {p['key']} has no Checkpoint"
                )
            if td["id"] in seen:
                raise SpecKitParseError(f"duplicate task id {td['id']}")
            seen.add(td["id"])
            # autonomy intentionally omitted in Spec-Kit v2 (routing deferred to executor layer)
            tasks.append(Task(id=td["id"], title=td["title"], success_check=sc, parallel=td["parallel"]))
        if tasks:                              # skip narrative-only phases (no dangling epic)
            built.append({**p, "tasks": tuple(tasks)})

    if not built:
        raise SpecKitParseError("no phases with tasks parsed")

    keys = [b["key"] for b in built]
    blockers = tuple(dict.fromkeys(k for k in keys if k in ("setup", "foundational")))
    us_keys = tuple(dict.fromkeys(k for k in keys if _US_RE.fullmatch(k)))   # dedup -> no duplicate deps

    phases: list[Phase] = []
    for b in built:
        key = b["key"]
        if _US_RE.fullmatch(key):
            deps = blockers
        elif key == "polish":
            deps = blockers + us_keys
        elif key == "foundational":
            deps = ("setup",) if "setup" in keys else ()
        else:
            deps = ()
        deps = tuple(d for d in deps if d != key)   # no self-edge
        phases.append(Phase(
            key=key, title=b["name"], goal=b["goal"],
            depends_on=deps, checkpoint=b["checkpoint"], tasks=b["tasks"],
        ))

    return Plan(title=title, overview="", out_of_scope=(), phases=tuple(phases))
