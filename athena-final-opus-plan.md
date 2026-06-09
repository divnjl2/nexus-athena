# Athena — Hermes-friendly Planner. ФИНАЛЬНЫЙ план для Опуса

> **Версия:** final v1. Заменяет все предыдущие черновики.
> **Что строим:** тонкую надстройку «**Athena**» над двумя готовыми чужими репо — **QRSPI** (планирующий фронт, промпт-цепочка) и **Beads `bd` v1.0** (durable task-граф на Dolt) — оформленную как **Claude Code плагин + MCP-сервер**. Через MCP **Hermes (L2-оркестратор NEXUS)** управляет всем циклом планирования высокоуровневыми глаголами и кормит **Ralph-цикл**, который исполняет задачи через **OpenHands** (изолированно/автономно) или **Claurst** (легко/быстро).
> **Кому:** агенту на Claude Opus, исполняющему этот план в Ralph-цикле.
> **Дисциплина:** дог-фудинг — строим планнер по той же методологии (QRSPI), которую он реализует. Каждая стадия — свежий контекст, состояние в файлах + git. Контекст <40%, fresh при 60%.

---

## 0. Что мы пишем сами, а что берём готовым (читать первым)

| Слой | Источник | Наш код? |
|---|---|---|
| QRSPI промпт-цепочка (планирование) | community (`matanshavit/qrspi`, `dfrysinger/qrspi-plus`) — vendored | нет, адаптируем формат вывода |
| Beads `bd` (task-граф/память) | `gastownhall/beads` v1.0 — установка | нет |
| **`plan2beads` (компилятор plan.md → bd)** | **мы** | **ДА — это ядро** |
| **Athena MCP server (глаголы для Hermes)** | **мы** | **ДА** |
| **Ralph loop + gate + роутер исполнителя** | **мы** | **ДА** |
| OpenHands / Claurst (исполнители) | внешние — установка | нет |

Реально пишем: компилятор, MCP-обёртку, loop. Всё остальное — клей и упаковка.

---

## 1. Инварианты (НЕ нарушать)

1. **`plan2beads` детерминированный.** Никаких LLM-вызовов в компиляторе. Один `plan.md` → один и тот же набор `bd`-команд. Чистое ядро без I/O, времени, random.
2. **Источник истины Beads — Dolt-база** под `.beads/`, НЕ `issues.jsonl` (он только экспорт). Все операции — через `bd` CLI / `beads-mcp`, никогда не писать Dolt напрямую.
3. **Канонический формат `plan.md` — единственный контракт** LLM↔код. QRSPI-стадия Plan ОБЯЗАНА выдавать его 1:1 с `plan_parser.py`. Несоответствие отбивается гейтом, не чинится в компиляторе.
4. **Один issue = одна итерация Ralph.** Зерно гранулярности зависит от исполнителя (см. §7): для Claurst ≤~2 мин; для OpenHands может быть крупнее (он сам итерирует внутри песочницы).
5. **Gate обязателен и ВНЕШНИЙ.** issue без исполнимого `success_check` не компилируется (ошибка). `gate.sh` — authoritative-арбитр, self-report исполнителя не считается.
6. **Athena executor-agnostic.** Своп OpenHands↔Claurst трогает только `loop.sh` + runtime, не планнер.
7. **QRSPI — community-реконструкция** (HumanLayer официально не открыли). Под-стадии могут гулять; держим стабильным только финальный артефакт `plan.md`.

---

## 2. Архитектура и структура репо

