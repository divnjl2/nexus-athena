# ADR-0003: Clause ids for parallel authors are drawn from lanes

- Status: accepted
- Date: 2026-09-23
- Deciders: operator
- Cited by: features/team-layer C-4.*

## Context

A clause id is allocated once and never reused. Two agents on two branches both allocate
`C-3.19`; the merge produces a duplicate id, which the parser refuses outright. Beads solved
the same problem for tasks with hash ids; the clause grammar (`C-3.19`) has no room for a
hash, and readable numbers are part of the point.

## Decision

Ids are allocated through `athena contract next-id <contract> <group> [--lane N]`. Lane
zero allocates the next number below one thousand; lane N allocates from
`N*1000 .. N*1000+999`. The lane comes from `--lane`, else from `ATHENA_LANE`, else zero.
An author or a long-lived branch takes a lane. Intake and any tool that writes a clause
use the allocator; a human writing by hand may still pick the next number in lane zero.
CODEOWNERS on `contract.md` keeps the merge in a human's hands.

## Consequences

- Ids in a lane read as `C-3.1019`; the number says who allocated it.
- A collision is still possible inside one lane and is still a parse error; lanes make the
  common case (parallel branches) collision-free without a central counter.
- The grammar is unchanged, so every existing reference keeps resolving.
