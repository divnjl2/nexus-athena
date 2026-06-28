# Athena — Hermes-friendly Planner. ЗАКРЕПЛЁННЫЙ план для Опуса — v3 (финальная архитектура)

> **Статус:** locked / финальная архитектура планирования. Заменяет v1, v2.
> **Отличие v3 от v2:** (1) **Spec-Kit `/specify` — КОРЕНЬ**, не toggle-середина — спека логически
> первична, всё ниже выводится из неё. (2) **QRSPI понижен из «генератора плана» в «дополнитель
> спеки»** — анализирует и обогащает замороженную спеку (research/design = «как»). (3) **Выход
> каждого LLM-хопа версионируется как first-class артефакт** (`design.md` пиннут к
> `(spec_version, run_id)`). (4) **Граф расширен до графа происхождения** — узлы spec/design/task,
> рёбра derived-from/refines/implements. (5) **Backedge research→/specify** бампает spec_version.
> (6) **Seam-слой переосмыслен** — это версионная подложка для недетерминированных хопов, не
> опциональная наблюдаемость. **implement (Ralph/исполнитель) остаётся отложенным stub'ом.**
>
> **Что строим:** надстройку «Athena» над тремя репо: ① **Spec-Kit** (корень: спека/требования/
> tasks), ② **CRISP/QRSPI** (анализ+дополнение: research/design), ③ **Beads `bd` v1.0** (durable
> граф происхождения на Dolt). Плагин + MCP-сервер; **Hermes** ведёт цикл глаголами.
> **Кому:** агенту на Claude Opus. **Дисциплина:** дог-фудинг по CRISP, контекст <40%.

---

## 0. Центральный принцип v3 (читать первым)

**Спека — логический корень. Всё остальное `derived-from` неё.** Но между спекой и графом сидит **QRSPI — LLM, недетерминированный хоп**. Отсюда железное правило версионирования:

> **На детерминированном хопе версионируем ВХОД. На LLM-хопе версионируем ВЫХОД.**

- `plan2beads` (детерминир.): достаточно версионировать вход (AST).
- QRSPI (LLM): обязан версионировать **выход** (`design.md`), потому что из спеки он НЕ регенерится одинаково.

Без пиннинга design-выхода цепочка «спека→исполнение» реконструируется с дыркой ровно там, где интенция превращалась в план. Поэтому **seam-слой — это версионная подложка**, делающая связь `spec_version ↔ graph_version` явной, а не «совпали по времени через run_id».

| Слой | Репо | Роль | Детерминизм | Что версионируем |
|---|---|---|---|---|
| ① Spec-Kit `/specify` | `github/spec-kit` + наш preset | **корень**: что+зачем | LLM | выход: `spec.md` → `spec_version` |
| ② CRISP/QRSPI | community vendored | **дополнитель**: как (research/design) | LLM | выход: `design.md` → `design_version`, пиннут к spec |
| Spec-Kit `/plan`+`/tasks` | Spec-Kit | операционализация | LLM | выход: `tasks.md` |
| **компилятор** | **мы** | AST → граф происхождения | **детерм.** | вход (AST) |
| ③ Beads | `gastownhall/beads` v1.0 | durable граф происхождения | — | состояние (Dolt) |
| ④ implement | — | исполнение | — | **ОТЛОЖЕНО — только интерфейс** |

---

## 1. Инварианты (НЕ нарушать)

