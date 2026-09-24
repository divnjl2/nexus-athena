---
plan_id: bot-tasks-telegram-obsidian
owner: divnjl2
risk_tier: T2
requires_approval: false
generated_by: athena
---

# bot-tasks — задачи через Telegram + Obsidian — bot-tasks — задачи через Telegram + Obsidian

## Goal (one sentence)
bot-tasks — задачи через Telegram + Obsidian

## Acceptance (one criterion)
every task's success_check exits 0

## Tasks

- [ ] task_id: T001
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "setup", "success_check": "python -c \"import boto3, moto\"", "title": "Добавить зависимости boto3 + moto в corp_attendance_bot/requirements.txt"}
  priority: 0
  max_retries: 2

- [ ] task_id: T002
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "setup", "success_check": "python -c \"from bot.config import s3_settings; s3_settings()\"", "title": "Завести .env-ключи S3_ENDPOINT/S3_BUCKET/S3_KEY_ID/S3_SECRET (env-substitution, не в гит) + config-загрузчик"}
  priority: 0
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T003
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "setup", "success_check": "pytest tests/conftest.py --collect-only -q", "title": "Каркас тестов tests/ (conftest с moto-S3 фикстурой, фейковая доска)"}
  priority: 0
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T004
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "foundational", "success_check": "pytest tests/test_s3board.py::test_parse_columns -q", "title": "Парсер доски: bot/s3board.py::parse_board(md) -> list[Card] (колонка=статус, текст, срок, done)"}
  priority: 1
  max_retries: 2

- [ ] task_id: T005
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "foundational", "success_check": "pytest tests/test_s3board.py::test_roundtrip_card -q", "title": "S3-модуль bot/s3board.py: read_board/add_card/move_card/mark_done (read-modify-write через boto3)"}
  priority: 1
  max_retries: 2

- [ ] task_id: T006
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "foundational", "success_check": "pytest tests/test_s3board.py::test_card_id_stable -q", "title": "Стабильный card_id = hash(vault, normalized_text) для callback-кнопок"}
  priority: 1
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T007
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "foundational", "success_check": "pytest tests/test_mapping.py::test_migration_adds_columns -q", "title": "Миграция SQLite: employees += vault TEXT, department TEXT; сид vault по имени"}
  priority: 1
  max_retries: 2

- [ ] task_id: T008
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "foundational", "success_check": "pytest tests/test_mapping.py::test_department_seed -q", "title": "Сид department из #сфера-тегов профилей вольтов (параметризуемо)"}
  priority: 1
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T009
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US1", "success_check": "pytest tests/test_assign.py::test_assign_flow_states -q", "title": "FSM-поток «Назначить»: сотрудник→текст→срок(кнопки)→подтвердить"}
  priority: 2
  max_retries: 2

- [ ] task_id: T010
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US1", "success_check": "pytest tests/test_assign.py::test_assign_creates_card -q", "title": "Хендлер записи: add_card в vault сотрудника (колонка «Надо сделать») + срок"}
  priority: 2
  max_retries: 2

- [ ] task_id: T011
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US2", "success_check": "pytest tests/test_report.py::test_report_groups_by_person -q", "title": "report(): агрегат по сотрудникам (счётчики по статусам)"}
  priority: 3
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T012
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US2", "success_check": "pytest tests/test_report.py::test_report_groups_by_department -q", "title": "Группировка по отделам (department)"}
  priority: 3
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T013
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US2", "success_check": "pytest tests/test_overdue.py::test_past_due_flagged -q", "title": "Пометка просроченных (due < today, не done)"}
  priority: 3
  max_retries: 2

- [ ] task_id: T014
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US2", "success_check": "pytest tests/test_report.py::test_admin_menu_renders -q", "title": "Инлайн-меню руководителя: Актуальные/По сотрудникам/По отделам/Просрочено"}
  priority: 3
  max_retries: 2

- [ ] task_id: T015
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US3", "success_check": "pytest tests/test_status.py::test_my_tasks_renders -q", "title": "«Мои задачи»: read_board своего vault + инлайн-статусы"}
  priority: 4
  max_retries: 2

- [ ] task_id: T016
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US3", "success_check": "pytest tests/test_status.py::test_move_reflects_in_report -q", "title": "Кнопки «В работу»/«Готово» → move_card/mark_done → видно в своде"}
  priority: 4
  max_retries: 2

- [ ] task_id: T017
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US4", "success_check": "pytest tests/test_roles.py::test_non_admin_denied_report -q", "title": "Роль-гейт декоратор admin_only на своды/назначение"}
  priority: 5
  max_retries: 2

- [ ] task_id: T018
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "US4", "success_check": "pytest tests/test_roles.py::test_callback_owner_check -q", "title": "Валидация callback по user_id (нельзя дёрнуть чужую доску)"}
  priority: 5
  max_retries: 2

- [ ] task_id: T019
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "polish", "success_check": "test -f docs/tasks-module.md", "title": "Дока модуля docs/tasks-module.md (перенести design.md) в репо бота"}
  priority: 6
  max_retries: 2
  # [P] parallelizable within phase

- [ ] task_id: T020
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"phase": "polish", "success_check": "pytest -q", "title": "CI: прогон всех тестов перед деплоем + Docker-сборка на VPS"}
  priority: 6
  max_retries: 2
  # [P] parallelizable within phase

## Linked
- generated by Athena `compile` from front `bot-tasks-telegram-obsidian`
- executor: `apps/hermes/workflows/PLAN_RUN.yaml` (existing)
