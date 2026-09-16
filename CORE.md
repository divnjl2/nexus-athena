# CORE: Athena

> The semantic core. Hand-written, under forty lines, read before anything else. Clauses cite
> it as `see: ../../CORE.md@<fingerprint>`; when this file changes, those clauses go suspect
> until somebody re-reads them (`athena contract refs`). Change it rarely, and on purpose.

## Goal
"Is it done?" is a linear scan of committed artifacts, never a re-read of the code. Three
questions: which requirements have no spec, what is left to build, where did requirement,
spec and code part ways.

## Language
| word | means |
|---|---|
| clause | one numbered obligation in EARS shape; its id is allocated once and never reused |
| spec | the executable command bound to a clause by id; exit 0 means the clause holds |
| pin | the fingerprint of the wording a spec, or a reference, was written against |
| ledger | which specs were green, and when |
| map | which lines of which files each clause owns, derived from coverage |
| supersede | the only way a requirement changes; the old id keeps resolving forward |
| lesson | a clause whose `source:` is a failure signal; `athena lessons rerun` keeps it |

## Priorities, in order
1. Honesty. Silence is never proof: a leg with no evidence is INCOMPLETE, not PASS; a named
   input that is missing is an error, not a choice.
2. Determinism. The gate holds no model. A judge is advisory until numbers fixed before its
   first run say otherwise.
3. Speed of the three questions. Coverage, todo and drift answer from committed artifacts in
   under a second; the spec lane is seconds, not minutes.
4. Ease of entry. One short document at the root leads to everything else.

## Constraints
- A derived artifact is never edited by hand; a hand-written one is never inferred.
- New behaviour is a clause and an executable spec, or it does not exist.
- A requirement that changes is superseded, never edited in place; wrong guesses stay on record.
- A run_cmd is an LLM-hop output: tokenized, never a shell.
- The frame is applied to itself first: every rule here has a clause and a spec in features/.