1. **Спека-корень.** `/specify` логически первичен; design/tasks/граф — `derived-from` спеки.
2. **Версионирование выхода LLM-хопов.** `spec.md`→`spec_version`, `design.md`→`design_version` (пиннут к `(spec_version, run_id)`) — first-class артефакты в git, не эфемера.
3. **Компилятор детерминированный.** AST→команды; чистое ядро без I/O/времени/random; идемпотентность через `existing_keys`.
4. **Внутренний `Plan` AST — общий контракт.** Несёт `Provenance(spec_version, design_version, run_id)`. Оба фронт-парсера выдают один AST.
5. **Граница «что/как» железная.** Spec-Kit владеет «что+зачем» (без техстека); QRSPI владеет «как». Спека — контракт между ними. **Question-стадия QRSPI сужена** на «как строим / технические неизвестные», НЕ «что хочешь».
6. **Beads source of truth = Dolt** (`.beads/`), только через `bd` CLI / `beads-mcp`.
7. **Семантические рёбра → нативные примитивы Beads** (см. §4): не изобретать типы рёбер, которых bd не поддерживает.
8. **Spec-Kit-треть отключаема** (`ATHENA_SPECKIT`): on = спека-корень через `/specify`; off = спека пишется CRISP/вручную, но логически всё равно первична.
9. **Backedge разрешён:** `research → /specify` бампает `spec_version` (спека-корень, но живой; не водопад).
10. **implement не реализуем** — только `ralph/INTERFACE.md` + определение ребра `implements`.

---

## 2. Архитектура и поток

```
Hermes ──MCP──>
 ① /specify  ─────────────────► spec.md   [КОРЕНЬ, spec_version]      LLM, версионируем ВЫХОД
      │ (заморожена как контракт)
 ② QRSPI (питается замороженной спекой):
      question(как+неизвестные) → research → design ─► design.md       LLM, версионируем ВЫХОД
                                                  [design_version, пиннут к (spec_version, run_id)]
 ② /plan → /tasks ──────────────► tasks.md  [strict checklist]         LLM
 ③ compile: speckit_parser(tasks.md)+Provenance → Plan AST
      → plan2beads → ГРАФ ПРОИСХОЖДЕНИЯ:                               ДЕТЕРМИНИРОВАННО
           spec(node) ──derived-from──► design(node) ──derived-from──► task(issue)
 ── ГРАНИЦА SCOPE ──
 ④ [ОТЛОЖЕНО] implement: commit ──implements──► task
 ↑ backedge: research нашёл кривую спеку ──refines──► /specify → spec_version++
```

### Структура репо
```
nexus-athena/
├── .claude-plugin/plugin.json
├── commands/
│   ├── specify_root.md              # /athena.spec   — обёртка Spec-Kit /specify (КОРЕНЬ)
│   ├── crisp/
│   │   ├── 1_question.md            # /crisp.question (сужено: КАК+неизвестные)
│   │   ├── 2_research.md            # /crisp.research (тикет скрыт, питается спекой)
│   │   ├── 3_design.md              # /crisp.design  → design.md (версионируется)
│   │   └── 4_structure.md
│   └── compile.md                   # /athena.compile
├── speckit/
│   ├── presets/athena/              # preset: success_check в task-шаблон
│   └── seed.md                      # спека→QRSPI контракт «что/как»
├── agents/                          # documentarian-сабагенты
├── skills/
│   ├── plan-format/SKILL.md         # канонический plan.md (fallback)
│   ├── speckit-tasks-format/SKILL.md# схема tasks.md (parse-контракт)
│   └── provenance-graph/SKILL.md    # узлы/рёбра происхождения + маппинг на bd (§4)
├── lib/
│   ├── ast.py                       # Plan AST + Provenance (§3)
│   ├── plan_parser.py               # plan.md  -> Plan (fallback)
│   ├── speckit_parser.py            # tasks.md -> Plan (primary) + version-drift golden
│   ├── versioning.py                # spec_version/design_version, пиннинг design.md
│   ├── plan2beads.py                # Plan -> bd (детерм. ядро + рёбра происхождения §4)
│   └── bd_client.py                 # ЕДИНСТВЕННЫЙ subprocess
├── mcp/athena_mcp/{server,verbs}.py # глаголы §6 (вкл. traversal-трейс)
├── .athena/seams.jsonl              # версионная подложка: пины LLM-хопов
├── ralph/INTERFACE.md               # [ОТЛОЖЕНО] контракт исполнителя + ребро implements
├── tests/                           # AST, парсеры, golden схемы, provenance-рёбра, idempotency
├── vendor/{spec-kit,crisp}/         # pinned
├── install.sh
└── README.md
```

---

## 3. Внутренний контракт: `Plan` AST с происхождением (lib/ast.py)

