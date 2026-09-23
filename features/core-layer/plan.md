# Plan: Athena Core Layer

## Overview
Apply the frame to the frame: give the pyramid its top and its edges. A semantic core the
clauses cite (and go suspect when it moves), a `source:` on every clause so lessons are a
linear scan, `athena lessons rerun` as the check that a lesson was learned, one entry
document at the root, a gate that judges every contract in the repository on Stop, and a
spec lane that runs many specs in one process so the loop is seconds instead of minutes.
Written contract-first: every clause here was red before the code existed.

## Out of Scope
- Product telemetry or incident intake (a clause is written by a human from the signal).
- A Gherkin runner; specs stay bound to the project's own test runner.
- Changing the v3.3 ledger or clause-map schema.
- Any executor; `implement` stays deferred.

## Phase 1: The semantic core
**Goal:** a project starts with a core document, and every scaffolded contract cites it by fingerprint.
**Depends on:** none
### Tasks
- [ ] T1.1 Add the core template to the scaffold and cite it from the first clause
  - success_check: `python -m pytest tests/test_core.py -q`
  - files: `lib/scaffold.py, athena.py, CORE.md, tests/test_core.py`
  - verifies: S1.1, S1.2, S1.3, S1.4, S1.5
### Manual Verification
- `python athena.py init /tmp/demo --title Demo` writes CORE.md; `athena check` on it passes.

## Phase 2: Where a clause came from
**Goal:** the origin of a clause is an attribute the reports can scan, never prose.
**Depends on:** none
### Tasks
- [ ] T2.1 Parse, lint, render and report the `source:` attribute
  - success_check: `python -m pytest tests/test_source_attr.py -q`
  - files: `lib/ast.py, lib/contract.py, lib/contract_report.py, athena.py, tests/test_source_attr.py`
  - verifies: S2.1, S2.2, S2.3, S2.4, S2.5
### Manual Verification
- `python athena.py contract sources features/contract-layer/contract.md --text` lists the retro-annotated lessons.

## Phase 3: Lessons, rerun
**Goal:** the old failure is rerun on the new configuration, and a forgotten lesson is a red verdict.
**Depends on:** Phase 2
### Tasks
- [ ] T3.1 Derive the lesson set from the contract and rerun its specs
  - success_check: `python -m pytest tests/test_lessons.py -q`
  - files: `lib/lessons.py, athena.py, tests/test_lessons.py`
  - verifies: S3.1, S3.2, S3.3, S3.4, S3.5, S3.6
### Manual Verification
- `python athena.py lessons rerun features/contract-layer/contract.md --text` reports every lesson kept.

## Phase 4: The way in
**Goal:** a reader lands on one short document that leads to the core, the contract and the check.
**Depends on:** Phase 1
### Tasks
- [ ] T4.1 Write CLAUDE.md as the entry and move design history under docs/history
  - success_check: `python -m pytest tests/test_entry.py -q`
  - files: `CLAUDE.md, docs/history/, README.md, tests/test_entry.py`
  - verifies: S4.1, S4.2, S4.3
### Manual Verification
- The repository root lists no athena-*-plan-*.md file.

## Phase 5: The gate
**Goal:** the criterion is enforced on Stop for every contract in the repository, cheaply.
**Depends on:** Phase 2
### Tasks
- [ ] T5.1 Implement `athena gate`: find contracts by content, fold verdicts, emit the hook decision
  - success_check: `python -m pytest tests/test_gate.py -q`
  - files: `lib/gate.py, athena.py, tests/test_gate.py`
  - verifies: S5.2, S5.3, S5.4, S5.5, S5.6, S5.7
- [ ] T5.2 Register the gate as a Stop hook in the project settings through a thin shell shim
  - success_check: `python -m pytest tests/test_gate.py::test_the_project_settings_register_the_gate_as_a_stop_hook -q`
  - files: `hooks/contract-criterion-gate.sh, .claude/settings.json`
  - verifies: S5.1
### Manual Verification
- `echo '{"cwd":"."}' | python athena.py gate --hook` prints nothing when every contract holds.

## Phase 6: The fast lane
**Goal:** many specs, one process; per-spec verdicts kept; the batch never hides a spec.
**Depends on:** none
### Tasks
- [ ] T6.1 Batch specs that share an invocation and attribute results from the runner's report
  - success_check: `python -m pytest tests/test_spec_batch.py -q`
  - files: `lib/spec_runner.py, athena.py, tests/test_spec_batch.py`
  - verifies: S6.1, S6.2, S6.3, S6.4, S6.5, S6.6, S6.7, S6.8
### Manual Verification
- `python athena.py spec run features/contract-layer/scenarios.md --skip-tag slow --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` finishes in seconds with the same verdicts as the per-process lane.
