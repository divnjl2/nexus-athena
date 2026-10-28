# ADR-0026: Disclose remaining execution budgets to generation

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
Status: accepted after the frozen subscription benchmark and diagnostic attempts 1–6.

## Context
The model was never told its call budget. The GPT-6-Sol calibration diagnostic spent
ten calls reading before submitting on the last generation call. This observation
does not establish causality or a quality improvement, but exposes missing operator
information necessary for planning bounded work.

## Decision
Before each attempted completion, attach trusted execution_budget metadata to the
latest user input: remaining generation calls including that request, reserved review
calls, remaining shared test runs, and the output-token acceptance limit. Preserve this
metadata in the transcript and count it against the existing context limit. Charge the
actual call exactly as before. A model cannot grant itself a larger budget in its reply.

## Consequences
The review reservation remains unavailable to generation. No retries, spending caps,
test exemptions or changes to native trust acceptance are introduced. In particular,
the subscription CLI output-token check is an observed acceptance limit, not a cap on
server spending. New model performance requires a separately frozen study; old results
and diagnostic INCOMPLETE outcomes remain unchanged.