```python
@dataclass(frozen=True)
class Provenance:
    spec_version: str        # хэш/git-ref spec.md (КОРЕНЬ)
    design_version: str      # хэш/git-ref design.md (выход QRSPI)
    run_id: str

@dataclass(frozen=True)
class Task:
    id: str
    title: str
    success_check: str        # обязателен, непуст
    files: tuple[str, ...] = ()
    parallel: bool = False    # [P]
    autonomy: str = "default" # роутинг будущего исполнителя

@dataclass(frozen=True)
class Phase:
    key: str                  # "US1"/"setup"
    title: str
    goal: str
    depends_on: tuple[str, ...]
    checkpoint: str = ""
    tasks: tuple[Task, ...] = ()

@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    provenance: Provenance    # НОВОЕ: связывает граф с spec/design версиями
    phases: tuple[Phase, ...]
```

---

## 4. Контракт: граф происхождения и маппинг на Beads (skills/provenance-graph/SKILL.md)

**Семантические узлы/рёбра → нативные примитивы Beads** (инвариант 7 — не изобретать то, чего bd не умеет):

| Семантика | Реализация в Beads |
|---|---|
| узел `spec` | issue с `--label kind:spec --label athena:spec:<spec_version>` |
| узел `design` | issue с `--label kind:design --label athena:design:<design_version>` |
| узел `task` | issue (как сейчас) |
| ребро `derived-from` | **parent-child цепь**: spec → design → epic(фаза) → task |
| ребро `refines` (backedge) | `related` + `--label refines` от research-issue к spec + бамп spec_version |
| ребро `implements` (отложено) | git-коммит с ID issue в сообщении (нативная конвенция Beads) + `--label implements` |

> Проверить в `bd --help`, что parent-child поддерживает multi-level (spec→design→epic→task = 3 уровня). Если нет — связь spec→design делать через `related --label derived-from`, остальное parent-child.

**Трассировка = обход графа (query-able через `bd`):**
- вниз по `derived-from` от spec → «что выросло из требования»;
- вверх от коммита/задачи → «зачем существует этот код»;
- `refines`-рёбра → «где реализация уточнила интенцию» (дополнения агента задокументированы, не потеряны).

---

## 5. Контракт: `plan2beads` — детерминир. ядро + рёбра происхождения

> Скелет — в приложенном `plan2beads.py`; под v3 поправить вход на `Plan` AST (§3) и добавить эмиссию узлов/рёбер происхождения.

**Сигнатура:** `compile(plan: Plan, *, existing_keys: frozenset[str] = frozenset()) -> CompileResult`

**Шаги (document order, детерминированно):**
1. Валидация: `success_check` непуст; deps резолвятся; нет дублей/циклов; `provenance` заполнен. Иначе `CompileError`.
2. **spec-node** (идемпотентно по `spec_version`): `bd create --label kind:spec --label athena:spec:<spec_version>` — создаётся только если `spec_version` новый (спека-корень переживает прогоны).
3. **design-node**: `bd create --label kind:design --label athena:design:<design_version>` + parent = spec-node.
4. **Phase** → epic, parent = design-node. **Task** → issue, parent = epic; тело несёт `success_check`/`files`; лейблы версий.
5. Зависимости фаз/задач (blocks); `[P]`-сиблинги — без ребра.
6. `implements`/`refines` — НЕ в обычном compile (коммитов ещё нет; backedge — отдельная операция §7).

**Идемпотентность:** внешние лейблы `athena:*` поверх hash-ID; `existing_keys` из `bd_client.fetch_existing_keys`; ядро пропускает существующее. **spec-node особенно** — один `spec_version` = один узел, не дублить между прогонами.

**Детерминизм:** без LLM/времени/random в ядре; только document order/`sorted()`; враги — `set`-итерация, locale-сортировка.

---

## 6. Версионная подложка (lib/versioning.py + .athena/seams.jsonl)

Каждый **LLM-хоп** пишет `SeamRecord` с `input_version` + `output_version` + хэш в `.athena/seams.jsonl`; детерминированный хоп — только `input_hash`.

