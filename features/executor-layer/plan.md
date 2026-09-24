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
  - verifies: S1.1, S1.2, S1.3, S1.4, S1.5, S1.6
### Manual Verification
- `python athena.py dispatch features/team-layer/contract.md --front features/team-layer/plan.md --task T5.1 --executor none` prints the packet.

## Phase 2: The verdict
**Goal:** the executor's report is recorded and ignored; diff and exit codes decide.
**Depends on:** none
### Tasks
- [ ] T2.1 Compute the verdict from snapshots and check results; flag touched contracts and derived files
  - success_check: `python -m pytest tests/test_dispatch.py -q -k "verdict or landed or red or flags"`
  - files: `lib/dispatch.py, tests/test_dispatch.py`
  - verifies: S2.1, S2.2, S2.3, S2.4, S2.5
### Manual Verification
- A dispatch whose worker changed nothing ends with `landed: false` whatever the worker said.

## Phase 3: Executors
**Goal:** one registry, three executors, none of them trusted.
**Depends on:** Phase 1
### Tasks
- [ ] T3.1 Registry, the local-lane command, the OpenHands configuration, availability
  - success_check: `python -m pytest tests/test_executors.py -q`
  - files: `lib/executors.py, tests/test_executors.py`
  - verifies: S3.1, S3.2, S3.3, S3.4, S3.5
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
### Manual Verification
- `python athena.py dispatch ... --executor local-27b --iterations 3 --text` reports the iteration count and leaves `.athena/checkpoints/<task>.md` when short of green.

## Phase 6: The gateway relay
**Goal:** a model's tool-call shape is absorbed on the client side; the lanes are never touched.
**Depends on:** Phase 3
### Tasks
- [ ] T6.1 Normalise tool calls left as text; serve the relay; let OpenHands point at it
  - success_check: `python -m pytest tests/test_toolcalls.py -q`
  - files: `lib/toolcalls.py, athena.py, lib/executors.py, tests/test_toolcalls.py`
  - verifies: S6.1, S6.2, S6.3, S6.4
### Manual Verification
- `python athena.py relay --port 8414` then `athena dispatch ... --executor openhands --base-url http://127.0.0.1:8414/v1` makes tool calls the lane's parser refused.
