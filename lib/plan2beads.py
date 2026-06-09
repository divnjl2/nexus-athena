"""
Athena plan2beads — ДЕТЕРМИНИРОВАННЫЙ компилятор plan.md -> bd-команды.

Принципы (НЕ нарушать):
  * Никаких LLM-вызовов. Чистая трансформация AST -> команды.
  * Чистое ядро (compile) без I/O, без времени, без случайности.
    Идемпотентность инжектится через параметр existing_keys.
  * Порядок строго детерминированный: document order + явный sorted() для рёбер.
  * Внешние ключи (athena:<slug>:...) = механизм upsert поверх hash-ID Beads.

Раскладка по файлам репо:
  lib/plan_parser.py  <- секция [PARSER]
  lib/plan2beads.py   <- секция [COMPILER]
  lib/bd_client.py    <- секция [EFFECTFUL] (единственное место с subprocess)
  tests/...           <- секция [TESTS]

Здесь всё в одном файле для удобства ревью; при сборке разнести по модулям.
"""

# =============================================================================
# [PARSER]  lib/plan_parser.py
# =============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass


class PlanParseError(ValueError):
    """Канонический формат нарушен — отбиваем ДО компиляции."""


@dataclass(frozen=True)
class Task:
    id: str                       # "T1.2" — стабильный, из документа
    title: str
    success_check: str            # обязателен и непуст
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class Phase:
    index: int                    # 1-based, из "## Phase N:"
    title: str
    goal: str
    depends_on: tuple[int, ...]   # индексы фаз
    tasks: tuple[Task, ...]


@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    phases: tuple[Phase, ...]


_PHASE_RE = re.compile(r"^##\s+Phase\s+(\d+):\s*(.+?)\s*$")
_TASK_RE = re.compile(r"^-\s*\[[ x]\]\s*(T\d+\.\d+)\s+(.+?)\s*$")
_KV_RE = re.compile(r"^\s+-\s*(success_check|files):\s*`?(.+?)`?\s*$")
_DEP_RE = re.compile(r"^\*\*Depends on:\*\*\s*(.+?)\s*$")
_GOAL_RE = re.compile(r"^\*\*Goal:\*\*\s*(.+?)\s*$")


