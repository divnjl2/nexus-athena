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
  - verifies: S2.1, S2.2, S2.3

### Manual Verification
- `python -m evals.self_improve.evidence --attempts <runs.jsonl> --artifacts <dir>` exits 2 when any task-arm cell is missing.
