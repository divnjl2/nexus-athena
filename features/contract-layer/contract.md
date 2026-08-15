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
- **C-1.8** — WHEN a clause states its attributes as indented sub-bullets THE SYSTEM SHALL
  read them as the inline marker form, leaving notes out of the normative text.
- **C-1.9** — WHEN a clause carries no normative sentence THE SYSTEM SHALL report it in lint.
- **C-1.10** — WHEN a clause supersedes itself THE SYSTEM SHALL report it in lint.
- **C-1.11** — WHEN a clause is marked superseded but names no successor THE SYSTEM SHALL
  report it in lint.
- **C-1.12** — WHEN a clause is both withdrawn and superseded THE SYSTEM SHALL report it in
  lint, because the reader cannot tell which one holds.
- **C-1.13** — WHEN a clause carries a status the format does not define THE SYSTEM SHALL
  report it in lint rather than treat it as active.
- **C-1.14** — WHEN attributes are written inside the inline marker THE SYSTEM SHALL accept
  every attribute the sub-bullet form accepts, keeping an unrecognised token as a note.

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
- **C-3.18** — WHEN a spec lane is given a single worker THE SYSTEM SHALL run its specs
  strictly one at a time.
  - note: found by the ledger, not by reasoning — S5.11 (real `bd` + Dolt) went red only
    while another bd process ran concurrently, and was green alone. A spec that needs an
    exclusive external resource needs a lane of one.
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
- **C-5.13** — WHEN a plan has a sibling contract file THE SYSTEM SHALL attach it to the plan
  and pin its version, leaving a plan without one unchanged.
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
- **C-6.4** — WHEN a spec.md is imported THE SYSTEM SHALL take only the named criteria
  section, falling back to the whole file when that heading is absent.
- **C-6.5** — WHEN a contract is rendered THE SYSTEM SHALL keep its group headings and tags,
  so the file stays human-editable.

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
- **C-7.16** — WHEN a clause states an obligation with neither a trigger nor a ubiquitous
  "THE SYSTEM SHALL" opening THE SYSTEM SHALL report it as non-conforming.
  - note: guards against a dead rule — a check that can never fire is decoration, and a
    linter nobody sees fire is one nobody trusts.
  - note: the rules must hold on the file that states them, or they are decoration.

## C-8 — The reverse leg: code that no requirement demands

- **C-8.1** — WHEN a coverage report strips its source root off every filename THE SYSTEM
  SHALL still resolve the paths a plan declares.
- **C-8.3** — WHEN two coverage entries share a basename THE SYSTEM SHALL resolve neither,
  rather than guess which one the plan meant.
- **C-8.2** — WHEN the reverse leg reports code no spec exercises THE SYSTEM SHALL separate
  branches inside files this contract claims from code it never claimed.

## C-9 — The per-clause file:line map

- **C-9.1** — WHEN each spec is run alone under coverage THE SYSTEM SHALL attribute the lines
  it executes to the clause that spec proves, deriving the map instead of asking anyone to
  annotate it.
- **C-9.2** — WHEN a file and line are queried THE SYSTEM SHALL name every clause that owns
  that line.
- **C-9.3** — WHEN the map runner builds a command THE SYSTEM SHALL refuse the same shell
  metacharacters the spec runner refuses.
- **C-9.4** — WHEN lines of a claimed file are classified THE SYSTEM SHALL separate lines this
  contract owns from lines only the wider suite reaches.
- **C-9.5** — WHEN one spec produces no coverage data THE SYSTEM SHALL keep the rest of the
  map rather than abandon the collection.
- **C-9.6** — WHEN a map is written THE SYSTEM SHALL pin the contract and scenario versions
  it was built from.
- **C-9.7** — WHEN coverage output is read THE SYSTEM SHALL parse it without importing a
  coverage library into the pure layer.
- **C-9.8** — WHEN the map's pins differ from the current contract or specs THE SYSTEM SHALL
  report the map as stale.
- **C-9.9** — WHEN a live clause has no entry in the map THE SYSTEM SHALL report it as
  unmapped.
- **C-9.10** — WHEN the map holds a clause the contract no longer defines THE SYSTEM SHALL
  report that entry as stale.
