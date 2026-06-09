# Plan: Demo Feature
## Overview
Add a healthcheck endpoint. Desired end state: GET /health returns 200.

## Out of Scope
- auth on the endpoint

## Phase 1: Endpoint
**Goal:** expose GET /health
**Depends on:** none
### Tasks
- [ ] T1.1 add /health route
  - success_check: `pytest tests/test_health.py -q`
  - files: `app/routes.py`

## Phase 2: Wire-up
**Goal:** register route in app
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 register blueprint
  - success_check: `curl -sf localhost:8000/health`