```
nexus-athena/
├── .claude-plugin/plugin.json          # манифест (Claude Code / Claurst / OpenHands читают)
├── commands/qrspi/                      # ПЛАНИРУЮЩИЙ ФРОНТ (vendored+адаптировано)
│   ├── 1_question.md                    # /qrspi.question  — развилки опциями
│   ├── 2_research.md                    # /qrspi.research  — факты, тикет СКРЫТ
│   ├── 3_design.md                      # /qrspi.design    — "хирургия мозга"
│   ├── 4_structure.md                   # /qrspi.structure — вертикальные срезы
│   └── 5_plan.md                        # /qrspi.plan      — КАНОНИЧЕСКИЙ plan.md
├── commands/compile.md                  # /athena.compile  — вызывает plan2beads
├── agents/                              # documentarian-сабагенты (описывают, не предлагают)
│   ├── codebase-locator.md
│   ├── codebase-analyzer.md
│   ├── codebase-pattern-finder.md
│   └── web-search-researcher.md
├── skills/plan-format/SKILL.md          # КАНОНИЧЕСКИЙ формат plan.md (контракт §4)
├── hooks/hooks.json                     # SessionStart: bd prime; PreCompact: bd sync
├── mcp/athena_mcp/                       # FastMCP сервер — глаголы для Hermes (§6)
│   ├── server.py
│   ├── verbs.py
│   └── pyproject.toml
├── lib/
│   ├── plan_parser.py                   # plan.md -> dataclasses (§4)
│   ├── plan2beads.py                    # ДЕТЕРМИНИРОВАННЫЙ компилятор (§5)
│   └── bd_client.py                     # ЕДИНСТВЕННОЕ место с subprocess
├── ralph/
│   ├── loop.sh                          # цикл + роутер исполнителя (§7,§8)
│   ├── gate.sh                          # внешний исполнитель success_check
│   ├── run_openhands.sh                 # запуск OpenHands headless на 1 issue
│   ├── run_claurst.sh                   # запуск Claurst на 1 issue
│   └── AGENTS.md                        # Ralph-контракт для исполнителя
├── tests/
│   ├── test_plan_parser.py
│   ├── test_plan2beads.py               # golden + idempotency + negative
│   └── fixtures/                        # valid.md + *.expected.json + битые кейсы
├── vendor/qrspi/                        # vendored QRSPI шаблоны (pinned commit)
├── install.sh                           # bd + plugin + mcp + executor setup
└── README.md
```

### Поток данных
```
Hermes ──MCP──> Athena:
  align()  = question → research(ticket hidden) → design → structure   [ярусные гейты]
  plan()   → plan.md (канонический формат)
  compile()→ bd: эпики/issue/deps  (детерминированно, идемпотентно)
Ralph loop:
  bd ready → claim → [router: OpenHands|Claurst исполняет 1 issue] → gate.sh(success_check)
           → bd close + bd sync → kill session (fresh ctx next)
           → найдено по ходу? → bd create discovered-from
Hermes ──MCP──> next()/report()/replan() для контроля и бэктрекинга
```

---

## 3. QRSPI планирующий фронт (commands/qrspi/)

5 стадий выравнивания + наш compile. Каждый промпт <40 инструкций, свежий контекст, свой артефакт. Мотивация: RPI ломался на (1) переполнении бюджета инструкций (~150–200 потолок), (2) ранних дизайн-решениях в 1000-строчном плане, (3) research жрущем 40% контекста впустую. На автономном прогоне это смертельно — Ralph всю ночь верно исполнит неверный план.

| Стадия | Что делает | Артефакт | Ярус гейта |
|---|---|---|---|
| **1 Question** | выкатывает дизайн-развилки опциями (Q1: A/B/C?), резолвит ДО research | `questions.md` | плотный |
| **2 Research** | documentarian-сабагенты собирают факты; **тикет СКРЫТ** (без преждевременных мнений) | `research.md` | плотный |
| **3 Design** | структурная дизайн-дискуссия ("хирургия мозга") до строчки кода | `design.md` (~200 стр) | плотный |
| **4 Structure** | вертикальные срезы > горизонтальные слои | structure outline (~2 стр) | spot-check |
| **5 Plan** | механический перевод согласованного дизайна в фазы+задачи+success_check | `plan.md` (канон) | spot-check |

