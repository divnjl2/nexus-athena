# Contract: Athena Contract Layer (v3.3)

> Athena's own requirement contract for the feature that adds requirement contracts.
> Every clause below is proved by an executable spec in `scenarios.md`, which runs the
> repo's real pytest suite. Dogfood: `athena contract coverage/todo/drift` answer the
> three questions about THIS file.
>
> Clause ids are allocated once and never reused. A requirement that changes is
> superseded, never edited in place, so a reference written today keeps resolving.

## C-1 — Clause identity

- **C-1.1** — WHEN a contract is parsed THE SYSTEM SHALL allocate one immutable id per
  clause and reject a duplicate id outright.
- **C-1.2** — WHEN a clause names successors THE SYSTEM SHALL mark it superseded and keep
  the old id resolvable.
- **C-1.3** — WHEN the supersede link is declared on only one end THE SYSTEM SHALL
  reconstruct both directions.
- **C-1.4** — WHEN a supersede chain branches or spans several hops THE SYSTEM SHALL
  resolve an old reference to every current clause it leads to.
- **C-1.5** — WHEN a supersede chain contains a cycle THE SYSTEM SHALL report it in lint
  and terminate resolution instead of hanging.
- **C-1.6** — WHEN clause text is wrapped across lines THE SYSTEM SHALL join the
  continuation without truncating the tail.
- **C-1.7** — WHEN a supersede reference names a clause absent from the contract THE
  SYSTEM SHALL report a lint issue rather than fail the parse.

## C-2 — Per-clause versioning and pins

- **C-2.1** — WHEN a clause version is computed THE SYSTEM SHALL derive it from that
  clause's normative text alone, so editing one clause leaves every other pin unchanged.
- **C-2.2** — WHEN clause text is only re-wrapped or re-spaced THE SYSTEM SHALL keep its
  version unchanged.
- **C-2.3** — WHEN specs are pinned THE SYSTEM SHALL write the clause version under the
  verifies line and replace a stale pin idempotently.
- **C-2.4** — WHEN a pinned spec is parsed THE SYSTEM SHALL carry the pin into the AST and
  leave it empty for an unpinned spec.
- **C-2.5** — WHEN a contract is rendered THE SYSTEM SHALL round-trip through the parser
  preserving ids, statuses, supersede links and the registry version.

## C-3 — Executable specs and the ledger

- **C-3.1** — WHEN the executable specs are run concurrently THE SYSTEM SHALL return
  results in document order regardless of completion order.
- **C-3.2** — WHEN a spec exceeds its timeout THE SYSTEM SHALL record it as red and
  continue the run.
- **C-3.3** — WHEN a spec command cannot be executed THE SYSTEM SHALL record it as red
  carrying the OS error instead of raising.
- **C-3.4** — WHEN a ledger is built THE SYSTEM SHALL pin the contract and scenario
  versions and roll up total, passed, failed and duration.
- **C-3.5** — WHEN the same results and timestamp are given THE SYSTEM SHALL produce a
  byte-identical ledger.
- **C-3.6** — WHEN the ledger is absent or corrupt THE SYSTEM SHALL treat the specs as
  unrun and still answer.
- **C-3.7** — WHEN a clause or spec prefix is given THE SYSTEM SHALL run only the
  matching specs.
- **C-3.8** — WHEN the selected spec set is empty THE SYSTEM SHALL produce an empty valid
  run rather than an error.
- **C-3.10** *(superseded-by C-3.13 C-3.14)* — WHEN a spec's run_cmd carries shell metacharacters,
  is unparseable or is empty THE SYSTEM SHALL refuse to execute it and record the spec as red,
  and SHALL tokenize every accepted command and run it shell-less.
  - note: split after `critique` flagged it as two obligations in one id — a single spec
    could not have proved both halves.
- **C-3.13** *(supersedes C-3.10)* — WHEN a spec's run_cmd carries shell metacharacters, is
  unparseable or is empty THE SYSTEM SHALL refuse to execute it and record the spec as red.
  - tags: security
- **C-3.14** *(supersedes C-3.10)* — WHEN a run_cmd is accepted THE SYSTEM SHALL tokenize it
  and run it shell-less.
  - tags: security
  - note: a run_cmd is an LLM-hop output, not authored code. Policy already set by
    `planner_verify` (mcp/.../verbs.py); found by the python audit registry when the first
    cut of spec_runner used shell=True.
  - tags: security
