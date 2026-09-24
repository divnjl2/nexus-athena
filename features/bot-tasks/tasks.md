# Tasks: bot-tasks — задачи через Telegram + Obsidian

## Phase 1: Setup
- [ ] T001 Добавить зависимости boto3 + moto в corp_attendance_bot/requirements.txt
  - success_check: `python -c "import boto3, moto"`
- [ ] T002 [P] Завести .env-ключи S3_ENDPOINT/S3_BUCKET/S3_KEY_ID/S3_SECRET (env-substitution, не в гит) + config-загрузчик
  - success_check: `python -c "from bot.config import s3_settings; s3_settings()"`
- [ ] T003 [P] Каркас тестов tests/ (conftest с moto-S3 фикстурой, фейковая доска)
  - success_check: `pytest tests/conftest.py --collect-only -q`

## Phase 2: Foundational
- [ ] T004 Парсер доски: bot/s3board.py::parse_board(md) -> list[Card] (колонка=статус, текст, срок, done)
  - success_check: `pytest tests/test_s3board.py::test_parse_columns -q`
- [ ] T005 S3-модуль bot/s3board.py: read_board/add_card/move_card/mark_done (read-modify-write через boto3)
  - success_check: `pytest tests/test_s3board.py::test_roundtrip_card -q`
- [ ] T006 [P] Стабильный card_id = hash(vault, normalized_text) для callback-кнопок
  - success_check: `pytest tests/test_s3board.py::test_card_id_stable -q`
- [ ] T007 Миграция SQLite: employees += vault TEXT, department TEXT; сид vault по имени
  - success_check: `pytest tests/test_mapping.py::test_migration_adds_columns -q`
- [ ] T008 [P] Сид department из #сфера-тегов профилей вольтов (параметризуемо)
  - success_check: `pytest tests/test_mapping.py::test_department_seed -q`

## Phase 3: User Story 1 - Назначение задачи (Priority: P1)
**Goal:** руководитель назначает задачу сотруднику инлайн-кнопками, она появляется в его доске.
- [ ] T009 [US1] FSM-поток «Назначить»: сотрудник→текст→срок(кнопки)→подтвердить
  - success_check: `pytest tests/test_assign.py::test_assign_flow_states -q`
- [ ] T010 [US1] Хендлер записи: add_card в vault сотрудника (колонка «Надо сделать») + срок
  - success_check: `pytest tests/test_assign.py::test_assign_creates_card -q`
**Checkpoint:** `pytest tests/test_assign.py -q`

## Phase 4: User Story 2 - Своды и статусы (Priority: P1)
**Goal:** руководитель видит статусы по сотрудникам, по отделам и просрочку.
- [ ] T011 [P] [US2] report(): агрегат по сотрудникам (счётчики по статусам)
  - success_check: `pytest tests/test_report.py::test_report_groups_by_person -q`
- [ ] T012 [P] [US2] Группировка по отделам (department)
  - success_check: `pytest tests/test_report.py::test_report_groups_by_department -q`
- [ ] T013 [US2] Пометка просроченных (due < today, не done)
  - success_check: `pytest tests/test_overdue.py::test_past_due_flagged -q`
- [ ] T014 [US2] Инлайн-меню руководителя: Актуальные/По сотрудникам/По отделам/Просрочено
  - success_check: `pytest tests/test_report.py::test_admin_menu_renders -q`
**Checkpoint:** `pytest tests/test_report.py tests/test_overdue.py -q`

## Phase 5: User Story 3 - Сотрудник ведёт свои (Priority: P2)
**Goal:** сотрудник видит свои задачи и меняет статус кнопкой.
- [ ] T015 [US3] «Мои задачи»: read_board своего vault + инлайн-статусы
  - success_check: `pytest tests/test_status.py::test_my_tasks_renders -q`
- [ ] T016 [US3] Кнопки «В работу»/«Готово» → move_card/mark_done → видно в своде
  - success_check: `pytest tests/test_status.py::test_move_reflects_in_report -q`
**Checkpoint:** `pytest tests/test_status.py -q`

## Phase 6: User Story 4 - Роли и приватность (Priority: P1)
**Goal:** управленческие виды только админам; сотрудник — только своё.
- [ ] T017 [US4] Роль-гейт декоратор admin_only на своды/назначение
  - success_check: `pytest tests/test_roles.py::test_non_admin_denied_report -q`
- [ ] T018 [US4] Валидация callback по user_id (нельзя дёрнуть чужую доску)
  - success_check: `pytest tests/test_roles.py::test_callback_owner_check -q`
**Checkpoint:** `pytest tests/test_roles.py -q`

## Phase 7: Polish
- [ ] T019 [P] Дока модуля docs/tasks-module.md (перенести design.md) в репо бота
  - success_check: `test -f docs/tasks-module.md`
- [ ] T020 [P] CI: прогон всех тестов перед деплоем + Docker-сборка на VPS
  - success_check: `pytest -q`
