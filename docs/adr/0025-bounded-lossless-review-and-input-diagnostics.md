# ADR-0025: Lossless bounded review inputs and actionable validation errors

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
Status: accepted in the post-benchmark revision; the frozen baseline study is unchanged.

## Context
The first subscription-backed TDD-Bench study exposed three interface failures.
Django-12858 review was stopped before inference: its source and proposed source were
repeated in an input larger than the declared 160000-character limit. Flask-5014 review
used --maxfail=1; the bounded command parser interpreted it as a test path and returned
a misleading overlay error. Requests-2931 review listed a scenario belonging to another
clause. An exception before the first audit save could also lose charged-budget fields.

## Decision
Represent reference files as lossless difflib.ndiff line arrays. Unchanged lines occur
once; restore mode 1 gives the exact base and mode 2 the exact proposed reference.
Remove the redundant reference field from the copied reviewer proposal. Never truncate
source and never increase the context limit. An over-limit input remains INCOMPLETE.
The reviewer is told how to interpret the format, and that the reference is a hypothesis.

Keep the existing pytest allowlist. Unsupported flags must name themselves and the
allowed flags before execution. Reviewer instructions state that allowlist and exact
scenario-to-clause membership. Persist charged generation and review budgets before
further validation. Preserve a bounded typed exception explanation; errors never export
a prediction. Valid reviews still require native baseline, valid-variant, violation and
independent activation checks.

## Consequences
The running baseline study is unchanged. These repairs require a new method revision;
old failed attempts remain in the original 30-case denominator. A compact representation
does not prove model review quality or semantic validity. Those require separate evidence.
