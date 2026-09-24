# ADR-0007: The local Qwopus model executes through the Claude Code harness

- Status: accepted
- Date: 2026-09-24
- Deciders: operator
- Cited by: features/executor-layer C-4.4

## Context

Qwopus 3.8 27B is a distillate trained on Opus traces: Claude Code's tools (Read, Edit,
Write, exact `old_string`) and its habits are what it learned. Measured on one clause with
every lever the frame could pull: through Claude Code the model landed a green edit in 2 of
8 dispatches; through OpenHands, 0 of 15 — with the red spec status in the packet it did
edit, but in a tool vocabulary it did not learn it never converged, and without it it read.
OpenHands' own documentation calls that behaviour model capability. The inference lanes
are the operator's and are not touched, so the harness has to fit the model, not the other
way round.

## Decision

The default executor for Qwopus is `local-27b`: a Claude Code worker on the local model
through the gateway, driven by `athena dispatch` with one clause, one spec and one file per
task, the file and the test source inlined, the repository root named absolutely, fresh-
context iterations with checkpoints when the first attempt is short of green. OpenHands
stays in the registry for a model trained on its traces (the docs name Qwen3.6-35B-A3B) or
for Claude on the subscription run from a plain shell; the relay and the packet already fit
it. The operator writes clauses and red specs and reads verdicts; the model types.

## Consequences

- `athena metrics` per executor and per task is the standing evidence for this choice;
  when a different model arrives, the same dispatches re-measure it in an afternoon.
- The lanes bridge (`run_local`) and `athena dispatch --executor local-27b` are the same
  path; the latter is judged by diff and specs and is preferred.
- A task that the lane cannot land in three iterations goes to Claude, not to more turns.
