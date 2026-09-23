# ADR-0004: Intake from the world writes a draft clause and a red spec first

- Status: accepted
- Date: 2026-09-23
- Deciders: operator
- Cited by: features/team-layer C-3.*

## Context

`source: incident` was a word with no path behind it. A failure seen in a trace, a log or
a failed agent run had no fast way into the contract; it went into somebody's memory and
from there, sometimes, into code. The reference practice turns each production failure
into a regression case before the fix.

## Decision

`athena intake <contract> --group C-n --source <signal> --text "WHEN ... THE SYSTEM SHALL
..." [--trace <file>] [--run-cmd <cmd>]` appends a DRAFT clause with the source and a fresh
id from the allocator, cites the trace file by fingerprint, and binds a spec: the given
run command, or a case skeleton whose `then` is `pending`, which the runner keeps red until
the assertion is written from the trace. The clause is never written active: promotion is a
human reading the wording and the red spec.

## Consequences

- `coverage` sees the new clause covered, `todo` lists it as backlog, `lessons` picks it up
  the moment it goes active.
- The failing spec exists before the fix, by construction.
- Intake does not read telemetry systems itself; the trace is a file somebody exported.