- **C-3.9** *(superseded-by C-3.11 C-3.12)* — WHEN the whole spec suite is run THE SYSTEM
  SHALL complete in under five seconds by batching the specs into a single test-runner process.
  - note: the draft named the WRONG mechanism, and measuring it said so. Batching was never
    the lever: of the 10.8s a spec took, 10.3s was third-party pytest plugin autoload (22
    plugins installed on the box), the pool was hardcoded to 8 workers on an 18-core machine,
    and after both were fixed the wall clock was still pinned by ONE inherently slow spec
    (real `bd` + Dolt init, 100.5s vs a 1.21s median). Superseded, not edited: the wrong
    guess stays on the record and `resolve("C-3.9")` lands on what replaced it.
  - tags: performance
- **C-3.11** *(superseded-by C-3.15 C-3.16)* — WHEN specs are run THE SYSTEM SHALL default the
  worker count to the machine's logical cores and SHALL let the caller pin environment variables
  for the spec processes.
- **C-3.15** *(supersedes C-3.11)* — WHEN specs are run without an explicit worker count THE
  SYSTEM SHALL size the pool from the machine's logical cores.
  - tags: performance
- **C-3.16** *(supersedes C-3.11)* — WHEN the caller pins environment variables for a run THE
  SYSTEM SHALL merge them over the inherited environment of every spec process.
  - tags: performance
- **C-3.12** — WHEN a clause carries a tag THE SYSTEM SHALL be able to include or exclude its
  specs by that tag, so one inherently slow spec cannot hold the fast lane hostage.
  - tags: performance

## C-4 — The three questions

- **C-4.1** — WHEN a live clause has no executable spec THE SYSTEM SHALL list it as
  uncovered.
- **C-4.2** — WHEN a spec names an unknown or withdrawn clause THE SYSTEM SHALL list it as
  an orphan spec with the reason.
- **C-4.3** *(superseded-by C-4.14 C-4.15)* — WHEN a spec names a superseded clause THE SYSTEM
  SHALL report it as redirected and SHALL NOT credit coverage to the successor.
- **C-4.14** *(supersedes C-4.3)* — WHEN a spec names a superseded clause THE SYSTEM SHALL
  report it as redirected, naming the clauses that reference now resolves to.
- **C-4.15** *(supersedes C-4.3)* — WHEN a spec names a superseded clause THE SYSTEM SHALL
  leave the successor uncovered until a spec of its own proves it.
- **C-4.4** — WHEN a clause is draft THE SYSTEM SHALL exempt it from coverage and report it
  separately.
- **C-4.5** *(superseded-by C-4.13)* — WHEN asked what is left to implement THE SYSTEM SHALL
  place every live clause in exactly one of unspecified, red, unrun or done.
  - note: found by running this frame on itself — with only these four buckets, `todo`
    answered "nothing left" for a clause whose proof was stale, while `drift` said the
    contract was out of sync. Replaced rather than edited, so this reference still resolves.
- **C-4.6** — WHEN a clause is unspecified THE SYSTEM SHALL include its normative text, and
  for a red clause the failing run commands, so the answer is actionable.
- **C-4.7** — WHEN a spec pin differs from its clause's current version THE SYSTEM SHALL
  report spec drift.
- **C-4.8** — WHEN a passing result was earned under an older clause version THE SYSTEM
  SHALL report a stale proof.
- **C-4.9** — WHEN specs carry no pins THE SYSTEM SHALL treat that as missing
  instrumentation and not as divergence.
- **C-4.10** — WHEN drift is requested THE SYSTEM SHALL report missing specs and extra
  specs in the same answer.
- **C-4.11** — WHEN a report is rendered as text THE SYSTEM SHALL show the counts and every
  non-empty finding section.
- **C-4.12** — WHEN asked what is left to implement THE SYSTEM SHALL also list draft clauses
  as backlog, so a requirement that is written down but not yet owed a proof is still
  visible in the answer.
- **C-4.13** *(supersedes C-4.5; superseded-by C-4.16 C-4.17)* — WHEN asked what is left to
  implement THE SYSTEM SHALL place every live clause in exactly one of unspecified, red, unrun,
  stale or done, and SHALL count a stale clause as remaining work.
- **C-4.16** *(supersedes C-4.13)* — WHEN asked what is left to implement THE SYSTEM SHALL place
  every live clause in exactly one of unspecified, red, unrun, stale or done.
- **C-4.17** *(supersedes C-4.13)* — WHEN a clause's specs pass only against an older wording THE
  SYSTEM SHALL count that clause as remaining work.

## C-5 — The contract in the graph

- **C-5.1** — WHEN a pinned contract is compiled THE SYSTEM SHALL emit one clause node per
  clause under the spec node, labelled with its own version and status.
- **C-5.2** — WHEN a clause supersedes another THE SYSTEM SHALL emit a successor to
  predecessor edge in canonical sorted order.