- `/specify` → пишет `spec.md`, считает `spec_version` (git-ref/хэш), record.
- `design` → пишет `design.md` в `thoughts/designs/<spec_version>/<run_id>/`, считает `design_version`, **пиннит к `(spec_version, run_id)`**, record.
- `compile` → record с `input=(spec_version,design_version)`, `output=graph` (cmd-hash).

Так `spec_version ↔ graph_version` явная. `SeamRecord` спроектировать 1:1 под OTel-span (trace_id=run_id, attrs=версии/хэши) — апгрейд на телеметрию = добавить экспортёр.

---

## 7. Backedge: research → /specify (спека живая)

Когда QRSPI-research показывает, что «что+зачем» неверно:
1. `planner_replan(trigger="spec_invalid", context=...)` →
2. research-issue получает `related --label refines` к текущему spec-node;
3. `/specify` производит `spec.md` v_{n+1} → новый `spec_version` → новый spec-node;
4. перекомпиляция выводит новый design/граф из новой спеки.

Это bidirectional feedback: спека остаётся корнем, но уточняется снизу. НЕ водопад.

---

## 8. Athena MCP server (глаголы для Hermes)

| Глагол | Действие |
|---|---|
| `planner_spec` | (root) Spec-Kit `/specify` → `spec.md` + `spec_version` [плотный гейт] |
| `planner_question` | CRISP 1, сужено: как+неизвестные; в автономе Hermes отвечает |
| `planner_research` | CRISP 2 (тикет скрыт, питается спекой) |
| `planner_design` | CRISP 3 → `design.md`, версионирует+пиннит к `(spec_version, run_id)` |
| `planner_align` | крупно: question→research→design с гейтами |
| `planner_tasks` | (speckit on) `/plan`+`/tasks`+`/analyze` → `tasks.md` |
| `planner_plan` | (speckit off) CRISP `5_plan` → канонический `plan.md` |
| `planner_compile` | парсер по `ATHENA_SPECKIT` → Plan AST(+Provenance) → `plan2beads` → граф |
| `planner_trace_down` | обход `derived-from` от `spec_version` → что выросло |
| `planner_trace_up` | обход вверх от task/commit → зачем существует |
| `planner_replan` | backedge research→/specify (бамп spec_version) или re-stage |
| `planner_report` | `bd stats` + версии + сводка эпиков |

---

## 9. Фазы сборки (plan.md для Опуса; каждый task с success_check)

### Phase 0: Scaffold + vendoring + pin
- [ ] T0.1 структура §2. `success_check:` `test -d commands/crisp && test -d speckit && test -f skills/provenance-graph/SKILL.md && test -f ralph/INTERFACE.md`
- [ ] T0.2 vendored CRISP + pinned ref Spec-Kit + хэши в README. `success_check:` `test -d vendor/spec-kit && test -f vendor/crisp/3_design.md`
- [ ] T0.3 `install.sh` (pinned bd, `specify init`, `bd init`, плагин+MCP). `success_check:` `bash -n install.sh`
**Manual:** запинить версии bd (v1.x Dolt) и Spec-Kit ref.

### Phase 1: Plan AST + Provenance
**Depends on:** Phase 0
- [ ] T1.1 `lib/ast.py` (§3, с `Provenance`). `success_check:` `python -m pytest tests/test_ast.py -q`
**Manual:** AST выражает spec/design версии + происхождение.

### Phase 2: Spec-Kit как КОРЕНЬ
**Depends on:** Phase 1
- [ ] T2.1 `commands/specify_root.md` (обёртка `/specify`, выход = spec-корень). `success_check:` `grep -qi specify commands/specify_root.md`
- [ ] T2.2 preset `speckit/presets/athena/` (+`success_check:` в task-шаблон). `success_check:` `test -d speckit/presets/athena`
- [ ] T2.3 `skills/speckit-tasks-format/SKILL.md` (схема tasks.md). `success_check:` `grep -q '\[P\]' skills/speckit-tasks-format/SKILL.md`
- [ ] T2.4 `speckit/seed.md` — контракт «что(spec)/как(QRSPI)». `success_check:` `grep -qi 'what.*how\|что.*как' speckit/seed.md`
**Manual:** `/specify` даёт спеку без техстека; tasks.md с success_check от preset.

