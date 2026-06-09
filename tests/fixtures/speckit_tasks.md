# Tasks: Healthcheck Endpoint

## Phase 1: Setup
- [ ] T001 Create project structure
  - success_check: `test -d src`
- [ ] T002 [P] Configure linting
  - success_check: `ruff --version`

## Phase 2: Foundational
- [ ] T003 Setup app skeleton in src/app.py
  - success_check: `python -c "import src.app"`

## Phase 3: User Story 1 - Health endpoint (Priority: P1)
**Goal:** GET /health returns 200
- [ ] T004 [P] [US1] Add route in src/routes.py
  - success_check: `pytest tests/test_health.py -q`
- [ ] T005 [US1] Register blueprint in src/app.py
  - success_check: `curl -sf localhost:8000/health`
**Checkpoint:** `pytest tests/test_us1.py -q`

## Phase 4: Polish
- [ ] T006 [P] Add docs
  - success_check: `test -f README.md`
