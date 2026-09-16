# Contract: Athena Core Layer (v3.10)

> The top of the pyramid, applied to the frame itself. The contract layer (v3.3) made
> requirement, spec and code one linear scan; this layer adds what sat above and around it:
> a semantic core the clauses cite, the origin of each clause, a rerun of every lesson, one
> way into the repository, the gate that makes the criterion bite, and a spec lane fast
> enough to be the inner loop. Every clause below is proved by an executable spec in
> `scenarios.md`; ids are allocated once and never reused.

## C-1 — The semantic core

- **C-1.1** — WHEN a feature is scaffolded and no core document exists above it THE SYSTEM
  SHALL write one that names the goal, the language, the priorities and the constraints.
  - see: ../../CORE.md@72d8198febff12a0
- **C-1.2** — WHEN a feature is scaffolded THE SYSTEM SHALL cite the core document from the
  first clause together with the fingerprint of the text that was written.
- **C-1.3** — WHEN the core template is rendered THE SYSTEM SHALL produce at most forty
  lines.
  - note: the core is the file a human reads before anything else and every agent loads
    first; past forty lines it stops being read and starts being skimmed.
- **C-1.4** — WHEN the core document changes after a clause cited it THE SYSTEM SHALL report
  that clause's reference as suspect.
- **C-1.5** — WHEN a suspect or broken core reference exists THE SYSTEM SHALL fail the check
  on the contract leg.
  - note: this is how a change to the principles becomes a conscious act: the diff of one
    file plus the list of clauses somebody must re-read before the gate is green again.

## C-2 — Where a clause came from

- **C-2.1** — WHEN a clause carries a source attribute THE SYSTEM SHALL read it as an
  attribute and keep it out of the normative text.
- **C-2.2** — WHEN a clause names a source outside the defined vocabulary THE SYSTEM SHALL
  report it in lint.
  - note: the vocabulary is `design`, `review`, `audit`, `incident`, `ledger`, `mutation`.
    Everything except `design` is a failure signal, and a clause born from one is a lesson.
- **C-2.3** — WHEN a contract is rendered THE SYSTEM SHALL round-trip the source attribute
  through the parser.
- **C-2.4** — WHEN the sources report is requested THE SYSTEM SHALL list every clause under
  its source in document order.
- **C-2.5** — WHEN a clause names no source THE SYSTEM SHALL count it as unstated rather than
  assign one.

## C-3 — Lessons, rerun

- **C-3.1** — WHEN lessons are listed THE SYSTEM SHALL select the clauses whose source is a
  failure signal and skip the withdrawn ones.
- **C-3.2** — WHEN a lesson clause is superseded THE SYSTEM SHALL carry the lesson forward to
  its live successors.
  - note: the wrong guess stays on the record with its source; what is rerun is the proof
    of whatever replaced it.
- **C-3.3** — WHEN lessons are rerun THE SYSTEM SHALL run only the specs bound to the live
  lesson clauses.
- **C-3.4** — WHEN any spec of a lesson is red after the rerun THE SYSTEM SHALL report that
  lesson as forgotten.
- **C-3.5** — WHEN a live lesson clause has no bound spec THE SYSTEM SHALL report the lesson
  as unproved rather than pass it.
- **C-3.6** — WHEN every spec of a lesson was left out of a rerun on purpose THE SYSTEM SHALL
  report the lesson as skipped rather than kept or forgotten.
  - source: ledger
  - note: found on the first rerun of the contract layer with `--skip-tag slow`: the real-bd
    lesson C-5.11 came back forgotten for a spec nobody ran. A lane the caller chose is not
    silence, but it is not proof either, so it gets its own word.

## C-4 — The way in

- **C-4.1** — WHEN the repository root is read THE SYSTEM SHALL provide an entry document of
  at most thirty lines that names the core, the contract and the check command.
- **C-4.2** — WHEN a design history document is kept THE SYSTEM SHALL keep it under
  docs/history and none at the repository root.
  - note: seven files named athena-*-plan-v*.md sat in the root; a reader took them for
    the way in. File names are part of the disclosure order.
- **C-4.3** — WHEN the entry document names a CLI command THE SYSTEM SHALL name one the CLI
  accepts.

## C-5 — The gate that makes it the criterion

- **C-5.1** — WHEN the repository's agent settings are read THE SYSTEM SHALL register the
  contract criterion gate as a Stop hook.
  - source: audit
  - note: the gate script existed on disk for a month and was registered nowhere. A lesson
    that does not change a check is not learned.
- **C-5.2** — WHEN the gate scans a directory THE SYSTEM SHALL recognise a contract by its
  clause bullets and not by its file name.
  - source: incident
  - note: the first cut picked commands/contract.md, a slash-command document, and died on
    "no clauses parsed".
- **C-5.3** — WHEN the gate finds several contracts THE SYSTEM SHALL fold their verdicts so
  that one failing contract fails the gate.
- **C-5.4** — WHEN the gate finds no contract THE SYSTEM SHALL pass without an opinion.
- **C-5.5** — WHEN a contract fails under the gate THE SYSTEM SHALL name that contract and its
  first cause in the reason.
- **C-5.6** — WHEN the bypass variable is set THE SYSTEM SHALL pass and say that it was
  bypassed.
- **C-5.7** — WHEN the gate has already blocked twice in one session THE SYSTEM SHALL pass
  and say that the nudge budget is spent.

## C-6 — The fast lane: one process for many specs

- **C-6.1** — WHEN several specs share one runner invocation apart from the test node THE
  SYSTEM SHALL run them in a single process.
  - source: ledger
  - note: C-3.9 of the contract layer named batching and was refuted, because plugin
    autoload was the ten seconds then. With autoload off the floor moved to interpreter
    start (a 523 ms median per spec run one at a time, 146 s for 183 specs on one worker)
    and batching became the lever (14.4 s). Measured both times; the numbers are in README.
- **C-6.2** — WHEN specs run in one process THE SYSTEM SHALL attribute a verdict and a duration
  to each spec from the runner's own report.
- **C-6.3** — WHEN a spec is absent from the runner's report THE SYSTEM SHALL record it as red
  rather than pass it.
- **C-6.4** — WHEN a spec's clause carries the isolated tag THE SYSTEM SHALL run that spec in a
  process of its own.
- **C-6.5** — WHEN an invocation carries an option that ends the run early or names its own
  report THE SYSTEM SHALL leave it out of every batch.
- **C-6.6** — WHEN a batched run ends before any spec reported THE SYSTEM SHALL rerun that
  batch one process per spec.
  - source: ledger
  - note: pytest aborts the whole invocation on one unknown node id and reports zero tests;
    without this rule one typo would redden every spec in the batch.
- **C-6.7** — WHEN a batched spec fails THE SYSTEM SHALL keep its failure message in the
  ledger.
- **C-6.8** — WHEN an executor is injected for a run THE SYSTEM SHALL run every spec through it
  one command at a time.
  - note: the injected executor is the seam every existing runner spec relies on; batching
    is the default path only.
