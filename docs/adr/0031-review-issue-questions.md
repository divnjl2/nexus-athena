# ADR-0031: Review retained issue questions after public generation

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
Status: accepted for the opt-in semantic cycle; semantic judgments remain advisory.

## Context
The first fresh calibration case stopped after one issue-only request because the
passport listed missing example inputs, unspecified tolerance and numerical-range
questions. Some questions can be answered from public base code or shown irrelevant
to a concrete regression witness. Their existence does not establish that no justified
test can be proposed.

## Decision
Keep the initial passport unchanged and allow public generation. A fresh reviewer must
account for every question with RESOLVED, NONBLOCKING or UNRESOLVED, a specific reason,
and exact public issue or base-code evidence for nonblocking/resolved declarations.
Missing answers, invented source quotations and unresolved questions withhold release.
The proposed reference is not authority for answering an issue question.

## Consequences
This adds accountable declarations, not proof of semantic implication. Native execution
and combined release decisions remain separate. Calibration attempts and their resource
use remain archived; this change cannot reclassify an earlier INCOMPLETE result as PASS.