- **C-9.11** — WHEN the map is absent or carries a foreign schema THE SYSTEM SHALL fail the
  gate, because "no map" must never read as "nothing to check".
- **C-9.12** — WHEN the freshness gate runs THE SYSTEM SHALL fingerprint the pins and the id
  deltas in its artifact hash.
- **C-9.13** *(superseded-by C-9.15)* — WHEN a file the map covers has changed since the map
  was built THE SYSTEM SHALL report the map as stale, even though the contract and the specs
  did not move.
  - note: right diagnosis, blunt instrument. Whole-file pinning invalidated every clause in
    a file for an edit that moved none of their lines, so on an active file the map could
    never be kept green. Superseded by the per-clause line pin, not deleted — the wrong
    granularity stays on the record.
- **C-9.15** *(supersedes C-9.13)* — WHEN the lines a clause owns no longer hold what they
  held THE SYSTEM SHALL report that clause as drifted, leaving clauses whose lines are
  untouched fresh.
- **C-9.16** — WHEN a clause owns a line its file no longer has THE SYSTEM SHALL count that
  clause as drifted.
- **C-9.17** — WHEN a map is rebuilt incrementally THE SYSTEM SHALL re-derive only the
  drifted and unseen clauses, carrying the rest of the map over unchanged.
- **C-9.14** — WHEN a map carries an earlier schema THE SYSTEM SHALL refuse it rather than
  trust pins it does not carry.

## C-10 — Does a spec prove anything: the deterministic runner and the judge pilot

- **C-10.1** — WHEN mutants are generated THE SYSTEM SHALL mutate the syntax tree and leave
  docstrings alone, so an equivalent mutant cannot masquerade as a survivor.
- **C-10.2** — WHEN a mutant is run THE SYSTEM SHALL use the specs of every clause that owns
  the mutated line.
- **C-10.3** — WHEN the hunt finishes a mutant THE SYSTEM SHALL restore the original source
  and stop at the first spec that goes red.
- **C-10.4** — WHEN the hunt is summarised THE SYSTEM SHALL name the surviving mutants with
  their file and line.
- **C-10.5** — WHEN the judge corpus is built THE SYSTEM SHALL derive its labels from
  mechanical degradations of pairs this repo already proves.
- **C-10.6** — WHEN a spec is bound to a different clause THE SYSTEM SHALL label that pair
  vacuous for the clause it names.
- **C-10.7** — WHEN a refutation carries no executable counterexample THE SYSTEM SHALL
  discard it rather than let it reject a spec.
- **C-10.8** — WHEN a judge is scored THE SYSTEM SHALL decide gate eligibility from the
  thresholds fixed before the run.
- **C-10.9** — WHEN a judge rejects a proving pair THE SYSTEM SHALL count it as a false
  reject, separately from its recall.
- **C-10.10** — WHEN a judge runs THE SYSTEM SHALL record its model id, prompt hash and
  temperature.
- **C-10.11** — WHEN clause text reaches a prompt THE SYSTEM SHALL neutralise instruction
  markers inside it while keeping the requirement readable.
- **C-10.12** — WHEN a judge greenlights a pair the mutation runner calls vacuous THE SYSTEM
  SHALL demote the judge to advisory.
- **C-10.13** — WHEN a spec's source is needed THE SYSTEM SHALL extract that one function
  from its module.
- **C-10.14** — WHEN an unknown degradation is requested THE SYSTEM SHALL refuse it.
- **C-10.15** — WHEN a mutant is reported THE SYSTEM SHALL carry the file and line of the
  break it introduced.
- **C-10.16** — WHEN a mutation run is killed THE SYSTEM SHALL leave the pristine sources on
  disk so a later invocation can restore them.
  - note: not theory — the first real run hit a ten-minute timeout and left a mutated
    `lib/judge.py` in the tree, because a kill takes the process out past `finally`.
- **C-10.17** — WHEN a mutant cap is given THE SYSTEM SHALL stop at it and report what it
  managed to run.
- **C-10.18** — WHEN mutants are run THE SYSTEM SHALL execute them in a mirror of the
  repository, leaving the working tree untouched.
  - note: `finally` lost twice to a timeout. Isolation is the fix that does not depend on
    the dying process cooperating.
