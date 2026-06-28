# Athena v4 — Замыкание живой двусторонней связи код ↔ спеки

> Полный план для Опуса. **Не новый слой** — замыкание уже зарезервированного ребра
> `implements` + обратный обход существующего графа + тот же версионный лейбл на коммите.
> Мы спроектировали v3/v3.1 так, что петля закрывается **заполнением placeholder'а**,
> а не переделкой.
>
> Опирается на: [`athena-final-opus-plan-v3.md`](./athena-final-opus-plan-v3.md) (провенанс-граф +
> зарезервированное ребро `implements`), [`athena-opus-plan-v3.1-harness.md`](./athena-opus-plan-v3.1-harness.md)
> (scenario-harness + `verifies`/`satisfies` + `success_check`), `ralph/INTERFACE.md`
> (deferred executor — точка `bd close`, куда втыкается заполнение).

---

## §0 Двусторонность УЖЕ почти собрана — не хватает одного

Куски лежат порознь; нужно соединить три. Что уже есть:

| Кусок | Откуда | Что умеет сейчас |
|---|---|---|
| `derived-from` рёбра | v3 §4 | план вниз: spec→design→task |
| `verifies`/`satisfies` | v3.1 §3 | сценарий↔требование, задача↔сценарий |
| `success_check` = запуск сценария | v3.1 | проверяемость (exit 0 = соответствует) |
| `implements` placeholder | v3 §4 (`commit ─implements► task`) | **зарезервировано, пусто** |
| версии-лейблы (`spec_version` и пр.) | v3 §4 | каждый узел знает свою версию |
| `bd close` с SHA в сообщении | нативная конвенция Beads | **уже умеет** привязать коммит к задаче |
| seam-записи с in/out версиями | v3 §6 | цепь версий явная |

Двусторонности не хватает **одного** — заполнить `implements` реальным SHA. Всё остальное
для обхода в обе стороны уже есть.

```
ПЛАН (построено, v3+v3.1)                    КОД (actual)
spec_v ─► design_v ─► task                    commit, файлы, тесты
   └─ derived-from ─┘ │                              ▲
                      └──── implements ◄─────────────┘  ← placeholder, кладём SHA
   scenario ─validates► spec                          (ребро уже определено, пустое)
   task ─tracks► scenario
```

---

## §1 Как соединяется из этих кусков (ноль новой семантики)

**Вниз (план→код) — уже работает.** `trace_down` обходит `derived-from`: от `spec_version`
→ design → задачи. Готово в v3. v4 добавляет лишь финальный хоп `task → implements → commit`
(по заполненному ребру).

**Вверх (код→план) — проход по уже определённым рёбрам:**
```
commit ─implements► task ─satisfies(tracks)► scenario ─verifies(validates)► spec
```
Все рёбра кроме `implements` уже построены (v3.1). Заполняем `implements` — и обратный
обход готов. **Новый глагол `trace_up(commit)`, но нулевая новая семантика графа** — это
проход существующих рёбер в обратную сторону.

**Живость (поперёк) — из готового `success_check`.** Задачин `success_check` уже = запуск
сценария (v3.1). Гоняешь его на текущем коде → exit 0 = код всё ещё соответствует
требованию. Механизм проверки встроен, **ничего не добавляем** (никакого нового
`conforms`-ребра — живость это прогон, а не декларация).

---

## §2 Версионная сшивка — из лейблов, что уже есть

Каждый узел в v3 несёт `spec_version`/`scenario_version` лейблами. Единственное
добавление — **тот же лейбл на коммите** при `bd close`. Тогда:
- рассинхрон видно сравнением лейблов (коммит под `spec_version:3`, спека уже `:4` → устарел);
- это **переиспользует** существующую seam-цепь версий, не строит новую.

