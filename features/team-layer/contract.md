# Contract: Athena Team Layer (v3.11)

> Seven weaknesses named against modern AI-native and spec-driven practice, each closed
> here as a clause group before the code existed: specs as data run in-process, decisions
> kept in the repository, intake from the world, ids that survive parallel authors, a
> harness that hands the agent its context, budgets and a record of runs, and proofs over
> generated inputs instead of hand-picked examples. Ids are allocated once and never reused.

## C-1 — Specs as data

- **C-1.1** — WHEN a case file is read THE SYSTEM SHALL parse its given, when and then parts
  and refuse one that lacks any of them.
  - see: ../../docs/adr/0001-specs-as-data.md@37819ca615f913ce
  - source: review
- **C-1.2** — WHEN a case is run THE SYSTEM SHALL execute it in the current process without
  spawning another.
- **C-1.3** — WHEN a case's then part does not hold THE SYSTEM SHALL report it red with the
  expected and the actual value.
- **C-1.4** — WHEN a case expects an exception THE SYSTEM SHALL pass only when that exception
  type is raised.
- **C-1.5** — WHEN a scenario names a case and no run command THE SYSTEM SHALL derive a run
  command that replays the case, so the map, the mutation sweep and the guard keep working.
- **C-1.6** — WHEN specs are run THE SYSTEM SHALL run case scenarios in-process alongside
  command scenarios and record both in one ledger.
- **C-1.7** — WHEN a case names a clause other than the one its scenario verifies THE SYSTEM
  SHALL report the binding as broken.

## C-2 — Decisions kept in the repository

- **C-2.1** — WHEN a decision record is read THE SYSTEM SHALL require an id, a status, a
  date, a context, a decision and consequences.
  - see: ../../docs/adr/0002-decisions-live-in-docs-adr.md@d8867aa30ff86c0c
  - source: review
- **C-2.2** — WHEN a decision record is cited by no clause of any contract THE SYSTEM SHALL
  report it as unlinked.
- **C-2.3** — WHEN the ownership file is read THE SYSTEM SHALL name a human owner for the
  core, every contract and every decision record.
- **C-2.4** — WHEN the design step of the planning pipeline is read THE SYSTEM SHALL name the
  decision records directory as the home of its decisions.

## C-3 — Intake from the world

- **C-3.1** — WHEN a failure is taken in THE SYSTEM SHALL append a draft clause carrying the
  given source and a fresh id.
  - see: ../../docs/adr/0004-intake-writes-draft-and-red-first.md@d20d54ea705ef452
  - source: review
- **C-3.2** — WHEN a failure is taken in THE SYSTEM SHALL bind a spec to the new clause so
  that coverage counts it and `todo` lists it as backlog.
- **C-3.3** — WHEN a failure record is given as a file THE SYSTEM SHALL cite it from the
  clause with its fingerprint.
- **C-3.4** — WHEN a failure is taken in THE SYSTEM SHALL leave the clause draft, never
  active.
  - note: promotion to active is a human reading the wording and the red spec. The intake
    is the fast path from a trace to a requirement, not a way around the review.
- **C-3.5** — WHEN intake writes a case skeleton THE SYSTEM SHALL keep it red until somebody
  writes the then part.

## C-4 — Ids for parallel authors

- **C-4.1** — WHEN the next id of a group is requested THE SYSTEM SHALL return one no clause
  of the contract carries.
  - see: ../../docs/adr/0003-clause-id-lanes.md@da2be0dc06d15d89
  - source: review
- **C-4.2** — WHEN two lanes request ids for one group THE SYSTEM SHALL draw them from ranges
  that never overlap.
- **C-4.3** — WHEN no lane is given THE SYSTEM SHALL read it from the ATHENA_LANE variable
  and fall back to lane zero.

## C-5 — The harness hands the agent its context

- **C-5.1** — WHEN an edit of a source file is about to happen THE SYSTEM SHALL name the
  clauses whose owned lines it touches, across every contract that has a map.
  - see: ../../docs/adr/0005-harness-hooks.md@bf102e2dcc6a17f6
  - source: review
- **C-5.2** — WHEN an edit targets a derived artifact THE SYSTEM SHALL refuse it and name the
  command that rebuilds it.
- **C-5.3** — WHEN the bypass variable is set THE SYSTEM SHALL allow the derived edit and say
  that it was bypassed.
- **C-5.4** — WHEN a module outside the effect allowlist imports a process or network module
  THE SYSTEM SHALL report it.
- **C-5.5** — WHEN the architecture lint runs on this repository THE SYSTEM SHALL report
  nothing.
- **C-5.6** — WHEN the project's agent settings are read THE SYSTEM SHALL register the
  pre-edit hook for edits and writes.

## C-6 — Budgets, and the record of runs

- **C-6.1** — WHEN the gate runs over this repository THE SYSTEM SHALL answer within two
  seconds.
  - tags: performance
  - source: review
- **C-6.2** — WHEN a spec run completes THE SYSTEM SHALL append one run record with its
  verdict counts and duration.
- **C-6.3** — WHEN metrics are requested THE SYSTEM SHALL report iterations to green and the
  mean duration from the run records.
- **C-6.4** — WHEN a run record is malformed THE SYSTEM SHALL skip it and still answer.

## C-7 — Proofs over generated inputs

- **C-7.1** — WHEN any well-formed contract is rendered and parsed again THE SYSTEM SHALL
  yield the same ids, statuses, sources, tags and supersede links.
  - source: review
- **C-7.2** — WHEN any clause text is only re-wrapped or re-spaced THE SYSTEM SHALL keep its
  version.
- **C-7.3** — WHEN any word of a clause changes THE SYSTEM SHALL change its version.
- **C-7.4** — WHEN any supersede graph is given, cycles included, THE SYSTEM SHALL terminate
  resolution for every id.
- **C-7.5** — WHEN arbitrary text is parsed THE SYSTEM SHALL raise nothing but the contract
  parse error.
  - tags: security
- **C-7.6** — WHEN any command line is classified for batching THE SYSTEM SHALL keep its
  prefix and nodes together equal to the tokens of the command.
