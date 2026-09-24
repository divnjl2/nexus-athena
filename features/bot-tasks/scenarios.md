# Scenarios: Управление задачами (EARS → executable GWT)

_Один Scenario на acceptance criterion. ID `S<n>.<m>`. run_cmd = success_check связанных задач._

### S1.1 — Назначение задачи создаёт карточку
- **verifies:** AC1
- **run_cmd:** `pytest tests/test_assign.py::test_assign_creates_card -q`
- **Given** руководитель Павел и сотрудник Иван с маппингом TG→вольт
- **When** Павел назначает Ивану задачу «Сделать эл. схему» со сроком 2026-07-28
- **Then** в доске Ивана появляется карточка в колонке «Надо сделать» с текстом и сроком

### S1.2 — Двусторонняя видимость (S3 ↔ Obsidian)
- **verifies:** AC7
- **run_cmd:** `pytest tests/test_s3board.py::test_roundtrip_card -q`
- **Given** задача создана ботом в S3-доске
- **When** доска перечитывается (как это делает Obsidian после синка)
- **Then** та же карточка присутствует с тем же текстом, статусом и сроком

### S2.1 — Свод по сотрудникам
- **verifies:** AC3
- **run_cmd:** `pytest tests/test_report.py::test_report_groups_by_person -q`
- **Given** несколько сотрудников с задачами в разных колонках
- **When** Павел открывает «По сотрудникам»
- **Then** по каждому показаны счётчики задач по статусам и перечень просроченных

### S2.2 — Свод по отделам
- **verifies:** AC4
- **run_cmd:** `pytest tests/test_report.py::test_report_groups_by_department -q`
- **Given** сотрудники размечены полем department
- **When** Павел открывает «По отделам»
- **Then** сотрудники сгруппированы по отделу с агрегатами по статусам

### S2.3 — Просроченные задачи
- **verifies:** AC6
- **run_cmd:** `pytest tests/test_overdue.py::test_past_due_flagged -q`
- **Given** задача со сроком в прошлом и не завершена
- **When** строится свод
- **Then** задача помечена как просроченная

### S3.1 — Смена статуса сотрудником отражается в своде
- **verifies:** AC2
- **run_cmd:** `pytest tests/test_status.py::test_move_reflects_in_report -q`
- **Given** у Ивана задача в колонке «Надо сделать»
- **When** Иван жмёт «Взял в работу»
- **Then** карточка переезжает в «В работе» и это видно в своде Павла

### S4.1 — Роль-гейт управленческого свода
- **verifies:** AC5
- **run_cmd:** `pytest tests/test_roles.py::test_non_admin_denied_report -q`
- **Given** сотрудник без роли admin
- **When** он запрашивает управленческий свод
- **Then** система отказывает и показывает только его собственные задачи