**Бэктрекинг (встроить в гейты):** Design нашёл дыру → re-run Question+Research; Structure вскрыл кривой дизайн → re-run Design; Implement уперся в ошибку плана → re-run Plan/Design. Мелкое чинится на месте.

**Автономный режим:** Question-стадия интерактивна by design. Роль человека играет **Hermes** — отвечает на развилки из политик/контекста проекта (см. `planner_question` в §6), либо решения пре-сидятся в тикете. Иначе агент зависнет на «магических словах» (баг RPI №1).

---

## 4. Контракт: канонический формат `plan.md` (skills/plan-format/SKILL.md)

Стадия 5_plan выдаёт ровно это; `plan_parser.py` парсит жёстко.

```markdown
# Plan: <название>
## Overview
<2-4 предложения: цель + desired end state>

## Out of Scope
- <что НЕ делаем>

## Phase 1: <название>
**Goal:** <одно предложение>
**Depends on:** none                 # или "Phase N"
### Tasks
- [ ] T1.1 <атомарная задача>
  - success_check: `<исполнимая команда, exit 0 = passed>`
  - files: `path/a.py, path/b.py`
  - autonomy: high                   # опц.: high → OpenHands, иначе Claurst
### Manual Verification
- <ручные шаги>

## Phase 2: <...>
**Depends on:** Phase 1
...
```

**Правила парсинга (жёсткие):** `## Phase N:`→эпик; `T<phase>.<n>`→child-issue; `Depends on: Phase K`→blocks-ребро эпик-уровня; `success_check:` обязателен (нет→ошибка); `autonomy:` опц.→лейбл роутинга; `files:`→в тело issue; `Out of Scope`→note эпика.

---

## 5. Контракт: `plan2beads` (детерминированный компилятор)

> Готовый рабочий скелет — в приложенном `plan2beads.py`. Здесь — контракт и почему именно так.

**Почему детерминизм критичен:** компилятор — линия заморозки между нечётким (LLM наверху) и механическим (граф внизу). LLM в компиляторе → невоспроизводимый ночной прогон, невозможные golden-тесты, дубли issue при replan.

**Сигнатура ядра (чистая функция):**
`compile(plan: Plan, *, existing_keys: frozenset[str] = frozenset()) -> CompileResult`

**Шаги (детерминированно, document order):**
1. Валидация: каждый task имеет непустой `success_check`; `Depends on` резолвятся; нет дублей task-id. Иначе `CompileError`.
2. Phase → `bd create --type epic --label athena:<slug>:epicN`.
3. Task → `bd create --parent <epic> --label athena:<slug>:T.. --label athena [+ autonomy лейбл]`, тело несёт `success_check`/`files`.
4. `Depends on` → `bd dep add ... --blocked-by ...`, рёбра в `sorted()` порядке.

**Идемпотентность (upsert):** внешние лейблы `athena:<slug>:...` поверх hash-ID Beads. Эффектный слой (`bd_client.fetch_existing_keys`) запрашивает существующие лейблы → передаёт в `existing_keys` → ядро пропускает `bd create` для уже существующего. **Чистое ядро остаётся чистым.**

**Враги детерминизма (ловить в ревью):** таймстемпы/random внутри ядра (инжектить параметрами), итерация по `set` (только document order / `sorted()`), locale-зависимая сортировка.

**Тестовая пирамида (Phase build §9 покрывает):**
- parser unit (кривые входы → внятные ошибки);
- **golden/snapshot** (`valid.md` → точный список команд);
- property: `parse(render(ast))==ast`; `compile(existing=all)` без единой `create`;
- negative: нет success_check / нераз­решённая зависимость / дубль id → ошибка;
- **bd contract (марка integration, реальный `bd` в temp-Dolt)** — ловит дрейф схемы Beads между версиями.

---

## 6. Контракт: Athena MCP server (глаголы для Hermes)

FastMCP, структурированный JSON. Два уровня зернистости — реализовать оба.

