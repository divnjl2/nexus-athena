# Athena — Plan для Опуса. Надстройка v3.2 — Coverage-backedge (замыкание code→spec)

> **Статус:** дельта поверх v3 + v3.1. НИЧЕГО не отменяет — только добавляет нижнюю дугу
> обратной связи. **Чистое добавление: 0 правок AST / parser / compiler** → не может сломать
> v3/v3.1 (доказано: 44 существующих теста зелёные после интеграции).
>
> **Зачем:** v3.1 замкнул трейс СВЕРХУ — `scenario_failed`: сценарий покраснел → код уехал от
> спеки. Но связь `satisfies` (task→scenario) и полнота «у кода есть требование» остаются
> **декларацией**: v3.1 не видит (a) сценарий проходит, но не покрывает `files` таска — ребро
> объявлено, но ложно; (b) ветку кода, которую не трогает ни один сценарий — код без
> требования. Обе дыры найдены пилотом qa_unit. v3.2 читает их детерминированно из
> `coverage.xml`, снятого прогоном сценариев, и превращает пунктирную стрелку `code→spec` в
> сплошную.

---

## 0. Центральный сдвиг v3.2

**Ребро `satisfies` становится coverage-proven, и появляется зеркальный backedge `spec_gap`.**

```
v3.1:  scenario RED   ──scenario_failed──►  «код уехал от спеки»    (сверху вниз)  ✅ было
v3.2:  code UNCOVERED ──spec_gap─────────►  «спека отстала от кода»  (снизу вверх)  ⟵ добавили
```

Спека была жива с одной стороны снизу (провал сценария). Теперь жива и со второй: **код, не
покрытый ни одним сценарием, — это дрейф спеки от кода**, пойманный автоматически, а не
периодическим аудитом.

---

## 1. Новые инварианты (к §1 v3 / v3.1)

16. **`satisfies` coverage-proven:** задача, у которой `verifies` непуст И есть source-`files`,
    ОБЯЗАНА иметь эти source-файлы покрытыми при прогоне её сценариев. Source без покрытия →
    ребро `satisfies` объявлено, но ложно → **fail-closed** (Seam 10).
17. **`spec_gap` — зеркало `scenario_failed`:** ветка кода без сценария = дрейф спеки от кода
    → триггер `planner_replan(trigger="spec_gap")`.
18. **Coverage — вход детерминированного хопа** (инвариант 2): `coverage.xml` снимается
    прогоном сценариев; шов и трейс — чистые, stdlib-only, без LLM.
19. **Test-файлы ≠ source:** обратную ногу доказывает покрытие SOURCE, не самих тестов
    (тест — раннер сценария, а не доказываемый код).

---

## 2. AST — БЕЗ изменений

v3.2 переиспользует уже существующие поля v3.1: `Task.files`, `Task.verifies`, `Plan.scenarios`,
`Scenario.run_cmd`. **Новых полей не нужно** — это и делает надстройку неломающей. (Опционально
позже: `Provenance.coverage_version` = хеш `coverage.xml`, пиннут к `scenario_version`, если
захотим версионировать сам артефакт покрытия. Не требуется для гейта.)

---

## 3. Граф происхождения — третья дуга

v3.1 дал `spec ◄verifies─ scenario ◄satisfies─ task`. v3.2 навешивает на `satisfies` **статус
покрытия** и добавляет обратное ребро `spec_gap` от осиротевшей ветки:

```
spec ──derived-from──► design ──► epic ──► task
 ▲                                          │
 │ verifies                       satisfies │  (v3.2: помечено proven / unproven по coverage)
scenario ◄─────────────────────────────────┘
 ▲
 └─ code branch ──spec_gap──► (нет сценария → backedge к /specify или снос мёртвого кода)
```

`planner_trace_proof` (v3.1) отвечал «доказано ли требование». v3.2 добавляет ось: **«покрыт ли
код требования и нет ли кода без требования»**.

---

## 4. Реализация (уже в коде, ветка `feat/v3.2-coverage-backedge`)

