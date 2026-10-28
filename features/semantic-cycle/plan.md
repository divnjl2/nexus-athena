# Plan: Semantic repair cycle

## Phase 1: Source-grounded intent
### Tasks
- [ ] T1.1 Derive issue-first intent and bind new assertions to sources
  - success_check: `python -m pytest tests/test_tdd_intent.py tests/test_tdd_assertion_support.py -q`
  - verifies: S1.1, S1.2
  - files: `evals/tddbench/intent.py, tests/test_tdd_intent.py, tests/test_tdd_assertion_support.py`

- [ ] T1.2 Preserve questions and require source-checked answers before release
  - success_check: `python -m pytest tests/test_tdd_issue_questions.py -q`
  - verifies: S1.3
  - files: `evals/tddbench/intent.py, evals/tddbench/semantic.py, evals/tddbench/cycle.py, tests/test_tdd_issue_questions.py`

## Phase 2: Immutable repair lineage
### Tasks
- [ ] T2.1 Coordinate immutable repairs with fresh reviews and public-only feedback
  - success_check: `python -m pytest tests/test_tdd_cycle.py tests/test_tdd_cycle_privacy.py -q`
  - verifies: S2.1, S2.2
  - files: `evals/tddbench/cycle.py, evals/tddbench/generator.py, tests/test_tdd_cycle.py, tests/test_tdd_cycle_privacy.py`

## Phase 3: Contrastive controls
### Tasks
- [ ] T3.1 Challenge oracle specificity with substantive declared alternatives
  - success_check: `python -m pytest tests/test_tdd_semantic_controls.py -q`
  - verifies: S3.1
  - files: `evals/tddbench/semantic.py, evals/tddbench/trust.py, tests/test_tdd_semantic_controls.py`

## Phase 4: Shared budget
### Tasks
- [ ] T4.1 Account for all phases and reserve full-cost verification
  - success_check: `python -m pytest tests/test_tdd_lineage.py -q`
  - verifies: S4.1, S4.2, S4.3
  - files: `evals/tddbench/lineage.py, tests/test_tdd_lineage.py`

## Phase 5: Independent assessment
### Tasks
- [ ] T5.1 Freeze and evaluate new cases without replacing failures
  - success_check: `python -m pytest tests/test_tdd_cycle_assessment.py -q`
  - verifies: S5.1, S5.2
  - files: `evals/tddbench/assessment.py, tests/test_tdd_cycle_assessment.py`