| Глагол | Вход | Действие | Выход |
|---|---|---|---|
| `planner_question` | `intent, repo_path` | стадия 1; в автономе Hermes отвечает на развилки | `{questions_path, open_decisions}` |
| `planner_research` | `questions_path` | стадия 2 (тикет скрыт), documentarian-сабагенты | `{research_path}` |
| `planner_design` | `research_path` | стадия 3 | `{design_path}` |
| `planner_structure` | `design_path` | стадия 4 | `{structure_path}` |
| `planner_plan` | `structure_path` | стадия 5 → канонический `plan.md` | `{plan_path}` |
| `planner_align` | `intent, repo_path` | крупнозернисто: 1→4 с гейтами под капотом | `{design_path, structure_path}` |
| `planner_validate` | `plan_path` | проверка формата + полноты до компиляции | `{passed, issues}` |
| `planner_compile` | `plan_path` | `plan2beads.compile(dry_run=False)` | `{epic_keys, issue_count}` |
| `planner_next` | — | `bd ready --json` верхний | `{issue}` \| `null` |
| `planner_complete` | `issue_id, gate_passed, log` | `bd close`+`bd sync` или reopen+note | `{ok}` |
| `planner_report` | — | `bd stats --json` + сводка эпиков | `{progress}` |
| `planner_replan` | `trigger, context` | агрегирует discovered-from/провалы → бэктрек на нужную стадию | `{plan_path}` |

Ярусные гейты: `question/research/design` — Hermes/человек плотно; `structure/plan` — spot-check; код — через `gate.sh`.

---

## 7. Исполнители: OpenHands (primary) + Claurst (alt) + роутинг

**OpenHands** — изоляция + автономия. Каждое действие в **sandboxed runtime-контейнере** (агент не трогает хост; bash/jupyter/browser внутри). **Backend-agnostic** (`LLM_MODEL`/`LLM_BASE_URL`/`LLM_API_KEY`) → твой self-hosted кластер через LiteLLM. Свой agent-loop (edit→test→fix внутри) → issue могут быть крупнее. Headless = always-approve → **ВСЕГДА Docker + `SANDBOX_VOLUMES=$REPO:/workspace:rw` (только workdir)**, и `--max-iterations` чтобы не сжёг ночь.

**Claurst** — легко/быстро на мелких issue (one-shot, без оверхеда контейнера).

**Роутинг** по лейблу из плана: `autonomy:high` → OpenHands; иначе → Claurst. Лейбл уже проставляет `plan2beads`. Hermes ничего не знает о кишках исполнителя.

**Версионные оговорки (перепроверить при установке):**
- OpenHands: V0 Runtime задеприкейчен, снятие **1 апреля 2026**; целься в **V1 `SandboxService` / `software-agent-sdk`**, не копируй `python -m openhands.core.main`.
- Beads: запинь стабильную **v1.x** (Dolt); проверь, что `bd ready --json`/`bd show --json`/`bd dep` не сменили схему (тесты `bd_client` ловят).
- Дай исполнителю **beads MCP** (`openhands mcp …` / plugin) → сам читает `bd show`, заводит `discovered-from`.

---

## 8. Ralph loop + внешний gate (ralph/)