- **`lib/coverage_backed.py`** — `parse_coverage(xml)` (Cobertura → covered lines + uncovered
  branches, stdlib) + `trace_coverage(plan, cov)` → `{proven_edges, unproven_edges, spec_gaps,
  replan_trigger}`. Чистое, детерминированное.
- **`lib/seams.py :: seam_coverage_backed(plan, cov)`** — **Seam 10**, fail-closed: падает на
  фальшивых рёбрах `satisfies`. Orphan-ветки едут в trace-отчёт, не в гейт.
- **`athena.py`** — `seam coverage_backed <front> --coverage <xml>` (гейт) +
  `trace-coverage <front> --coverage <xml>` (отчёт, CLI-лицо `planner_trace_coverage`).
- **`tests/test_coverage_backed.py`** — 8 тестов: parse, proven/unproven/orphan, meta-task
  игнор, seam pass/fail.

---

## 5. Новый триггер replan (к §5 v3.1)

`planner_replan` получает `spec_gap` (зеркало `scenario_failed`):
1. ветка кода без сценария → развилка:
   - **мёртвый код** (требования нет и не будет) → снести;
   - **потерянное требование** (код нужен, спека молчит) → backedge `code → /specify`, бамп
     `spec_version` → регенерация сценариев/графа.
2. `satisfies_unproven` (фальшивое ребро) → reopen задачи: её сценарий не доказывает её код.

---

## 6. Новый MCP-глагол (к §6 v3.1)

| Глагол | Действие |
|---|---|
| `planner_trace_coverage` | обход `satisfies` с покрытием + список `spec_gaps`; вход для `planner_replan(spec_gap)` |

CLI-эквивалент готов (`athena.py trace-coverage`); MCP-регистрация — тонкая обёртка над ним.

---

## 7. Фазы

### Phase D: Coverage reader + Seam 10 (ГОТОВО)
- [x] D.1 `lib/coverage_backed.py` (parse + trace). `success_check:` `pytest tests/test_coverage_backed.py -q -k parse or trace`
- [x] D.2 `seam_coverage_backed` fail-closed на фальшивых рёбрах. `success_check:` `pytest tests/test_coverage_backed.py -q -k seam`
- [x] D.3 CLI `seam coverage_backed` + `trace-coverage`. `success_check:` `python athena.py --speckit off trace-coverage qa-farm/unit/plan.md --coverage <xml>`

### Phase E: spec_gap backedge (в replan-слое)
- [ ] E.1 `planner_replan(trigger="spec_gap")` — развилка мёртвый-код / потерянное-требование. `success_check:` `pytest tests/test_backedge.py -q -k spec_gap`
- [ ] E.2 `planner_trace_coverage` MCP-глагол поверх `trace_coverage`. `success_check:` `pytest tests/ -q -k trace_coverage`

### Правка Phase 11 (E2E)
- [ ] после compile: `seam coverage_backed` зелёный (нет фальшивых `satisfies`); `trace-coverage` показывает `spec_gaps`. `success_check:` есть отчёт с `proven`/`unproven`/`spec_gaps`.

---

## 8. Acceptance

- `pytest tests/test_coverage_backed.py` зелёный (8), существующие 44 не тронуты.
- `seam coverage_backed` падает, если у задачи `verifies`+source, а source не покрыт.
- `trace-coverage` перечисляет `spec_gaps` (осиротевшие ветки) и ставит `replan_trigger`.
- **Самозамыкание доказано:** прогон на `qa-farm/unit/plan.md` покрытием самого qa_unit →
  `seam passed:true` (16 рёбер proven, 0 fake), `9 spec_gaps`, `replan_trigger: spec_gap`.
- Ноль правок AST/parser/compiler; ноль LLM в шве.

---

## 9. Что v3.2 даёт по сути

v3.1 замкнул спеку сверху; v3.2 — снизу на уровне КОДА, а не только требований. Петля
`spec → scenario → code → (coverage) → spec` становится настоящей: декларированное «в две
стороны» теперь и доказано в две стороны. Это отложенный v4 из README бандла, собранный «из
существующих кусков» — кусок и есть `coverage.xml`. Остаётся только `implements`-ребро
(commit↔task, реальный SHA) — ортогонально и дешевле после этого шва.