def parse(text: str) -> Plan:
    """Строчный state-machine парсер. Детерминированный, без зависимостей."""
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
        cur_tasks.append(Task(
            id=cur_task["id"],
            title=cur_task["title"],
            success_check=cur_task["success_check"],
            files=tuple(f.strip() for f in cur_task.get("files", "").split(",") if f.strip()),
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

    # дубли task-id по всему плану
    seen: set[str] = set()
    for ph in phases:
        for t in ph.tasks:
            if t.id in seen:
                raise PlanParseError(f"duplicate task id {t.id}")
            seen.add(t.id)

    return Plan(title, " ".join(overview_lines), tuple(out_of_scope), tuple(phases))


# =============================================================================
# [COMPILER]  lib/plan2beads.py  — ЧИСТАЯ ФУНКЦИЯ
# =============================================================================
import shlex
from dataclasses import dataclass as _dc

EXTERNAL_KEY_PREFIX = "athena"


class CompileError(ValueError):
    """Ошибка компиляции (а не warning) — план невалиден для графа."""


@_dc(frozen=True)
class Command:
    argv: tuple[str, ...]

    def __str__(self) -> str:
        return " ".join(shlex.quote(a) for a in self.argv)


@_dc(frozen=True)
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
    Чистая функция: Plan (+ множество уже существующих внешних ключей)
    -> детерминированный список bd-команд.

    existing_keys пуст при первой компиляции; при replan эффектный слой
    заполняет его из `bd list --label athena:*`, и мы пропускаем create
    для всего, что уже в графе (идемпотентный upsert).
    """
    # --- валидация (жёсткая) ---
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

    # --- эпики + issue, строго в document order ---
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
                continue  # идемпотентно
            cmds.append(Command((
                "bd", "create", "--parent", ekey,
                "--title", f"{t.id} {t.title}",
                "--label", tkey, "--label", "athena",
                "--description", _issue_body(t),
            )))

    # --- рёбра зависимостей (эпик-уровень), КАНОНИЧЕСКИЙ порядок ---
    for ph in plan.phases:
        for d in sorted(ph.depends_on):
            cmds.append(Command((
                "bd", "dep", "add", _epic_key(slug, ph.index),
                "--blocked-by", _epic_key(slug, d),
            )))

    return CompileResult(tuple(cmds), tuple(epic_keys), issue_count)


# =============================================================================
# [EFFECTFUL]  lib/bd_client.py — ЕДИНСТВЕННОЕ место с subprocess/I/O
# =============================================================================
def fetch_existing_keys(slug: str, *, run) -> frozenset[str]:
    """
    run: callable -> stdout (инжектим subprocess в проде, фейк в тестах).
    Запрашивает у bd уже существующие athena-лейблы для идемпотентности.
    """
    import json
    out = run(["bd", "list", "--label", f"{EXTERNAL_KEY_PREFIX}:{slug}:", "--json"])
    issues = json.loads(out or "[]")
    keys: set[str] = set()
    for it in issues:
        for lbl in it.get("labels", []):
            if lbl.startswith(f"{EXTERNAL_KEY_PREFIX}:{slug}:"):
                keys.add(lbl)
    return frozenset(keys)


def execute(result: CompileResult, *, run) -> None:
    """Исполнить команды по очереди. Эффектный слой, НЕ тестируется golden-тестами."""
    for cmd in result.commands:
        run(list(cmd.argv))


# =============================================================================
# [TESTS]  tests/test_plan2beads.py
# =============================================================================
# import pytest, pathlib, json
# from lib.plan_parser import parse, PlanParseError
# from lib.plan2beads import compile, CompileError, EXTERNAL_KEY_PREFIX
#
# FIX = pathlib.Path(__file__).parent / "fixtures"
#
# def _cmds(res): return [str(c) for c in res.commands]
#
# def test_golden_valid():
#     """plan.md -> точный ожидаемый список команд (snapshot)."""
#     res = compile(parse((FIX / "valid.md").read_text()))
#     expected = json.loads((FIX / "valid.expected.json").read_text())
#     assert _cmds(res) == expected
#
# def test_deterministic_repeated():
#     """Дважды скомпилировать -> идентичный вывод."""
#     plan = parse((FIX / "valid.md").read_text())
#     assert _cmds(compile(plan)) == _cmds(compile(plan))
#
# def test_idempotent_upsert():
#     """При existing_keys=всё -> ни одной 'bd create'."""
#     plan = parse((FIX / "valid.md").read_text())
#     first = compile(plan)
#     all_keys = frozenset(
#         a for c in first.commands for i, a in enumerate(c.argv)
#         if i > 0 and c.argv[i-1] == "--label" and a.startswith(EXTERNAL_KEY_PREFIX)
#     )
#     second = compile(plan, existing_keys=all_keys)
#     assert [c for c in _cmds(second) if " create " in c] == []
#
# def test_missing_success_check_rejected():
#     with pytest.raises((PlanParseError, CompileError)):
#         compile(parse((FIX / "no_check.md").read_text()))
#
# def test_unresolved_dependency_rejected():
#     with pytest.raises(CompileError):
#         compile(parse((FIX / "bad_dep.md").read_text()))
#
# def test_duplicate_task_id_rejected():
#     with pytest.raises(PlanParseError):
#         parse((FIX / "dup_id.md").read_text())
#
# # --- property (hypothesis), опционально ---
# # @given(...) roundtrip: parse(render(plan)) == plan
#
# # --- bd contract (марка integration, реальный bd в temp Dolt) ---
# # @pytest.mark.integration
# # def test_emitted_commands_accepted_by_bd(tmp_path): ...
#   #  ловит дрейф схемы Beads между версиями


# =============================================================================
# [FIXTURE]  tests/fixtures/valid.md  (пример канонического формата)
# =============================================================================
_FIXTURE_VALID = """\
# Plan: Demo Feature
## Overview
Add a healthcheck endpoint. Desired end state: GET /health returns 200.

## Out of Scope
- auth on the endpoint

## Phase 1: Endpoint
**Goal:** expose GET /health
**Depends on:** none
### Tasks
- [ ] T1.1 add /health route
  - success_check: `pytest tests/test_health.py -q`
  - files: `app/routes.py`

## Phase 2: Wire-up
**Goal:** register route in app
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 register blueprint
  - success_check: `curl -sf localhost:8000/health`
"""

if __name__ == "__main__":
    # быстрый smoke: распарсить фикстуру и напечатать команды
    p = parse(_FIXTURE_VALID)
    r = compile(p)
    print(f"epics={len(r.epic_keys)} issues={r.issue_count} commands={len(r.commands)}")
    for c in r.commands:
        print(" ", c)
