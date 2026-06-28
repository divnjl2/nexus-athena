# Athena — Plan для Опуса. Надстройка v3.1 — Harness-слой (живой контракт спеки)

> **Статус:** дельта поверх закреплённого `athena-final-opus-plan-v3.md`. Опус читает v3 + этот файл.
> v3.1 НИЧЕГО не отменяет в v3 — только добавляет слой исполняемых сценариев между `/specify` и
> `success_check`, чем превращает спеку из артефакта в **постоянно-верифицируемый контракт**.
>
> **Зачем:** в v3 `success_check` — россыпь произвольных команд, а связь «спека↔код» односторонняя
> (derived-from вниз). Спека после реализации рискует стать мёртвым грузом: ничто не проверяет, что
> код всё ещё ей соответствует, кроме дорогого периодического аудита агентом (не масштабируется).
> v3.1 чинит это паттерном BDD: требование → исполняемый сценарий Given-When-Then → этот сценарий
> и есть `success_check`. Спека верифицируется хоть сто раз за сессию, почти бесплатно (AI-Native Harness).

---

## 0. Центральный сдвиг v3.1

**`success_check` перестаёт быть произвольной командой и становится запуском сценария требования.**
Раньше gate проверял «pytest зелёный». Теперь — «поведение соответствует требованию X». Это замыкает трейс снизу: спека жива не только сверху (backedge `research→/specify`), но и снизу — **сломал код сценарий → красный harness → дрейф реализации от спеки пойман автоматически**.

Конвейер v3 расширяется одним шагом:
```
/specify (что+зачем + acceptance criteria EARS)
   → derive scenarios: EARS → исполняемый Given-When-Then, сгруппированы по требованиям   ← НОВОЕ
   → QRSPI (как) → tasks, где success_check = ЗАПУСК сценария требования
```

**Вкусовщина автора = реальная развилка, принимаем его сторону:** НЕ тащим Gherkin/Cucumber — их парсеры сами становятся источником проблем при росте (ещё один хрупкий шов, как мы боялись за Spec-Kit). Вместо этого **генерим исполняемый тест прямо из EARS-критериев Spec-Kit** (`WHEN…THE SYSTEM SHALL…` — это уже почти Given-When-Then). Сценарии выводятся из acceptance-критериев, а не пишутся отдельно → остаются синхронны со спекой by construction.

---

## 1. Новые/усиленные инварианты (добавить к §1 v3)

11. **`success_check` = запуск сценария требования**, не произвольная команда. Задача без привязанного сценария → **ошибка компиляции** (усиливает инвариант 9).
12. **Сценарии выводятся из acceptance-критериев спеки** (EARS→GWT), не авторятся вручную → синхронны со спекой.
13. **Генерация сценариев — LLM-хоп → версионируем ВЫХОД** (инвариант 2 распространяется): `scenario_version`, пиннут к `spec_version`. Исполняемый тест кэшируется по `scenario_version` (не регенерим на каждый прогон).
14. **Никакого Gherkin-парсера.** Сценарий = человекочитаемый GWT (версионируется) + сгенерённый исполняемый тест в раннере проекта (pytest и т.п.). Контракт: «success_check исполняет сценарий, exit 0 = требование выполнено».
15. **Спека живая снизу:** проваленный сценарий = дрейф кода от спеки = триггер `planner_replan(trigger="scenario_failed")`.

---

## 2. Изменение AST (правка §3 v3)

```python
@dataclass(frozen=True)
class Provenance:
    spec_version: str
    scenario_version: str     # НОВОЕ v3.1: выход EARS→GWT хопа, пиннут к spec_version
    design_version: str
    run_id: str

@dataclass(frozen=True)
class Scenario:               # НОВОЕ v3.1
    id: str                   # "S1.2"
    requirement_key: str      # требование спеки, которое верифицирует
    gwt_text: str             # человекочитаемый Given-When-Then
    run_cmd: str              # исполнимая команда запуска сценария (exit 0 = passed)

@dataclass(frozen=True)
class Task:
    id: str
    title: str
    success_check: str        # = run_cmd сценария(ев), НЕ произвольная команда
    verifies: tuple[str, ...] = ()   # НОВОЕ v3.1: id сценариев, которые задача satisfies
    files: tuple[str, ...] = ()
    parallel: bool = False
    autonomy: str = "default"

@dataclass(frozen=True)
class Plan:
    title: str
    overview: str
    out_of_scope: tuple[str, ...]
    provenance: Provenance
    scenarios: tuple[Scenario, ...]   # НОВОЕ v3.1
    phases: tuple[Phase, ...]
```

---

## 3. Изменение графа происхождения (правка §4 v3)

