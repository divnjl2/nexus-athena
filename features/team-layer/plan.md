# Plan: Athena Team Layer

## Overview
Close the seven weaknesses found against modern AI-native and spec-driven practice, each as
a clause group proved before the code: cases as in-process specs, decisions kept under
docs/adr with a human owner, an intake path from a failure to a draft clause and a red spec,
lane-based id allocation for parallel authors, a pre-edit hook that hands the agent the
blast radius and refuses hand-edits of derived artifacts, an architecture lint, budgets
with a record of runs, and property-based proofs of the parser, the pins and the batch key.

## Out of Scope
- Reading telemetry systems directly; intake takes a file somebody exported.
- Replaying whole agent trajectories; `lessons rerun` stays at the spec level.
- Hash-shaped clause ids; the grammar stays readable and lanes do the collision work.
- An executor; attempts-to-green come from run records, not from bd task provenance.

## Phase 1: Specs as data
**Goal:** a scenario can be a JSON case run in the current process, with every downstream tool unchanged.
**Depends on:** none
### Tasks
- [ ] T1.1 Add the case format, the in-process runner and the derived run command
  - success_check: `python -m pytest tests/test_cases.py -q`
  - files: `lib/cases.py, lib/scenario_parser.py, lib/ast.py, lib/spec_runner.py, athena.py, tests/test_cases.py`
  - verifies: S1.1, S1.2, S1.3, S1.4, S1.5, S1.6, S1.7
### Manual Verification
- `python athena.py case run features/team-layer/cases/S2.5-adr-parses.json` exits 0.

## Phase 2: Decisions kept
**Goal:** decisions are records in the repository, cited by clauses and owned by a human.
**Depends on:** none
### Tasks
- [ ] T2.1 Parse and lint decision records, report unlinked ones, own the hand-written layers
  - success_check: `python -m pytest tests/test_adr.py -q`
  - files: `lib/adr.py, athena.py, docs/adr/, .github/CODEOWNERS, commands/crisp/3_design.md, tests/test_adr.py`
  - verifies: S2.1, S2.2, S2.3, S2.4, S2.5
### Manual Verification
- `python athena.py adr lint docs/adr` and `python athena.py adr unlinked docs/adr` are clean.

## Phase 3: Intake from the world
**Goal:** a failure becomes a draft clause and a red spec in one command.
**Depends on:** Phase 1, Phase 4
### Tasks
- [ ] T3.1 Implement intake: draft clause, trace citation, bound spec or red skeleton
  - success_check: `python -m pytest tests/test_intake.py -q`
  - files: `lib/intake.py, athena.py, tests/test_intake.py`
  - verifies: S3.1, S3.2, S3.3, S3.4, S3.5
### Manual Verification
- `python athena.py intake <contract> --group C-1 --source incident --text "WHEN ... THE SYSTEM SHALL ..."` then `contract todo` shows backlog=1.

## Phase 4: Ids for parallel authors
**Goal:** two authors on two branches never allocate the same id.
**Depends on:** none
### Tasks
- [ ] T4.1 Implement lane-based allocation and the next-id command
  - success_check: `python -m pytest tests/test_allocate.py -q`
  - files: `lib/allocate.py, athena.py, tests/test_allocate.py`
  - verifies: S4.1, S4.2, S4.3, S4.4
### Manual Verification
- `ATHENA_LANE=2 python athena.py contract next-id features/team-layer/contract.md C-4` prints C-4.2001.

## Phase 5: The harness
**Goal:** the agent sees the blast radius before an edit, derived artifacts stay derived, effects stay behind the seams.
**Depends on:** none
### Tasks
- [ ] T5.1 Implement the pre-edit hook decision and the architecture lint; register the hook
  - success_check: `python -m pytest tests/test_harness.py -q`
  - files: `lib/hooks.py, lib/archlint.py, athena.py, hooks/pre-edit.sh, .claude/settings.json, tests/test_harness.py`
  - verifies: S5.1, S5.2, S5.3, S5.4, S5.5, S5.6, S5.7
### Manual Verification
- `echo '{"tool_input":{"file_path":"lib/contract.py"}}' | python athena.py hook pre-edit` lists owning clauses.

## Phase 6: Budgets and the record of runs
**Goal:** the gate has a latency budget, and every run leaves a record metrics can read.
**Depends on:** none
### Tasks
- [ ] T6.1 Append run records, compute iterations-to-green, time the gate
  - success_check: `python -m pytest tests/test_budgets.py -q`
  - files: `lib/metrics.py, athena.py, tests/test_budgets.py`
  - verifies: S6.1, S6.2, S6.3, S6.4
### Manual Verification
- `python athena.py metrics features/team-layer/contract.md --text` reports runs and cycles.

## Phase 7: Proofs over generated inputs
**Goal:** the invariants of the parser, the pins and the batch key hold over generated inputs, not examples.
**Depends on:** none
### Tasks
- [ ] T7.1 Property-based specs with hypothesis
  - success_check: `python -m pytest tests/test_properties.py -q`
  - files: `tests/test_properties.py`
  - verifies: S7.1, S7.2, S7.3, S7.4, S7.5, S7.6
### Manual Verification
- `python -m pytest tests/test_properties.py -q` stays under ten seconds.