Заполнение `implements` минимально = при `bd close` навесить на закрытую задачу лейблы:
`implements`, `commit:<full_sha>`, `spec_version:<sv>`, `scenario_version:<scv>`. Нативная
конвенция Beads (ID issue в сообщении коммита) уже привязывает SHA — мы лишь фиксируем его
+ версии лейблом. **Отдельный `kind:commit` узел не обязателен**; `commit:<sha>` лейбл на
задаче достаточен для обхода и для детектора. (Если позже понадобится коммит как узел
первого класса — добавим, но v4 этого не требует.)

---

## §3 Двусторонний обход целиком из имеющегося

```
trace_down(spec_v):  spec ─derived-from► design → task ─implements► commit   [v3 + заполненный implements]
trace_up(commit):    commit ─implements► task ─satisfies► scenario ─verifies► spec   [всё рёбра v3.1]
trace_proof(spec_v): гоняет success_check сценариев на коде → соответствие сейчас   [v3.1 success_check]
```

| Направление | Верб | Вопрос |
|---|---|---|
| вниз (план→код) | `planner_trace_down(spec_version)` | «что в коде реализует это требование» |
| вверх (код→план) | `planner_trace_up(commit_sha)` | «зачем существует этот код» |
| поперёк (живость) | `planner_trace_proof(spec_version)` | «соответствует ли код спеке **сейчас**» |

`trace_up` сегодня принимает `task_label` и идёт `task→epic→design→spec`. v4: добавляет
вход по `commit_sha` — резолв задачи с лейблом `commit:<sha>` → существующий путь вверх.

---

## §4 Что реально нужно достроить (минимум, всё из кусков)

1. **`bd close` пиннит `commit_sha` → заполняет `implements`** (ребро/лейбл уже есть, кладём
   в него значение). Нативная Beads-конвенция + `--label implements`.
2. **Тот же версионный лейбл на коммит** (`spec_version:<sv>`, `scenario_version:<scv>`) —
   механизм лейблов уже есть.
3. **`trace_up(commit)` — обход по уже определённым рёбрам в обратную сторону** (новый
   глагол, нулевая новая семантика).
4. **Детектор рассинхрона** — сравнение лейбла версии коммита с текущей + перепрогон
   `success_check` устаревших.

---

## §5 Фазы реализации

### Phase A — заполнить `implements` (Мост 1)
**Goal:** `bd close` фиксирует SHA + версии лейблами на закрытой задаче.
**Depends on:** none
- [ ] A.1 `lib/bd_client.py`: `record_implementation(task_label, commit_sha, *, spec_version, scenario_version, run)` — навешивает лейблы `implements`, `commit:<sha>`, `spec_version:<sv>`, `scenario_version:<scv>` (идемпотентно).
  - success_check: `pytest tests/test_implements_fill.py -q`
- [ ] A.2 `ralph/INTERFACE.md`: handoff-шаг `bd close` вызывает `record_implementation` с SHA gate-прошедшего коммита. Контракт, без реализации Ralph.
  - success_check: `grep -q record_implementation ralph/INTERFACE.md`
- [ ] A.3 Верб `planner_record_commit(task_label, commit_sha, spec_version, scenario_version)` в `verbs.py` + `server.py` (@mcp.tool).
  - success_check: `pytest mcp/athena_mcp/tests/test_record_commit.py -q`

### Phase B — двусторонний трейс (Мост 2, обратный обход)
**Goal:** `trace_up(commit)` и `trace_down→commit` обходят обе стороны по существующим рёбрам.
**Depends on:** Phase A
- [ ] B.1 `planner_trace_up` принимает `commit_sha` ИЛИ `task_label`: при SHA резолвит задачу по `commit:<sha>` → существующий путь вверх до spec.
  - success_check: `pytest mcp/athena_mcp/tests/test_trace_up_commit.py -q`
- [ ] B.2 `planner_trace_down` добавляет финальный хоп `task → commit:<sha>`.
  - success_check: `pytest mcp/athena_mcp/tests/test_trace_down_commit.py -q`

### Phase C — детектор рассинхрона (живость)
**Goal:** бамп spec_version → пометить устаревшие коммиты → перепрогнать их `success_check`.
**Depends on:** Phase A, Phase B
- [ ] C.1 `planner_detect_drift(current_spec_version)` — находит задачи с `spec_version:<old>` ≠ current, ставит `stale:spec_version:<old>`, возвращает список.
  - success_check: `pytest mcp/athena_mcp/tests/test_detect_drift.py -q`
