# CORE: Athena

> The semantic core. Hand-written, under forty lines, read before anything else. Clauses cite
> it as `see: ../../CORE.md@<fingerprint>`; when this file changes, those clauses go suspect
> until somebody re-reads them (`athena contract refs`). Change it rarely, and on purpose.

## Goal
Show which declared requirements have current evidence, what remains unimplemented or
unassessed, and where requirement, spec and code disagree. Artifact checks are a fast scan;
intent fidelity, check adequacy and code correspondence need distinct, scoped evidence.

## Language
| word | means |
|---|---|
| clause | one numbered obligation in EARS shape; its id is allocated once and never reused |
| spec | an executable check bound to a clause; success is an observation within its checked scope |
| pin | the fingerprint of the wording a spec, or a reference, was written against |
| ledger | recorded execution results and their inputs; a green result is not requirement truth |
| map | observed execution attributed through bound specs; legacy ownership is not semantic correspondence |
| supersede | the only way a requirement changes; the old id keeps resolving forward |
| lesson | a clause whose `source:` is a failure signal; reruns record whether its checks still pass |

## Priorities, in order
1. Honesty. Missing evidence is INCOMPLETE or UNKNOWN; a missing named input is an error.
   PASS is scoped to checked gates; execution, intent, adequacy and correspondence stay distinct.
2. Determinism. The gate holds no model. A judge is advisory until numbers fixed before its
   first run say otherwise.
3. Speed of the three questions. Coverage, todo and drift answer from committed artifacts in
   under a second; the spec lane is seconds, not minutes.
4. Ease of entry. One short document at the root leads to everything else.

## Constraints
- A derived artifact is never edited by hand; a hand-written one is never inferred.
- New behaviour requires a clause and an executable spec; unclaimed code remains visible.
- A requirement that changes is superseded, never edited in place; wrong guesses stay on record.
- A run_cmd is an LLM-hop output: tokenized, never a shell.
- The frame is applied to itself first: every rule here has a clause and a spec in features/.