**loop.sh (суть):**
```bash
#!/usr/bin/env bash
set -uo pipefail
for ((i=0; i<${MAX_ITER:-200}; i++)); do
  ISSUE=$(bd ready --json --limit 1)
  [ "$(echo "$ISSUE" | jq 'length')" -eq 0 ] && { echo "queue empty"; break; }
  ID=$(echo "$ISSUE" | jq -r '.[0].id')
  AUTON=$(echo "$ISSUE" | jq -r '.[0].labels[]? | select(.=="autonomy:high")')
  bd update "$ID" --claim
  if [ -n "$AUTON" ]; then ./ralph/run_openhands.sh "$ID"; else ./ralph/run_claurst.sh "$ID"; fi
  if ./ralph/gate.sh "$ID"; then bd close "$ID"; bd sync
  else bd update "$ID" --status open --note "gate failed iter $i"; fi
  # сессия исполнителя убита → следующий проход = чистый контекст
done
```
**gate.sh:** достаёт `success_check` из `bd show $ID --json`, исполняет, возвращает его exit code (authoritative).
**run_openhands.sh:** `LLM_MODEL=$NEXUS_MODEL LLM_BASE_URL=$NEXUS_LITELLM SANDBOX_VOLUMES=$REPO:/workspace:rw openhands --headless --max-iterations 30 --task "<bd show $ID + контракт>"`.
**AGENTS.md:** `bd prime` на старте; работа только через `bd ready`; новое — `discovered-from`; `bd sync` перед выходом; не трогать чужой claim.

---

## 9. Фазы сборки (это plan.md для Опуса; QRSPI-стиль, каждый task с success_check)

### Phase 0: Scaffold + vendoring + pin версий
**Goal:** скелет репо, запиненные зависимости.
- [ ] T0.1 структура каталогов §2. `success_check:` `test -f .claude-plugin/plugin.json && test -d lib && test -d ralph && test -d commands/qrspi`
- [ ] T0.2 vendored QRSPI в `vendor/qrspi/` + commit-hash в README. `success_check:` `test -f vendor/qrspi/5_plan.md`
- [ ] T0.3 `install.sh`: pinned `bd`, `bd init`, регистрация плагина+MCP, проверка OpenHands V1. `success_check:` `bash -n install.sh`
**Manual:** зафиксировать версии bd (v1.x Dolt) и OpenHands (V1) в install.sh.

### Phase 1: Канонический формат plan.md
**Depends on:** Phase 0
- [ ] T1.1 `skills/plan-format/SKILL.md` по §4. `success_check:` `grep -q success_check skills/plan-format/SKILL.md`
- [ ] T1.2 fixtures: valid + no_check + bad_dep + dup_id. `success_check:` `ls tests/fixtures/*.md | wc -l | grep -qE '[4-9]'`
**Manual:** глазами — формат однозначно парсится строчным парсером.

### Phase 2: Парсер + детерминированный компилятор
**Depends on:** Phase 1
- [ ] T2.1 `plan_parser.py` → dataclasses. `success_check:` `python -m pytest tests/test_plan_parser.py -q`
- [ ] T2.2 `plan2beads.py` (чистое ядро + idempotency через existing_keys). `success_check:` `python -m pytest tests/test_plan2beads.py -q`
- [ ] T2.3 golden + idempotency + negative тесты зелёные. `success_check:` `python -m pytest tests/ -q`
- [ ] T2.4 `bd_client.py` (subprocess, `--json`). `success_check:` `python -c "import lib.bd_client"`
**Manual:** dry-run на реальном `bd init`, сверить команды глазами.

### Phase 3: QRSPI команды + сабагенты
**Depends on:** Phase 1
- [ ] T3.1 адаптировать vendored → `commands/qrspi/{1..5}_*.md`, 5_plan выдаёт канон. `success_check:` `ls commands/qrspi/*.md | wc -l | grep -q 5`
- [ ] T3.2 documentarian-сабагенты в `agents/`. `success_check:` `ls agents/*.md | wc -l | grep -qE '[4-9]'`
- [ ] T3.3 `commands/compile.md` → plan2beads. `success_check:` `test -f commands/compile.md`
**Manual:** прогнать question→research→design→structure→plan на тестовой задаче; plan.md проходит парсер Phase 2.

### Phase 4: Athena MCP server
**Depends on:** Phase 2, Phase 3
- [ ] T4.1 `server.py`+`verbs.py`, все глаголы §6 (мелко- и крупнозернистые). `success_check:` `cd mcp/athena_mcp && uv run python -c "import athena_mcp.server"`
- [ ] T4.2 compile→plan2beads; next/complete→bd_client; align гоняет 1-4 с гейтами. `success_check:` `cd mcp/athena_mcp && uv run pytest -q`
**Manual:** через MCP-инспектор `planner_next` на наполненном графе → разблокированный issue.

