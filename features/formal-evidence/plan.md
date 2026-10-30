# Plan: Optional formal evidence

## Phase 1: Bounded tool receipts
**Goal:** demonstrate formal evidence without promoting it to user-intent validation.
**Depends on:** none
### Tasks
- [ ] T1.1 Add collector and system-design view
  - success_check: `python -m pytest tests/test_formal_evidence.py -q`
  - verifies: S1.1, S1.2, S1.3, S1.4, S1.5
  - files: `lib/formal_evidence.py, lib/formal_review.py, athena.py, tests/test_formal_evidence.py, tools/run_formal_pilot.py`
- [ ] T1.2 Run CrossHair on the production evidence reducer
  - success_check: `python -m pytest tests/test_crosshair_selfcheck.py -q`
  - verifies: S1.6
  - files: `lib/assurance.py, tools/run_crosshair_selfcheck.py, tests/test_crosshair_selfcheck.py`
- [ ] T1.3 Explain counterexamples through interactive replay
  - success_check: `python -m pytest tests/test_crosshair_selfcheck.py::test_replay_distinguishes_executed_state_table_from_tool_claims -q`
  - verifies: S1.7
  - files: `lib/formal_review.py, tools/run_crosshair_selfcheck.py, tests/test_crosshair_selfcheck.py`
- [ ] T1.4 Render assurance arguments with native gsn2x
  - success_check: `python -m pytest tests/test_gsn_case.py -q`
  - verifies: S1.8
  - files: `lib/gsn_case.py, tools/render_gsn_case.py, tests/test_gsn_case.py`
