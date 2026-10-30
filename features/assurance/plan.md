# Plan: Requirement assurance

## Phase 1: Requirement evidence map
**Goal:** distinguish execution, check adequacy and semantic review without inferring completion.
**Depends on:** none
### Tasks
- [ ] T1.1 Evidence map and review view
  - success_check: `python -m pytest tests/test_assurance.py tests/test_assurance_demo.py -q`
  - verifies: S1.1, S1.2, S1.3, S1.4, S1.5, S1.6, S1.7
  - files: `lib/assurance.py, athena.py, tests/test_assurance.py, tests/test_assurance_demo.py, examples/assurance_demo.py`
- [ ] T1.2 Exercise current evidence across generated lifecycle histories
  - success_check: `python -m pytest tests/test_assurance_stateful.py -q`
  - verifies: S1.8
  - files: `tests/test_assurance_stateful.py`
