# Plan: Athena Executor Layer

## Overview
Close the deferred executor with the frame: a work packet derived from contract, scenarios
and plan; a verdict computed from the workspace diff and the spec commands; a registry of
executors (local lanes, OpenHands, Claude Code) behind one dispatch command; and a record
that says, per executor, how often the work landed and went green.

## Out of Scope
- Driving bd's ready queue; `ralph/adapter.py` keeps that loop.
- Sandboxing; the executor works in the repository or a worktree the caller chose.
- Judging plan quality; only whether the task's specs went green.

## Phase 1: The packet
**Goal:** what an executor receives is derived from the artifacts, never hand-composed.
**Depends on:** none
### Tasks
- [ ] T1.1 Build and render the packet; refuse unknown specs; report oversize
  - success_check: `python -m pytest tests/test_dispatch.py -q -k packet`
  - files: `lib/dispatch.py, tests/test_dispatch.py`
  - verifies: S1.1, S1.2, S1.3, S1.4, S1.5, S1.6, S1.7, S1.8
### Manual Verification
- `python athena.py dispatch features/team-layer/contract.md --front features/team-layer/plan.md --task T5.1 --executor none` prints the packet.

## Phase 2: The verdict
**Goal:** the executor's report is recorded and ignored; diff and exit codes decide.
**Depends on:** none
### Tasks
- [ ] T2.1 Compute the verdict from snapshots and check results; flag touched contracts and derived files
  - success_check: `python -m pytest tests/test_dispatch.py -q -k "verdict or landed or red or flags"`
  - files: `lib/dispatch.py, tests/test_dispatch.py`
  - verifies: S2.1, S2.2, S2.3, S2.4, S2.5, S2.6, S2.7
### Manual Verification
- A dispatch whose worker changed nothing ends with `landed: false` whatever the worker said.

## Phase 3: Executors
**Goal:** one registry, three executors, none of them trusted.
**Depends on:** Phase 1
### Tasks
- [ ] T3.1 Registry, the local-lane command, the OpenHands configuration, availability
  - success_check: `python -m pytest tests/test_executors.py -q`
  - files: `lib/executors.py, tests/test_executors.py`
  - verifies: S3.1, S3.2, S3.3, S3.4, S3.5, S3.6, S3.7
### Manual Verification
- `python athena.py dispatch ... --executor local-27b` lands the C-5.7 change in a worktree and its spec goes green.

## Phase 4: The record
**Goal:** the numbers that decide whether local models suffice are read from the record.
**Depends on:** Phase 2, Phase 3
### Tasks
- [ ] T4.1 Append the dispatch record, report per-executor rates, print-only mode
  - success_check: `python -m pytest tests/test_dispatch.py -q -k "record or metrics or printed"`
  - files: `lib/dispatch.py, athena.py, tests/test_dispatch.py`
  - verifies: S4.1, S4.2, S4.3
- [ ] T4.2 Report iterations to green per task in the dispatch metrics
  - success_check: `python -m pytest tests/test_dispatch.py::test_dispatch_metrics_report_iterations_to_green_per_task -q`
  - files: `lib/dispatch.py`
  - verifies: S4.4
### Manual Verification
- `python athena.py metrics features/executor-layer/contract.md --text` shows a dispatch section.

## Phase 5: Iterations with checkpoints
**Goal:** long work crosses iterations through checkpoints, so a 30k window and six slots stay.
**Depends on:** Phase 2, Phase 3
### Tasks
- [ ] T5.1 Checkpoint after a short iteration, carry it into the next packet, stop on green, note it in bd
  - success_check: `python -m pytest tests/test_dispatch.py -q -k "checkpoint or iteration or budget"`
  - files: `lib/dispatch.py, athena.py, tests/test_dispatch.py`
  - verifies: S5.1, S5.2, S5.3, S5.4, S5.5
- [ ] T5.2 Fan out the attempts of an iteration over copies of the workspace; keep the first green, else the least red landing
  - success_check: `python -m pytest tests/test_dispatch.py -q -k "fanned or least_red"`
  - files: `lib/dispatch.py, athena.py, tests/test_dispatch.py`
  - verifies: S5.6, S5.7
- [ ] T5.3 The selection module: cluster attempts by behaviour, choose the largest green cluster
  - success_check: `python -m pytest tests/test_select.py -q`
  - files: `lib/select.py`
  - verifies: S5.8
### Manual Verification
- `python athena.py dispatch ... --executor local-27b --iterations 3 --text` reports the iteration count and leaves `.athena/checkpoints/<task>.md` when short of green.

## Phase 6: The gateway relay
**Goal:** a model's tool-call shape is absorbed on the client side; the lanes are never touched.
**Depends on:** Phase 3
### Tasks
- [ ] T6.1 Normalise tool calls left as text; serve the relay; let OpenHands point at it
  - success_check: `python -m pytest tests/test_toolcalls.py -q`
  - files: `lib/toolcalls.py, athena.py, lib/executors.py, tests/test_toolcalls.py`
  - verifies: S6.1, S6.2, S6.3, S6.4, S6.5, S6.6
### Manual Verification
- `python athena.py relay --port 8414` then `athena dispatch ... --executor openhands --base-url http://127.0.0.1:8414/v1` makes tool calls the lane's parser refused.

## Phase 7: The ceiling
**Goal:** four graded tasks, one clause each, that say how far a local model in a harness reaches.
**Depends on:** Phase 3
### Tasks
- [ ] T7.1 The bench module: plan the matrix, fold the record, render the table
  - success_check: `python -m pytest tests/test_bench.py::test_a_bench_matrix_is_planned_and_read_back_from_the_record -q`
  - files: `lib/bench.py`
  - verifies: S7.1
- [ ] T7.2 The witness: end a silent worker at the stall window, report stalled
  - success_check: `python -m pytest tests/test_witness.py -q`
  - files: `athena.py`
  - verifies: S7.2
- [ ] T7.3 The queue module: pick and claim the next ready task of a slug
  - success_check: `python -m pytest tests/test_next.py -q`
  - files: `lib/queue.py`
  - verifies: S7.3
- [ ] T7.4 The bench command: run the matrix through dispatch, or print the plan when dry
  - success_check: `python -m pytest tests/test_bench.py::test_the_bench_command_prints_its_plan_without_running_when_dry -q`
  - files: `athena.py, lib/bench.py`
  - verifies: S7.4
### Manual Verification
- `python athena.py bench features/refinery-layer/contract.md --front features/refinery-layer/plan.md --tasks T2.1,T2.3 --executors pi-9b,pi-27b --base-workspace <dir> --dry-run` prints the plan.

## Phase 8: The second source
**Goal:** tests and locations the swarm proposes and the frame selects by behaviour.
**Depends on:** Phase 5
### Tasks
- [ ] T8.1 The test-writer module: admissible candidates, clustering, the chosen test
  - success_check: `python -m pytest tests/test_testwriter.py -q`
  - files: `lib/testwriter.py`
  - verifies: S8.1
- [ ] T8.2 The locator module: repo map within a budget, reply parsing, merged votes
  - success_check: `python -m pytest tests/test_locate.py -q`
  - files: `lib/locate.py`
  - verifies: S8.2
### Manual Verification
- `python athena.py testwrite <contract> --clause C-x.y --executor pi-9b --n 4` leaves one red test that fails on the current code.
- `python athena.py locate <contract> --clause C-x.y --executor pi-27b --n 3` prints the top files.