### Phase 3: QRSPI как дополнитель (версионируемый design)
**Depends on:** Phase 1, Phase 2
- [ ] T3.1 `commands/crisp/{1..4}` (question сужено на «как», research питается спекой). `success_check:` `ls commands/crisp/*.md | wc -l | grep -qE '[4-9]'`
- [ ] T3.2 documentarian-сабагенты. `success_check:` `ls agents/*.md | wc -l | grep -qE '[4-9]'`
- [ ] T3.3 `lib/versioning.py`: `design.md` пиннится к `(spec_version, run_id)` в `thoughts/designs/...`. `success_check:` `python -m pytest tests/test_versioning.py -q`
**Manual:** design.md лежит под (spec_version, run_id), регенерация даёт новый design_version (LLM-хоп).

### Phase 4: Парсеры (primary + fallback) + страж версии
**Depends on:** Phase 1
- [ ] T4.1 `plan_parser.py` (`plan.md`→Plan, fallback). `success_check:` `python -m pytest tests/test_plan_parser.py -q`
- [ ] T4.2 `speckit_parser.py` (`tasks.md`→Plan+Provenance, [P]→parallel, Checkpoint). `success_check:` `python -m pytest tests/test_speckit_parser.py -q`
- [ ] T4.3 **golden схемы Spec-Kit** (страж дрейфа формата). `success_check:` `python -m pytest tests/test_speckit_parser.py -q -k golden`
**Manual:** реальный `/speckit.tasks`+preset → парсер видит success_check и версии.

### Phase 5: Детерминир. компилятор + граф происхождения
**Depends on:** Phase 1, Phase 4
- [ ] T5.1 `plan2beads.py` ядро на Plan AST + узлы spec/design + рёбра derived-from (§4,§5). `success_check:` `python -m pytest tests/test_plan2beads.py -q`
- [ ] T5.2 golden(команды) + idempotency(spec-node не дублится) + provenance-рёбра + negative. `success_check:` `python -m pytest tests/ -q`
- [ ] T5.3 `bd_client.py` (`--json`, `fetch_existing_keys`). `success_check:` `python -c "import lib.bd_client"`
**Manual:** dry-run на `bd init`: spec→design→epic→task parent-цепь; повторный compile того же spec_version не плодит spec-node.

### Phase 6: Версионная подложка (seams)
**Depends on:** Phase 3, Phase 5
- [ ] T6.1 `SeamRecord` (1:1 под OTel-span) → `.athena/seams.jsonl`, пины LLM-хопов. `success_check:` `python -m pytest tests/test_seams.py -q`
- [ ] T6.2 связь `spec_version ↔ graph_version` явна в записях. `success_check:` `python -m pytest tests/ -q -k version_link`
**Manual:** по `run_id` восстанавливается цепь spec_version→design_version→graph без дырки.

### Phase 7: Backedge research→/specify
**Depends on:** Phase 2, Phase 5
- [ ] T7.1 `planner_replan(trigger=spec_invalid)`: `refines`-ребро + бамп spec_version + новый spec-node. `success_check:` `python -m pytest tests/test_backedge.py -q`
**Manual:** кривая спека → research → spec v++ → перекомпиляция выводит новый граф из новой спеки.

### Phase 8: Athena MCP server
**Depends on:** Phase 5, Phase 6, Phase 7
- [ ] T8.1 `server.py`+`verbs.py`, глаголы §8 (вкл. `trace_down/up`). `success_check:` `cd mcp/athena_mcp && uv run python -c "import athena_mcp.server"`
- [ ] T8.2 toggle `ATHENA_SPECKIT` выбирает парсер; compile одинаков по контракту. `success_check:` `cd mcp/athena_mcp && uv run pytest -q`
**Manual:** intent→спека→design→граф; `trace_down(spec_version)` возвращает design+задачи.