### Phase 5: Исполнители + Ralph loop + gate
**Depends on:** Phase 2
- [ ] T5.1 `gate.sh` извлекает+гонит success_check. `success_check:` `bash -n ralph/gate.sh`
- [ ] T5.2 `run_openhands.sh` (V1, headless, Docker, max-iter) + `run_claurst.sh`. `success_check:` `bash -n ralph/run_openhands.sh && bash -n ralph/run_claurst.sh`
- [ ] T5.3 `loop.sh` с роутингом по `autonomy:high` §8. `success_check:` `bash -n ralph/loop.sh && grep -q autonomy ralph/loop.sh`
- [ ] T5.4 `AGENTS.md` с контрактом. `success_check:` `grep -q "bd ready" ralph/AGENTS.md`
**Manual:** сухой прогон MAX_ITER=2 на 2 тривиальных issue (один autonomy:high → OpenHands-контейнер, один → Claurst); закрылись по gate, сессии убиты.

### Phase 6: Интеграция с Hermes
**Depends on:** Phase 4, Phase 5
- [ ] T6.1 зарегистрировать athena MCP в конфиге Hermes. `success_check:` `<проверка конфига Hermes>`
- [ ] T6.2 Hermes-плейбук: align→plan→validate(loop)→compile→[loop: next→execute→complete]→report; автономные ответы на Question. `success_check:` `test -f hermes_playbook.md`
**Manual:** Hermes одним промптом доводит до наполненного bd-графа, сам отвечая на развилки Question-стадии.

### Phase 7: End-to-end дог-фудинг
**Depends on:** Phase 6
- [ ] T7.1 реальная мелкая фича: полный QRSPI→compile→ночной Ralph-прогон. `success_check:` `bd stats --json | jq '.closed > 0'`
- [ ] T7.2 метрики (итераций, провалов gate, discovered-from, бэктреков). `success_check:` `test -f run-report.md`
**Manual:** ревью diff'а — качество, отсутствие дрейфа, корректный replan на discovered-from.

---

## 10. Acceptance (надстройка готова)
- `pytest tests/` зелёный, включая golden + idempotency + bd-contract.
- Hermes одним промптом → наполненный bd-граф (эпики/issue/deps, success_check у каждого issue), сам отвечая на Question-развилки.
- `loop.sh` автономно закрывает очередь, роутит OpenHands/Claurst по лейблу, завершается по пустому `bd ready`, не зацикливается на провале gate.
- Установка на чистой машине: `bash install.sh`.
- Состояние Beads синкается в self-hosted git/Dolt и переживает kill сессий между итерациями.
- Своп исполнителя — правка только `ralph/`, планнер не тронут.

## 11. Риски / не забыть
- **OpenHands V0→V1:** целиться в `SandboxService`/`software-agent-sdk`; V0 снимают 1 апреля 2026. Per-issue спин-ап контейнера — оверхед; для мелочи роутить в Claurst.
- **Beads version flux:** запинить v1.x (Dolt), `bd_client` тесты ловят дрейф схемы; durable-артефакт = Dolt-репо (`bd dolt push/pull`, `bd backup`), не jsonl.
- **QRSPI community-reconstructed:** имена под-стадий гуляют; стабильный контракт — только финальный `plan.md`. Держать стадии <40 инструкций (баг бюджета).
- **Question-стадия в автономе:** Hermes ОБЯЗАН отвечать на развилки, иначе зависание на «магических словах».
- **Токеномика:** 8 QRSPI-вызовов + fresh-context-per-issue дороги; смягчается self-hosted моделями на кластере.
- **Gate только внешний:** не доверять self-report ни OpenHands, ни Claurst.