- **C-5.3** — WHEN a contract is attached THE SYSTEM SHALL point each spec's validates edge
  at its clause rather than at the whole spec document.
- **C-5.4** — WHEN a spec names a clause outside the contract THE SYSTEM SHALL refuse to
  compile.
- **C-5.5** — WHEN no contract is attached THE SYSTEM SHALL emit the byte-identical v3.1
  command list.
- **C-5.6** — WHEN a contract is attached but not pinned THE SYSTEM SHALL emit no clause
  nodes and no clause labels.
- **C-5.7** — WHEN the same plan is compiled against an existing graph THE SYSTEM SHALL not
  create the clause nodes a second time.
- **C-5.8** — WHEN the contract-bound gate runs THE SYSTEM SHALL fail closed on uncovered
  live clauses and on orphan specs, exempting drafts.
- **C-5.9** — WHEN any clause text or status changes THE SYSTEM SHALL change the gate's
  artifact hash.
- **C-5.11** — WHEN the compiled graph is executed against a REAL `bd` THE SYSTEM SHALL have
  its clause nodes materialize with their own version labels and its supersede and
  clause-rooted validates edges accepted by bd's native typed-edge API.
  - note: command SHAPE is not acceptance — v3.1 shipped `bd related`, a command bd does not
    have, and every fake-based test passed. This clause exists so that class cannot repeat.
  - tags: slow, integration
- **C-5.10** *(superseded-by C-5.3)* — WHEN scenarios are compiled THE SYSTEM SHALL point
  each spec's validates edge at the spec document.
  - note: this was the v3.1 requirement, retro-documented so the change is auditable. It is
    superseded, not deleted — a reference to C-5.10 still resolves, forward to C-5.3.

## C-6 — Migration and file hygiene

- **C-6.1** — WHEN an existing spec.md is imported THE SYSTEM SHALL preserve its EARS ids
  verbatim so references already written keep resolving.
- **C-6.2** — WHEN a contract file contains no clauses THE SYSTEM SHALL reject it rather
  than report an empty green contract.
- **C-6.3** — WHEN a clause status changes without a text change THE SYSTEM SHALL move the
  registry version.

## C-7 — The frame judging its own authors

- **C-7.1** — WHEN a clause states more than one SHALL obligation THE SYSTEM SHALL report it
  as not atomic.
- **C-7.2** — WHEN a clause joins two obligations with "and shall" THE SYSTEM SHALL report it
  as conjoined.
- **C-7.3** — WHEN a clause uses unprovable wording such as "properly" or "as needed" THE
  SYSTEM SHALL report it as vague.
- **C-7.4** — WHEN two live clauses carry identical wording THE SYSTEM SHALL report the later
  one as a duplicate rather than as coverage.
- **C-7.5** — WHEN a clause is superseded or withdrawn THE SYSTEM SHALL exempt its wording
  from the quality pass.
- **C-7.6** — WHEN wording findings exist THE SYSTEM SHALL keep them advisory unless the
  caller asks for a strict gate.
- **C-7.7** — WHEN a clause carries a multi-line note THE SYSTEM SHALL keep that note out of
  the normative text and out of the clause version.
- **C-7.8** — WHEN this frame's own contract is checked THE SYSTEM SHALL find it free of both
  structural issues and wording findings.
- **C-7.9** — WHEN a clause states an obligation with "should", "may" or "can" THE SYSTEM
  SHALL report it as a weak modal.
- **C-7.10** — WHEN a clause joins alternatives with "and/or" THE SYSTEM SHALL report the
  obligation as undecidable.
- **C-7.11** — WHEN a clause states a passive obligation that names no actor THE SYSTEM SHALL
  report it as an ambiguous passive.
- **C-7.12** — WHEN a clause carries a "TBD" or "TODO" placeholder THE SYSTEM SHALL report
  it as incomplete.
  - note: the markers are quoted because this clause is a mention, not a use — the same
    discipline the linter applies to every other rule that names its own trigger words.
- **C-7.13** — WHEN a clause prescribes a mechanism with a "by ...ing" construction THE SYSTEM
  SHALL report that it dictates implementation rather than behaviour.
- **C-7.14** — WHEN a clause states an unquantified quality such as "as fast as possible" THE
  SYSTEM SHALL report it as unverifiable.
- **C-7.15** — WHEN the quality rules are exercised against a known-bad contract THE SYSTEM
  SHALL produce at least one finding for every rule code it defines.
  - note: guards against a dead rule — a check that can never fire is decoration, and a
    linter nobody sees fire is one nobody trusts.
  - note: the rules must hold on the file that states them, or they are decoration.