Новый узел и два ребра — замыкают трейс по верификации:

| Семантика | Реализация в Beads |
|---|---|
| узел `scenario` | issue с `--label kind:scenario --label athena:scenario:<scenario_version>` |
| ребро `verifies` | `related --label verifies` от scenario-node к spec-node (сценарий верифицирует требование) |
| ребро `satisfies` | `related --label satisfies` от task к scenario (задача выполняет сценарий; её success_check его гоняет) |

Граф становится:
```
spec ──derived-from──> design ──> epic ──> task
  ▲                                          │
  │ verifies                        satisfies│
scenario ◄─────────────────────────────────-┘
  ▲                                          
  └─ commit ──implements──> task (отложено, Phase 10 v3)
```

**Трассировка обретает третью ось** (поперёк derived-from): `planner_trace` теперь отвечает не только «что выросло / зачем код», но и **«доказано ли требование X прямо сейчас»** — обход `verifies`/`satisfies` + статус сценариев. Этого в v3 не было.

---

## 4. Изменение компилятора (правка §5 v3)

`plan2beads` дополнительно (детерминированно, document order):
1. **scenario-node** на каждый `Scenario` (идемпотентно по `scenario_version`): `kind:scenario` + лейблы версий.
2. ребро `verifies`: scenario → spec-node по `requirement_key`.
3. ребро `satisfies`: task → scenario по `Task.verifies`.
4. **тело issue:** `success_check` = `run_cmd` привязанного сценария (валидация: `Task.verifies` непуст и резолвится, иначе `CompileError`).

Остальное ядро — без изменений (чистое, без LLM, идемпотентность через `existing_keys`).

---

## 5. Новый триггер replan (правка §7 v3)

`planner_replan` получает триггер `scenario_failed`:
1. harness требования покраснел → дрейф кода от спеки.
2. Развилка по причине:
   - **код не дотягивает до сценария** (сценарий верный) → reopen task, ещё итерация исполнителя [Phase 10];
   - **сценарий неверен** (требование изменилось/кривое) → backedge `research/scenario → /specify`, бамп `spec_version` → перегенерация сценариев и графа.
3. Спека-корень остаётся корнем, но теперь уточняется и сверху (research), и снизу (failed scenario).

---

## 6. Новые MCP-глаголы (добавить к §8 v3)

| Глагол | Действие |
|---|---|
| `planner_scenarios` | EARS acceptance-критерии спеки → исполняемые GWT-сценарии, сгруппированы по требованиям; `scenario_version` пиннут к `spec_version` |
| `planner_verify` | запустить сценарии требования (harness) → `{requirement, passed, failed[]}` — это runner gate'а |
| `planner_trace_proof` | обход `verifies`/`satisfies`: «доказано ли требование X сейчас» + покрытие требований сценариями |

`planner_trace_down/up` (v3) — без изменений; добавляется ось доказательства через `trace_proof`.

---

## 7. Новые фазы (вставляются в план v3)

> Нумерация — буквенная, чтобы не ломать Phase 0–11 v3; указаны якоря зависимостей к фазам v3.

### Phase A: Scenario-слой (EARS→GWT harness)
**Depends on:** Phase 2 v3 (Spec-Kit как корень)
- [ ] A.1 `skills/scenario-format/SKILL.md` — контракт GWT-сценария + правило «выводится из EARS, без Gherkin-парсера». `success_check:` `grep -qi 'given.*when.*then' skills/scenario-format/SKILL.md`
- [ ] A.2 `lib/versioning.py`: `scenario_version` пиннут к `spec_version`; сценарии в `thoughts/scenarios/<spec_version>/`. `success_check:` `python -m pytest tests/test_versioning.py -q -k scenario`
- [ ] A.3 `commands/scenarios.md` (`/athena.scenarios`): EARS-критерии → исполняемые GWT-тесты в раннере проекта. `success_check:` `test -f commands/scenarios.md`
**Manual:** `/specify` даёт acceptance EARS → `/athena.scenarios` генерит исполняемые сценарии, сгруппированные по требованиям; повторный запуск даёт новый `scenario_version` (LLM-хоп).

### Phase B: AST + компилятор под сценарии
**Depends on:** Phase A, Phase 1 v3, Phase 5 v3
- [ ] B.1 правка `lib/ast.py` (§2: `Scenario`, `Provenance.scenario_version`, `Task.verifies`, `Plan.scenarios`). `success_check:` `python -m pytest tests/test_ast.py -q -k scenario`
- [ ] B.2 `speckit_parser`: вытащить `verifies` у задач + список сценариев в Plan. `success_check:` `python -m pytest tests/test_speckit_parser.py -q -k verifies`
- [ ] B.3 `plan2beads`: scenario-node + рёбра `verifies`/`satisfies`; `success_check`=run_cmd; задача без `verifies` → `CompileError`. `success_check:` `python -m pytest tests/test_provenance.py -q -k scenario`
- [ ] B.4 golden + idempotency (scenario-node не дублится по scenario_version). `success_check:` `python -m pytest tests/ -q`
**Manual:** dry-run на `bd init`: spec←verifies←scenario, task→satisfies→scenario; success_check задачи = команда сценария.

