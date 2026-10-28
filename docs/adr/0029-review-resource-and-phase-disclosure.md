# ADR-0029: Disclose reviewer resources and distinguish pending execution

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
Status: accepted after Astra calibration diagnostic 8.

## Context
The candidate passed independent fail-before/pass-after scoring. Native audit remained
INCOMPLETE for real semantic gaps, execution errors and exhausted tests. Generation had
already consumed three of twelve test runs. Two clauses with one bound command each
need ten more runs for one valid and one violation per clause, or twelve for two valid
controls. Nine remained. The reviewer did not receive these limits.

## Decision
Expose the remaining shared calls/tests and per-clause bound command counts. For n
commands on a clause, baseline + one valid + one violation costs 3n+2 runs; baseline +
two valid + one violation costs 4n+2. These are planning counts assuming all controls
run, including two isolated activation runs per violation; early inconclusive outcomes
can consume fewer. Include metadata in the unchanged context limit and retain the
single-call review protocol. Grant no extra resources and drop no obligations.

Review precedes native challenge execution. Instruct reviewers not to claim future
execution as observed or treat its pending phase alone as a semantic gap. Real gaps
stay declared. Native policy still rejects missing or unsuccessful execution; no old
known_gaps field is rewritten or interpreted by parsing prose.

## Consequences
The independent PASS is bounded benchmark evidence, not a completeness proof: its
upstream coverage and score were 2/3, and the native review identified unsupported
representations and assumptions. No historical results are relabelled.
