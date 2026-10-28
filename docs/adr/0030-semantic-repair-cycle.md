# ADR-0030: Issue-grounded semantic repair with a shared resource lineage

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
Status: implementation in progress; the five requested outcomes are not yet complete.

## Context
The previous calibration exposed unsupported literal/internal-state assertions, weak
valid alternatives, a missing repair loop and audit costs greater than remaining
resources. Instructions alone did not attest semantics. A stronger model produced a
candidate accepted by the external benchmark while native trust correctly retained
unresolved gaps and exhausted execution as INCOMPLETE.

## Decision
Implement a separate semantic-cycle protocol while preserving legacy baseline modes.
Derive intent in an issue-only context before proposing implementation. Bind newly
introduced test assertions to that intent and exact issue quotations. These are
reviewer declarations, not proofs that the quotations imply the assertions. Unjustified,
unknown and missing support must remain distinguishable.

Keep every candidate, review and native audit in immutable attempt directories. Repair
feedback comes only from public/native evidence, never the sealed evaluator. A changed
candidate needs fresh independent review; changed requirements retain their old wording
and supersede their IDs. Known gaps and execution errors are not silently removed.

Every phase shares one durable journal. Charge outer model requests and test-tool
attempts before side effects, retain timeout/error/pending charges across restart, and
reserve future review/repair resources. A clause with n bound commands costs
n*(1+valid+violations)+2*violations native audit runs when all controls execute.
Recompute before admission if bindings grow. Insufficiency never authorizes narrower
obligations, fewer required controls or a larger implicit budget.

Journal entries use exclusive creation, file flushing, OS locking and a linked digest.
They protect against accidental resets and concurrent stale coordinators. Hashes do not
authenticate a hostile owner, and deleting a valid journal suffix requires a trusted
external head to detect. Partial records fail closed; process-crash durability does not
claim power-loss durability on every filesystem. Unknown token usage is not zero.

Request and evaluate materially different valid mechanisms/representations where allowed.
Execution witnesses remain typed; semantic validity of a control remains declared.
The final release rule must combine support review and native checks without claiming
universal correctness or completeness.

## Consequences
Before new inference, freeze code, runtimes, model configuration and the already selected
new cohort. Independently grade every immutable candidate only after generation ends.
Report native/independent PASS, FAIL and INCOMPLETE cross-tabulations, withheld-good cases,
all 30 selected cases per arm and cumulative resources. Calibration and engineering
controls are not model-performance evidence. The previous study remains unchanged.
