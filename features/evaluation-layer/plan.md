# Plan: Athena Evaluation Foundation

## Overview
Build a reproducible comparison of ordinary Codex, Codex with Athena, and Codex with
Athena plus an optimizer. The corpus, run evidence and report are separate artifacts.

## Phase 1: Freeze the corpus
**Goal:** fix real tasks before any optimization.
**Depends on:** none
### Tasks
- [ ] T1.1 Freeze and validate the stratified pilot task set
  - success_check: `python -m pytest tests/test_self_improve_corpus.py -q`
  - files: `evals/self_improve/corpus.py, evals/self_improve/manifest.json, tests/test_self_improve_corpus.py`
  - verifies: S1.1, S1.2, S1.3

### Manual Verification
- `python -m evals.self_improve.corpus verify` checks the committed manifest against the pinned source revision.

## Phase 2: Record evidence and summarize
**Goal:** reject inconsistent attempt records and expose missing comparisons.
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 Validate attempt provenance and calculate the pilot matrix
  - success_check: `python -m pytest tests/test_self_improve_evidence.py -q`
  - files: `evals/self_improve/evidence.py, tests/test_self_improve_evidence.py`
  - verifies: S2.1, S2.2, S2.3, S2.4, S2.5, S2.6

### Manual Verification
- `python -m evals.self_improve.evidence --attempts <runs.jsonl> --artifacts <dir>` exits 2 when any task-arm cell is missing.

## Phase 3: Isolate and capture candidates
**Goal:** run each task-arm attempt at its pinned base and preserve its patch and trace.
**Depends on:** Phase 1
### Tasks
- [ ] T3.1 Plan and create task worktrees and capture Codex candidates
  - success_check: `python -m pytest tests/test_self_improve_workspaces.py tests/test_self_improve_codex_driver.py tests/test_self_improve_pilot.py -q`
  - files: `evals/self_improve/workspaces.py, evals/self_improve/codex_driver.py, evals/self_improve/pilot.py, tests/test_self_improve_workspaces.py, tests/test_self_improve_codex_driver.py, tests/test_self_improve_pilot.py`
  - verifies: S3.1, S3.2, S3.3, S3.4, S3.5, S3.6, S3.7

## Phase 4: Bind official acceptance
**Goal:** preserve the official test result independently of the agent's claim.
**Depends on:** Phase 1, Phase 3
### Tasks
- [ ] T4.1 Run SWE-bench against a pinned local task snapshot and bind its report
  - success_check: `python -m pytest tests/test_self_improve_gate_adapter.py tests/test_self_improve_pilot.py tests/test_self_improve_evidence.py -q`
  - files: `evals/self_improve/gate_adapter.py, evals/self_improve/evidence.py, evals/self_improve/pilot.py, tests/test_self_improve_gate_adapter.py, tests/test_self_improve_evidence.py, tests/test_self_improve_pilot.py`
  - verifies: S4.1, S4.2, S4.3, S4.4, S4.5, S4.6