### Phase 9: Интеграция с Hermes
**Depends on:** Phase 8
- [ ] T9.1 регистрация athena MCP в конфиге Hermes. `success_check:` `<проверка конфига Hermes>`
- [ ] T9.2 Hermes-плейбук: spec→align→tasks→compile→trace→report; автономные ответы на (суженный) question; backedge при spec_invalid. `success_check:` `test -f hermes_playbook.md`
**Manual:** Hermes одним промптом доводит до графа происхождения, сам отвечая на «как»-развилки.

### Phase 10: [ОТЛОЖЕНО] интерфейс исполнителя (stub)
**Depends on:** Phase 8
- [ ] T10.1 `ralph/INTERFACE.md`: контракт `bd ready→executor→внешний gate→close`, роутинг `autonomy:high`, ребро `implements` (commit→task), без реализации. `success_check:` `grep -q 'implements' ralph/INTERFACE.md && grep -q DEFERRED ralph/INTERFACE.md`
**Manual:** интерфейс достаточен, чтобы позже воткнуть Ralph без правки планнера/графа.

### Phase 11: End-to-end дог-фудинг (планирование + происхождение)
**Depends on:** Phase 9
- [ ] T11.1 реальная фича: spec→QRSPI→tasks→compile (on) → граф происхождения. `success_check:` `bd list --label kind:spec --json | jq 'length>0' && bd list --label kind:design --json | jq 'length>0'`
- [ ] T11.2 трассировка: `planner_trace_down(spec_version)` достаёт design+задачи; `trace_up` от задачи достаёт spec. `success_check:` `test -f trace-demo.md`
- [ ] T11.3 backedge: спека-бамп даёт новый spec_version, граф перевыводится. `success_check:` `bd list --label refines --json | jq 'length>0'`
- [ ] T11.4 `run-report.md`: версии (spec/design/graph) + где гейты. `success_check:` `test -f run-report.md`
**Manual:** сквозной трейс spec→design→task без дырки; design пиннут к (spec_version, run_id); [P] без лишних рёбер.

---

## 10. Acceptance (v3 закрыт)
- `pytest tests/` зелёный: AST+Provenance, оба парсера, golden Spec-Kit (страж версии), компилятор (golden+idempotency+provenance-рёбра+negative), versioning, seams, backedge, toggle.
- Hermes одним промптом → **граф происхождения**: spec-node → design-node → epic → task, с `success_check` у каждой задачи, в обоих режимах toggle.
- **Сквозной трейс реконструируем запросом, не догадкой:** `trace_down(spec_version)` ↓, `trace_up(task)` ↑.
- **design.md версионирован и пиннут** к `(spec_version, run_id)`; `spec_version ↔ graph_version` явна в seams.
- **Backedge** research→/specify бампает spec_version и перевыводит граф.
- implement НЕ реализован; `ralph/INTERFACE.md` определяет ребро `implements` и контракт так, что втыкается позже без правки планнера.
- Установка `bash install.sh`; состояние в self-hosted git/Dolt, переживает kill сессий.

## 11. Риски / не забыть
- **Версионирование design-выхода — НЕ опция.** Пропустишь пиннинг — трейс рвётся на самом важном хопе (интенция→план). Это инвариант 2, не «nice to have».
- **Граница «что/как»** — Spec-Kit НЕ лезет в техстек, QRSPI НЕ переписывает «зачем». Иначе дрейф и дубль планирования.
- **Multi-level parent-child** — проверить в bd; если нет, spec→design через `related --label derived-from`.
- **Version coupling на Spec-Kit** — golden-страж (T4.3) обязан падать при смене схемы tasks.md; pinned ref в vendor/.
- **Beads version flux** — pinned v1.x (Dolt); durable артефакт = Dolt-репо; `bd_client` тесты ловят дрейф.
- **Question в автономе** — Hermes отвечает только на «как»-развилки (на «что» отвечает спека); иначе зависание.
- **Токены** — 3-слой дорогой; смягчается self-hosted кластером; рутину гонять в режиме off.
- **implement отложен** — держать границу scope на графе происхождения.