- [ ] C.2 `planner_reverify_stale(spec_version)` — для устаревших собирает их сценарии (обход `implements→satisfies→…`) и гоняет `success_check`; красный = код отстал от спеки.
  - success_check: `pytest mcp/athena_mcp/tests/test_reverify_stale.py -q`
- [ ] C.3 Связать с `planner_replan(trigger="spec_invalid")`: бамп spec_version авто-дёргает `detect_drift`.
  - success_check: `pytest mcp/athena_mcp/tests/test_replan_triggers_drift.py -q`

---

## §6 MCP-вербы

| Верб | Статус | Делает |
|---|---|---|
| `planner_record_commit` | NEW | заполняет `implements` + version-лейблы на закрытой задаче |
| `planner_trace_up` | EXT | принимает `commit_sha` (обратный обход существующих рёбер) |
| `planner_trace_down` | EXT | финальный хоп до commit |
| `planner_detect_drift` | NEW | помечает устаревшие по версии задачи |
| `planner_reverify_stale` | NEW | перепрогон `success_check` устаревших |

Итого: 17 → **20** вербов. Семантика графа не меняется — только заполнение + обход + сравнение лейблов.

---

## §7 Критерии приёмки (догфуд на `examples/snake_game/`)

1. `record_commit("…:T1.1", "<sha>", sv, scv)` навешивает `implements` + `commit:<sha>` +
   version-лейблы (идемпотентно при повторе).
2. `trace_up("<sha>")` возвращает `commit → T1.1 → S3.1 → R3` (правая→левая цепь, всё по
   существующим рёбрам).
3. `trace_down(spec_version)` доходит до коммитов: `R3 → S3.1 → T1.1 → commit`.
4. `detect_drift(new_spec_version)` после бампа помечает старые задачи `stale:*`.
5. `reverify_stale` гоняет `success_check` помеченных, возвращает pass/fail по каждой.
6. Детерминизм: компилятор плана не изменился (golden-тесты v3/v3.1 зелёные); вся правота
   правой половины — в `bd_client` + verbs, не в `plan2beads`.

---

## §8 Что НЕ делаем (границы)

- **НЕ новый слой графа.** Ноль новых видов рёбер/узлов сверх заполнения зарезервированного
  `implements`. Никакого `conforms` — живость это прогон `success_check`, а не ребро.
- **НЕ переписываем Ralph.** Executor pluggable (`ralph/INTERFACE.md`); трогаем только
  точку `bd close`.
- **НЕ тащим git-парсинг в компилятор.** `plan2beads` остаётся pure AST→commands.
- **НЕ заводим вторую систему версий** — переиспользуем контент-хэши v3 как лейблы справа.

---

## §9 Риски / открытые вопросы

- **R-1 форма `implements`.** v3 §162 определяет «ID issue в сообщении коммита + `--label
  implements`». Решить: лейбл на задаче (минимум, выбран) vs типизированное ребро к
  commit-узлу. Лейбл достаточен для обхода и детектора — выбираем его; узел добавим позже,
  если понадобится. **Проверить, что выбранная форма ищется через `bd list --label`.**
- **R-2 SHA до/после gate.** `record_commit` только после зелёного gate (gate авторитетен,
  `ralph/INTERFACE.md`).
- **R-3 N коммитов на задачу.** Допускаем N лейблов `commit:<sha>`; trace берёт последний.
- **R-4 стоимость reverify.** По умолчанию reverify только сценариев, затронутых бампнутым
  требованием (через `trace_down`), не всей репы.

---

## §10 Одной строкой

v4 — это **замыкание зарезервированного ребра + обратный обход существующего графа**: один
заполненный `implements` (SHA + версионный лейбл) превращает граф из снимка «как построили»
в живую модель соответствия, где «весь ли код соответствует текущей спеке» — прогон, а не вера.
