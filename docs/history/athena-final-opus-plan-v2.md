# Athena — Hermes-friendly Planner. ФИНАЛЬНЫЙ план для Опуса — v2 (3 слоя)

> **Версия:** v2. Заменяет v1. Главное отличие от v1: добавлен средний слой **Spec-Kit**
> (нативная детерминированная спека), а **implement (Ralph/исполнитель) вынесен в отложенный
> stub** — прикрутим потом. Сейчас scope = три слоя ПЛАНИРОВАНИЯ, доводящие до наполненного
> Beads-графа, готового к исполнению.
>
> **Что строим:** надстройку «**Athena**» над ТРЕМЯ готовыми чужими репо:
> ① **CRISP/QRSPI** (агентный харнесс + выравнивание), ② **GitHub Spec-Kit** (нативная
> спека/требования/задачи, более детерминированный слой), ③ **Beads `bd` v1.0** (durable
> task-граф на Dolt). Оформлено как **Claude Code плагин + MCP-сервер**, через который
> **Hermes (L2-оркестратор NEXUS)** ведёт весь цикл планирования высокоуровневыми глаголами.
>
> **Кому:** агенту на Claude Opus.
> **Дисциплина:** дог-фудинг — строим по CRISP. Каждая стадия — свежий контекст, состояние в
> файлах + git. Контекст <40%, fresh при 60%, бюджет инструкций <40 на промпт.

---

## 0. Карта: кто что даёт и что мы пишем сами

