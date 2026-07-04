# Athena — Plan для Опуса. Надстройка v4 — Implements-port (commit↔task, executor-agnostic)

> **Статус:** дельта поверх v3 + v3.1 + v3.2. Последний кусок петли. Чистое добавление:
> **0 правок AST / parser / compiler**. Полный сьют зелёный после интеграции.
>
> **Зачем:** v3.1 замкнул `spec→scenario` (сверху), v3.2 — `code→spec` покрытием (снизу).
> Остаётся вписать в граф **какой РЕАЛЬНЫЙ коммит реализовал каждую задачу** — ребро
> `implements` (commit→task). Ключевой принцип оператора: **это ПОРТ, а не хардкод исполнителя.**
> Фрейм НЕ должен зависеть от того, *кто* пишет код. Hermes, OpenHands, Claude Code, Ralph —
> каждый адаптер под один контракт; Athena видит только `{task_id, commit_sha, checks_passed}`.

---

## 0. Центральный сдвиг v4

**`implements` (commit→task) заполняется через executor-ПОРТ, а не встроенным исполнителем.**

```
       ┌─ HermesAdapter ─┐
ready  ├─ OpenHandsAdapter┤   Executor.implement(task)   ExecutorResult          seam.implements_backed
task ──┼─ ClaudeCodeAdapter├──────────────────────────►  {task_id, commit_sha,  ──► pin implements edge
       └─ RalphAdapter ───┘   (HOW is the adapter's       checks_passed}             (commit->task) + bd close
                               business — Athena is blind)
```

Athena никогда не заглядывает внутрь исполнителя. Контракт гарантирует единственное: **в граф
пришёл реальный SHA**. Это и делает фрейм переносимым между исполнителями без единой правки ядра.

---

## 1. Новые инварианты

20. **`implements` пиннит РЕАЛЬНЫЙ sha** (≥7 hex). Пустой/фейковый sha → ребро commit→task ложно
    → **fail-closed** (Seam 11). Задача-фантом (нет в плане) — тоже ложь → fail.
21. **Executor-agnostic порт:** реализация зависит от адаптера, не от ядра. Athena принимает
    `ExecutorResult`, не знает и не хочет знать *как* он получен.
22. **Закрытие только при зелёном чеке:** `bd close` задачи — лишь если `checks_passed` (её
    success_check прошёл). Иначе ребро есть, задача открыта.

---

## 2. AST — без изменений

Переиспользует `Task.id` + существующие ключи графа (`athena:<slug>:<id>`). Ребро `implements`
эмитится тем же паттерном, что `validates`/`satisfies`/`tracks` (`bd dep add … --type implements`).

---

## 3. Граф — последняя дуга

```
spec ◄verifies─ scenario ◄satisfies─ task ◄implements─ commit
 ▲                  (v3.1)    (v3.2 coverage-proven)      (v4, реальный SHA от любого исполнителя)
 └── петля замкнута: spec → scenario → code → commit → task, доказательство на КАЖДОМ ребре
```

---

## 4. Реализация (ветка `feat/v4-implements-port`)

**Phase F — порт + ребро + шов**
- `lib/executor.py` — `ExecutorResult`, **`Executor` Protocol (порт)**, `validate_results`
  (real-sha guard), `implements_commands` (детерминированная эмиссия bd-рёбер).
- `lib/seams.py :: seam_implements_backed` — **Seam 11**, fail-closed на фейковом sha / фантом-таске.
- `tests/test_executor.py` — 7 тестов (порт duck-types любой объект с контрактом; edge/close/seam).

**Phase G — verbs + backedge**
- `verbs.planner_close_task(front, task_id, commit_sha, checks_passed, executor)` — валидирует
  sha → пиннит `implements` → `bd close`. Executor-agnostic.
- `verbs.planner_trace_implements(front)` — какие задачи имеют коммит, какие открыты.
- `verbs.replan("implements_missing")` — handoff в executor-адаптер, затем `planner_close_task`.
- `server.py` — MCP-глаголы `planner_close_task`, `planner_trace_implements`.
- `tests/test_verbs.py` +4.

Адаптеры (тонкие, отдельно от ядра — примеры контракта):
```python
class ClaudeCodeAdapter:            # или Hermes / OpenHands / Ralph
    name = "claude_code"
    def implement(self, task) -> ExecutorResult:
        sha = ...                   # исполнитель написал код и закоммитил — ЕГО дело как
        passed = ...                # прогнал task.success_check
        return ExecutorResult(task.id, sha, passed, self.name)
```

---

## 5. replan trigger (к §5 v3.2)

`implements_missing` — у задачи нет коммита: handoff `export_ready → адаптер`, затем
`planner_close_task` пиннит ребро. Athena не исполняет — только принимает результат.

---

## 6. MCP-глаголы (к §6 v3.2)

| Глагол | Действие |
|---|---|
| `planner_close_task` | пиннит `implements` (commit→task, real SHA) + `bd close` |
| `planner_trace_implements` | какие задачи реализованы (есть коммит) vs открыты |

---

## 7. Фазы

### Phase F: порт + Seam 11 (ГОТОВО)
- [x] F.1 `lib/executor.py` — port + validate + implements_commands. `success_check:` `pytest tests/test_executor.py -q`
- [x] F.2 `seam_implements_backed`. `success_check:` `pytest tests/test_executor.py -q -k seam`

### Phase G: verbs + backedge (ГОТОВО)
- [x] G.1 `planner_close_task` + `planner_trace_implements`. `success_check:` `pytest mcp/athena_mcp/tests/test_verbs.py -q -k "close_task or trace_implements"`
- [x] G.2 `replan("implements_missing")` + server-регистрация. `success_check:` `pytest mcp/athena_mcp/tests/test_verbs.py -q -k implements_missing`

---

## 8. Acceptance

- `pytest tests/test_executor.py` (7) + `mcp/.../test_verbs.py` (+4) зелёные; полный сьют без регрессии.
- Порт принимает ЛЮБОЙ объект с `{name, implement}` (duck-type isinstance).
- Фейковый/пустой sha → Seam 11 падает; реальный sha к реальной задаче → passed.
- `planner_close_task` пиннит `implements` и закрывает только при зелёном чеке.
- Ноль правок AST/parser/compiler; ноль привязки к конкретному исполнителю.

---

## 9. Что v4 даёт по сути

Петля замкнута полностью: `spec → scenario → design → task → commit`, с доказательством на каждом
ребре (verifies / satisfies-coverage / implements-sha). И — главное — **фрейм переносим**: смена
исполнителя (Hermes↔OpenHands↔Claude Code↔Ralph) не трогает ядро, только адаптер под порт.
SDD стал полностью-верифицируемым И executor-agnostic контрактом.