### Phase C: Harness-runner + scenario_failed backedge
**Depends on:** Phase B, Phase 7 v3 (backedge)
- [ ] C.1 `planner_verify` гоняет сценарии требования, агрегирует pass/fail. `success_check:` `python -m pytest tests/test_harness.py -q`
- [ ] C.2 `planner_replan(trigger="scenario_failed")`: развилка код/сценарий, при кривом сценарии — бамп spec_version + регенерация. `success_check:` `python -m pytest tests/test_backedge.py -q -k scenario_failed`
- [ ] C.3 `planner_trace_proof` — ось доказательства + покрытие требований. `success_check:` `python -m pytest tests/ -q -k trace_proof`
**Manual:** намеренно сломать код под требованием → harness краснеет → `scenario_failed` корректно маршрутизирует.

### Правка Phase 11 v3 (E2E)
- [ ] добавить: **«требование доказано»** — после compile у каждого требования есть ≥1 `verifies`-сценарий, и `planner_trace_proof` показывает покрытие. `success_check:` `bd list --label kind:scenario --json | jq 'length>0'`
- [ ] добавить: сломать реализацию → harness падает → `scenario_failed` replan срабатывает. `success_check:` `test -f harness-demo.md`

---

## 8. Acceptance (v3.1 поверх v3)
- Всё из v3 + ниже.
- `pytest tests/` зелёный, включая scenario-AST, parser `verifies`, provenance scenario-рёбра, harness, scenario_failed backedge, trace_proof.
- **Каждое требование спеки покрыто ≥1 исполняемым сценарием**, выведенным из его EARS-критериев (не вручную).
- **`success_check` каждой задачи = запуск её сценария**, не произвольная команда; задача без сценария не компилируется.
- `planner_trace_proof` отвечает «доказано ли требование X сейчас» обходом `verifies`/`satisfies`.
- Намеренно сломанная реализация валит harness и триггерит `planner_replan(scenario_failed)`.
- `scenario_version` версионирован и пиннут к `spec_version` (инвариант 13); исполняемый тест кэшируется по нему.
- Никакого Gherkin/Cucumber-парсера в зависимостях.

## 9. Риски / не забыть
- **НЕ тащить Cucumber/Gherkin** (предупреждение автора): парсер сценариев — отдельный хрупкий шов, плохо растёт. Генерим исполняемый тест из GWT напрямую в раннере проекта.
- **scenario_version — ещё один LLM-хоп-выход** (EARS→GWT): версионируем по инварианту 2; кэшируем по версии, чтобы не регенерить и не плодить дрейф.
- **Сценарии ОБЯЗАНЫ выводиться из acceptance-критериев**, не авторятся параллельно спеке — иначе теряется синхронность (та самая болезнь «спека = мёртвый груз»).
- **Покрытие требований** — следить, чтобы у каждого требования был сценарий; `trace_proof` это и проверяет (пробел = непокрытое требование).
- **Граница с implement** — `planner_verify` определяет контракт harness'а сейчас; непрерывный прогон сценариев (хоть сто раз за сессию) — это уже исполнительский слой (Phase 10 v3, отложен), где `implements`-рёбра замкнут commit→task→satisfies→scenario.
- **Event-driven specs** (альтернатива автора для 10k+ сценариев) — НЕ сейчас; дороже на архитектуре. Зафиксировать как путь масштабирования, если число сценариев взлетит.

---

## 10. Что v3.1 даёт по сути
Это последний структурный кусок. После него:
- спека **жива с обеих сторон** — research уточняет сверху, harness ловит дрейф снизу;
- `success_check` означает «требование доказано», а не «тест прошёл»;
- граф происхождения отвечает на третий вопрос — **«выполняется ли требование прямо сейчас»** — обходом, а не аудитом агентом;
- SDD перестаёт быть «одноразовым вайб-планом» и становится **постоянно-верифицируемым контрактом**.

Остаётся только implement-слой (Phase 10 v3): Ralph + OpenHands/Claurst + заполнение `implements`-рёбер до коммита, и тогда трейс замыкается полностью: `spec → scenario → design → task → commit`, с доказательством на каждом требовании.