| Слой | Репо | Роль | Наш код? |
|---|---|---|---|
| ① CRISP/QRSPI | community (`matanshavit/qrspi`, `dfrysinger/qrspi-plus`) — vendored | агентный харнесс: выравнивание + контекст-дисциплина | нет |
| ② Spec-Kit | `github/spec-kit` — установка + наш preset | нативная спека: requirements/plan/**tasks.md** (строгая схема) + analyze-gate | preset + парсер |
| ③ Beads | `gastownhall/beads` v1.0 — установка | durable task-граф/память (Dolt) | нет |
| **компилятор** | **мы** | `tasks.md`/`plan.md` → `bd` (детерминированно) | **ДА — ядро** |
| **Athena MCP** | **мы** | глаголы для Hermes | **ДА** |
| **toggle-склейка** | **мы** | переключение 3-слой ↔ 2-слой fallback | **ДА** |
| ④ implement (Ralph/OpenHands/Claurst) | — | исполнение | **ОТЛОЖЕНО — только интерфейс-stub** |

---

## 1. Инварианты (НЕ нарушать)

1. **Компилятор детерминированный.** Никаких LLM-вызовов. Одна и та же входная спека → один и тот же набор `bd`-команд. Чистое ядро без I/O/времени/random; идемпотентность через `existing_keys`.
2. **Внутренний AST (`Plan`) — общий контракт.** Оба фронт-парсера (Spec-Kit и канонический) выдают ОДИН и тот же `Plan` AST; компилятор знает только AST. Это и есть точка, где toggle стоит дёшево.
3. **Beads source of truth = Dolt** (`.beads/`), НЕ `issues.jsonl`. Только через `bd` CLI / `beads-mcp`.
4. **Spec-Kit-треть ОТКЛЮЧАЕМА за флаг `ATHENA_SPECKIT=on|off`** (см. §6). off → fallback на 2-слойный путь CRISP→граф. Хрупкость Spec-Kit не должна блокировать весь пайплайн.
5. **Перекрытие вырезано жёстко:** в 3-слое стадия **Plan у CRISP не используется** (её делает Spec-Kit); стадия **implement у Spec-Kit не используется** (она отложена и будет нашим Ralph).
6. **`success_check` обязателен у каждой задачи** на выходе AST. Нет → ошибка компиляции.
7. **CRISP/QRSPI и часть схемы — community-реконструкция**; стабильным держим только: внутренний AST + схему `tasks.md` Spec-Kit (через golden-тест версии).
8. **implement не реализуем** в этой итерации — только `ralph/INTERFACE.md` с контрактом (§9, Phase 9).

---

## 2. Архитектура и структура репо

```
nexus-athena/
├── .claude-plugin/plugin.json
├── commands/
│   ├── crisp/
│   │   ├── 1_question.md            # /crisp.question
│   │   ├── 2_research.md            # /crisp.research  (тикет СКРЫТ)
│   │   ├── 3_design.md              # /crisp.design
│   │   ├── 4_structure.md           # /crisp.structure
│   │   └── 5_plan.md                # /crisp.plan  — ТОЛЬКО в fallback (speckit OFF)
│   └── compile.md                   # /athena.compile  — вызывает компилятор
├── speckit/
│   ├── presets/athena/              # наш preset: добавляет success_check в task-шаблон
│   └── seed.md                      # как сидить Spec-Kit из CRISP по-фазно (§5)
├── agents/                          # documentarian-сабагенты (описывают, не предлагают)
│   ├── codebase-locator.md
│   ├── codebase-analyzer.md
│   ├── codebase-pattern-finder.md
│   └── web-search-researcher.md
├── skills/
│   ├── plan-format/SKILL.md         # канонический plan.md (контракт FALLBACK)
│   └── speckit-tasks-format/SKILL.md# схема tasks.md Spec-Kit, которую парсим (контракт PRIMARY)
├── hooks/hooks.json                 # SessionStart: bd prime; PreCompact: bd sync
├── mcp/athena_mcp/
│   ├── server.py
│   ├── verbs.py
│   └── pyproject.toml
├── lib/
│   ├── ast.py                       # ВНУТРЕННИЙ Plan AST (общий контракт §3)
│   ├── plan_parser.py               # plan.md  -> Plan   (fallback)
│   ├── speckit_parser.py            # tasks.md -> Plan   (primary)
│   ├── plan2beads.py                # Plan -> bd  (детерминированное ЯДРО, §4)
│   └── bd_client.py                 # ЕДИНСТВЕННОЕ место с subprocess
├── tests/
│   ├── test_ast.py
│   ├── test_plan_parser.py
│   ├── test_speckit_parser.py       # + golden схемы Spec-Kit (страж версии)
│   ├── test_plan2beads.py           # golden + idempotency + negative
│   └── fixtures/
├── ralph/
│   └── INTERFACE.md                 # [ОТЛОЖЕНО] контракт исполнителя, НЕ реализуем
├── vendor/
│   ├── crisp/                       # vendored CRISP/QRSPI (pinned commit)
│   └── spec-kit/                    # pinned ref Spec-Kit (для воспроизводимости схемы)
├── install.sh
└── README.md
```

### Поток (3-слой, primary)
```
Hermes ──MCP──>
 ① CRISP:  question → research(тикет скрыт) → design → structure        [ярусные гейты]
 ② Spec-Kit (seeded из CRISP по-фазно):
      Q+R → specify (spec.md) → clarify
      D+S → plan (plan.md)
            → tasks (tasks.md: strict checklist + [P] + [Story])
            → analyze (consistency gate)
 ③ compile: speckit_parser(tasks.md) → Plan AST → plan2beads → Beads (эпики/issue/deps)
 ── ГРАНИЦА SCOPE ──
 ④ [ОТЛОЖЕНО] Ralph: bd ready → исполнитель → внешний gate → bd close
```
### Поток (2-слой, fallback при ATHENA_SPECKIT=off)
```
 ① CRISP: question → research → design → structure → plan (5_plan.md, канонический формат)
 ③ compile: plan_parser(plan.md) → Plan AST → plan2beads → Beads
```

---

## 3. Внутренний контракт: `Plan` AST (lib/ast.py)

Оба парсера выдают это; компилятор ест только это. Toggle = выбор парсера.

```python
@dataclass(frozen=True)
class Task:
    id: str                       # стабильный из источника (T1.1 / T001)
    title: str
    success_check: str            # обязателен, непуст
    files: tuple[str, ...] = ()
    parallel: bool = False        # из [P] Spec-Kit / "P" в нашем формате
    autonomy: str = "default"     # роутинг будущего исполнителя (high → OpenHands)

@dataclass(frozen=True)
class Phase:
    key: str                      # "US1" / "setup" / "phase1"
    title: str
    goal: str
    depends_on: tuple[str, ...]   # ключи других фаз
    checkpoint: str = ""          # команда-gate фазы (из Spec-Kit Checkpoint), опц.
    tasks: tuple[Task, ...] = ()

@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    phases: tuple[Phase, ...]
```

---

## 4. Контракт: `plan2beads` — детерминированное ядро (Plan AST → bd)

> Рабочий скелет — в приложенном `plan2beads.py` (под v2 поправить вход на `Plan` AST из §3).

**Почему детерминизм:** компилятор — линия заморозки. LLM генерит всё ВВЕРХУ (нечётко), компилятор переводит AST→команды (предсказуемо). LLM в компиляторе ⇒ невоспроизводимый прогон, невозможные golden-тесты, дубли при replan.

**Сигнатура:** `compile(plan: Plan, *, existing_keys: frozenset[str] = frozenset()) -> CompileResult`

**Шаги (document order, детерминированно):**
1. Валидация: каждый `Task.success_check` непуст; `depends_on` резолвятся; нет дублей `Task.id`. Иначе `CompileError`.
2. `Phase` → `bd create --type epic --label athena:<slug>:<phase.key>` (+ `checkpoint` в тело/note).
3. `Task` → `bd create --parent <epic> --label athena:<slug>:<task.id> --label athena [+ autonomy:<a>]`; тело несёт `success_check`/`files`.
4. Зависимости: между фазами — `bd dep add ... --blocked-by ...` по `depends_on`; внутри фазы для НЕ-`parallel` задач — blocks по порядку; для `parallel` сиблингов — рёбер НЕТ. Все рёбра в `sorted()` порядке.

**Идемпотентность:** внешние лейблы `athena:<slug>:...` поверх hash-ID Beads. `bd_client.fetch_existing_keys` запрашивает существующие → `existing_keys` → ядро пропускает `bd create` существующего. Чистое ядро остаётся чистым.

**Враги детерминизма (ревью):** таймстемпы/random в ядре (инжектить), итерация по `set` (только document order/`sorted()`), locale-сортировка.

---

## 5. Слой ② Spec-Kit: seed по-фазно + preset для success_check

**Seed (избегаем impedance mismatch CRISP→Spec-Kit):** не «один документ стопкой», а по-фазно —
- CRISP **Q+R** (понимание проблемы) → сидит `specify` (spec.md: требования/user stories) → `clarify`;
- CRISP **D+S** (решение) → сидит `plan` (plan.md: архитектура);
- далее `tasks` → `tasks.md`; `analyze` → consistency-gate.

**Формат `tasks.md`, который парсим** (зафиксировать в `skills/speckit-tasks-format/SKILL.md`): строгий checklist — `- [ ] T001 [P] [US1] описание` + пути к файлам; `[P]` = параллелизуемо (разные файлы, нет зависимостей); `[Story]` = US1/US2/...; фазы Setup/Foundational блокируют все US-фазы; каждая US-фаза заканчивается **Checkpoint**.

**Шов `success_check` — решение: Athena preset (primary).** Пишем preset под `speckit/presets/athena/`, который расширяет task-шаблон Spec-Kit обязательной строкой `success_check:` на задачу (Spec-Kit нативно поддерживает presets, стакаются по приоритету). Тогда `speckit_parser` читает её нативно.
**Fallback (если preset хрупкий):** `Phase.checkpoint` = команда Checkpoint фазы → gate на уровне эпика; внутри полагаемся на test-first задачи.

**Маппинг `tasks.md` → AST:** US-фаза → `Phase(key="US1")`; Setup/Foundational → `Phase` блокирующие US-фазы; task → `Task`; `[P]` → `Task.parallel=True`; `success_check` из preset (или `Phase.checkpoint` fallback).

---

## 6. Toggle: 3-слой ↔ 2-слой fallback (`ATHENA_SPECKIT`)

- `ATHENA_SPECKIT=on` (primary): CRISP останавливается на Structure → Spec-Kit → `speckit_parser(tasks.md)` → AST → compile.
- `ATHENA_SPECKIT=off` (fallback): CRISP идёт до `5_plan.md` (канонический формат) → `plan_parser(plan.md)` → AST → compile.
- Реализуется одной развилкой в `compile.md`/MCP: какой парсер вызвать. **Ядро `plan2beads` не знает о toggle** — оно видит только AST.

---

## 7. Athena MCP server (глаголы для Hermes)

| Глагол | Действие |
|---|---|
| `planner_question` | CRISP стадия 1; в автономе Hermes отвечает на развилки |
| `planner_research` | CRISP стадия 2 (тикет скрыт), documentarian-сабагенты |
| `planner_design` / `planner_structure` | CRISP 3/4 |
| `planner_align` | крупно: 1→4 с ярусными гейтами |
| `planner_spec` | (speckit on) seed → specify/clarify/plan/tasks/analyze → `tasks.md` |
| `planner_plan` | (speckit off) CRISP 5_plan → канонический `plan.md` |
| `planner_validate` | проверка формата выбранного источника до компиляции |
| `planner_compile` | выбрать парсер по `ATHENA_SPECKIT` → AST → `plan2beads` → bd |
| `planner_report` | `bd stats --json` + сводка эпиков |
| `planner_replan` | агрегирует discovered-from/провалы analyze → бэктрек на нужную стадию |
| `planner_export_ready` | (мост к будущему ④) `bd ready --json` — НЕ исполняет, только отдаёт очередь |

Ярусные гейты: `question/research/design` + `analyze` — плотно (Hermes/человек); `structure/plan/tasks` — spot-check.

---

## 8. Фазы сборки (plan.md для Опуса; каждый task с success_check)

### Phase 0: Scaffold + vendoring + pin
- [ ] T0.1 структура §2. `success_check:` `test -d commands/crisp && test -d lib && test -d speckit && test -f ralph/INTERFACE.md`
- [ ] T0.2 vendored CRISP + pinned ref Spec-Kit + commit-hash в README. `success_check:` `test -f vendor/crisp/4_structure.md && test -d vendor/spec-kit`
- [ ] T0.3 `install.sh`: pinned `bd`, `specify init`, `bd init`, регистрация плагина+MCP. `success_check:` `bash -n install.sh`
**Manual:** запинить версии bd (v1.x Dolt) и Spec-Kit ref; убедиться, что `specify` ставится.

### Phase 1: Внутренний Plan AST
**Depends on:** Phase 0
- [ ] T1.1 `lib/ast.py` по §3. `success_check:` `python -m pytest tests/test_ast.py -q`
**Manual:** AST достаточно выразителен для обоих источников (Spec-Kit и канон).

### Phase 2: Канонический формат + парсер (fallback-путь)
**Depends on:** Phase 1
- [ ] T2.1 `skills/plan-format/SKILL.md`. `success_check:` `grep -q success_check skills/plan-format/SKILL.md`
- [ ] T2.2 `plan_parser.py` → `Plan`. `success_check:` `python -m pytest tests/test_plan_parser.py -q`
**Manual:** fallback-формат однозначно парсится.

### Phase 3: Слой Spec-Kit (схема + парсер + preset + страж версии)
**Depends on:** Phase 1
- [ ] T3.1 `skills/speckit-tasks-format/SKILL.md` (схема `tasks.md` §5). `success_check:` `grep -q '\[P\]' skills/speckit-tasks-format/SKILL.md`
- [ ] T3.2 preset `speckit/presets/athena/` добавляет `success_check:` в task-шаблон. `success_check:` `test -d speckit/presets/athena`
- [ ] T3.3 `speckit_parser.py` (`tasks.md` → `Plan`, [P]→parallel, Checkpoint→checkpoint). `success_check:` `python -m pytest tests/test_speckit_parser.py -q`
- [ ] T3.4 **golden схемы Spec-Kit** — фикстура реального `tasks.md` → ожидаемый AST; падает при дрейфе формата. `success_check:` `python -m pytest tests/test_speckit_parser.py -q -k golden`
**Manual:** прогнать реальный `/speckit.tasks` с нашим preset, скормить парсеру — success_check на месте.

### Phase 4: Детерминированный компилятор (AST → bd)
**Depends on:** Phase 1
- [ ] T4.1 `plan2beads.py` ядро на `Plan` AST + idempotency. `success_check:` `python -m pytest tests/test_plan2beads.py -q`
- [ ] T4.2 golden + idempotency + negative зелёные. `success_check:` `python -m pytest tests/ -q`
- [ ] T4.3 `bd_client.py` (subprocess, `--json`, `fetch_existing_keys`). `success_check:` `python -c "import lib.bd_client"`
**Manual:** dry-run на реальном `bd init`, сверить команды; одинаковый вход → одинаковый выход дважды.

### Phase 5: CRISP-цепочка + сабагенты + seed
**Depends on:** Phase 1
- [ ] T5.1 `commands/crisp/{1..4}_*.md` + `5_plan.md` (fallback). `success_check:` `ls commands/crisp/*.md | wc -l | grep -q 5`
- [ ] T5.2 documentarian-сабагенты в `agents/`. `success_check:` `ls agents/*.md | wc -l | grep -qE '[4-9]'`
- [ ] T5.3 `speckit/seed.md` — по-фазный seed (Q+R→specify, D+S→plan). `success_check:` `grep -q specify speckit/seed.md`
**Manual:** прогнать question→research→design→structure на тестовой задаче.

### Phase 6: Toggle 3↔2 слоя
**Depends on:** Phase 2, Phase 3, Phase 4
- [ ] T6.1 `commands/compile.md` выбирает парсер по `ATHENA_SPECKIT`. `success_check:` `grep -q ATHENA_SPECKIT commands/compile.md`
- [ ] T6.2 оба пути дают валидный AST → одинаковый compile-контракт. `success_check:` `python -m pytest tests/ -q -k toggle`
**Manual:** on → tasks.md→граф; off → plan.md→граф; граф эквивалентен по структуре.

### Phase 7: Athena MCP server
**Depends on:** Phase 4, Phase 5, Phase 6
- [ ] T7.1 `server.py`+`verbs.py`, глаголы §7. `success_check:` `cd mcp/athena_mcp && uv run python -c "import athena_mcp.server"`
- [ ] T7.2 `planner_spec`/`planner_plan`/`planner_compile`/`planner_export_ready`. `success_check:` `cd mcp/athena_mcp && uv run pytest -q`
**Manual:** через MCP-инспектор довести intent → наполненный bd-граф в обоих режимах.

### Phase 8: Интеграция с Hermes
**Depends on:** Phase 7
- [ ] T8.1 регистрация athena MCP в конфиге Hermes. `success_check:` `<проверка конфига Hermes>`
- [ ] T8.2 Hermes-плейбук: align→(spec|plan)→validate→analyze→compile→report; автономные ответы на Question. `success_check:` `test -f hermes_playbook.md`
**Manual:** Hermes одним промптом доводит до наполненного графа, сам отвечая на развилки.

### Phase 9: [ОТЛОЖЕНО] интерфейс исполнителя (stub, НЕ реализуем)
**Depends on:** Phase 7
- [ ] T9.1 `ralph/INTERFACE.md`: контракт `bd ready → executor → внешний gate → bd close`, роутинг `autonomy:high`→OpenHands/иначе Claurst, внешний gate как authoritative. Реализацию НЕ писать. `success_check:` `grep -q 'bd ready' ralph/INTERFACE.md && grep -q DEFERRED ralph/INTERFACE.md`
**Manual:** интерфейс достаточен, чтобы позже воткнуть Ralph без изменения планнера.

### Phase 10: End-to-end дог-фудинг (только планирование)
**Depends on:** Phase 8
- [ ] T10.1 реальная мелкая фича: полный CRISP→Spec-Kit→compile (режим on) → наполненный граф. `success_check:` `bd list --label athena --json | jq 'length > 0'`
- [ ] T10.2 та же фича в режиме off (CRISP→plan→compile). `success_check:` `bd stats --json | jq '.total > 0'`
- [ ] T10.3 `run-report.md`: метрики обоих прогонов + где сработали гейты. `success_check:` `test -f run-report.md`
**Manual:** граф dependency-корректен; `[P]`-задачи без лишних рёбер; success_check у каждого issue; analyze отбил бы кривой план.

---

## 9. Acceptance (v2 готов)
- `pytest tests/` зелёный: AST, оба парсера, golden Spec-Kit-схемы (страж версии), компилятор (golden+idempotency+negative), toggle.
- Hermes одним промптом → наполненный, dependency-корректный Beads-граф с `success_check` у каждого issue — В ОБОИХ режимах (`ATHENA_SPECKIT=on|off`).
- `[P]`-сиблинги без рёбер между собой; межфазные зависимости корректны.
- Spec-Kit-треть отключается флагом без правки `plan2beads`.
- implement НЕ реализован, но `ralph/INTERFACE.md` определяет контракт так, что позже втыкается без изменения планнера.
- Установка: `bash install.sh`. Состояние Beads в self-hosted git/Dolt, переживает kill сессий.

## 10. Риски / не забыть
- **Version coupling на Spec-Kit** — самый острый риск 3-слоя. `tasks.md` схема движется; golden-тест Spec-Kit (T3.4) обязан падать при дрейфе. Запинить ref в vendor/.
- **Перекрытие** — в режиме on НЕ использовать `5_plan.md` CRISP (двойное планирование); в режиме off НЕ трогать Spec-Kit.
- **Шов success_check** — preset первичен; при его хрупкости падать на Checkpoint-fallback (`Phase.checkpoint`).
- **Beads version flux** — pinned v1.x (Dolt); durable артефакт = Dolt-репо (`bd dolt push/pull`, `bd backup`), не jsonl; `bd_client` тесты ловят дрейф схемы.
- **Question-стадия в автономе** — Hermes ОБЯЗАН отвечать на развилки, иначе зависание на «магических словах».
- **Токены** — 3-слой самый дорогой (CRISP 4 + Spec-Kit 4-5 + compile); смягчается self-hosted кластером; при дороговизне гонять рутину в режиме off.
- **implement отложен** — не тянуть Ralph/OpenHands сейчас; держать границу scope на наполнении графа.
