# ADR-0006: Executors under the gate — packets in, verdicts out

- Status: accepted
- Date: 2026-09-23
- Deciders: operator
- Cited by: features/executor-layer C-1.*

## Context

`implement` was deferred since v2: the planner stops at a bd graph, and `ralph/INTERFACE.md`
names the executors (Claude Code, OpenCode, OpenHands, Hermes) behind one adapter contract
with an external gate. The operator wants to orchestrate rather than type: the work should
go to OpenHands or to the local lanes (Claude Code workers on local models through
LiteLLM), with the frame's specs as the harness, and only the review left to the expensive
model. Two measured facts shaped the design: the local 27b lane returned `ok` with no diff
twice, and once it was diagnosed the causes were context (ten turns spent on Read) and an
output cap (2048 tokens) that cut every multi-line edit mid-call.

## Decision

A dispatch has three parts, each a clause group:

1. **The packet** is derived, never hand-composed: for a plan task, the clauses its specs
   verify, the spec commands, the task's files (inlined when the executor has no Bash), and
   the done criterion stated as those commands. A packet over the executor's budget is
   reported, not trimmed.
2. **The verdict** is computed from a workspace snapshot before and after, plus the spec
   commands run shell-less afterwards. The executor's report is recorded and ignored.
   A run that touched a derived artifact or a contract is flagged for review.
3. **Executors** are a registry: `local-27b` / `local-9b` (Claude Code worker, read and edit
   tools only, capped turns, local gateway), `openhands` (SDK, workspace = repository,
   model named by the caller), `claude` (Claude Code with the subscription). An executor
   that is not installed is "unavailable", never a traceback. `--executor none` prints the
   packet for manual delegation.

Every dispatch appends a record; `athena metrics` reports per executor the attempts, the
landed rate and the green rate. Those numbers decide whether local models suffice.

## Consequences

- The orchestrator's job becomes: write clauses and specs, dispatch, read verdicts.
- The gate is the same for a human, a local model, OpenHands or Claude: PASS on the
  contract, non-empty diff.
- OpenHands needs no Docker here: the SDK runs in-process against the repository.
- `ralph/adapter.py` keeps the bd-side loop; this layer is the packet and the verdict.
