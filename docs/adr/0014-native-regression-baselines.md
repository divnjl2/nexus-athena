# ADR-0014: Native regression baselines use public agent proposals

- Status: accepted
- Date: 2026-10-25
- Deciders: implementation within the operator-approved benchmark work
- Cited by: features/tdd-benchmark C-7.1 and C-7.2

## Context
A useful regression test should fail on old buggy code. Requiring a green native gate on
that version would reject exactly the desired test. Supplying the evaluator's gold fix to
the generator would instead leak the answer key and invalidate the comparison.

## Decision
The Athena arm proposes a contract, executable scenarios, test files and its own reference
implementation using only the public issue and base code. Execute real contract parsing,
scenario pinning, spec-runner ledger generation and check folding. All code execution
uses the offline pytest bridge and the same per-arm test budget; nothing executes on the
host. Keep this result explicitly scoped to the native contract fast lane, with the
reverse leg absent. Retain framework source fingerprints for the check.

Both direct and Athena arms have the same run tool, including optional proposed public
implementation edits. Exact-anchor replacements avoid spending model output on entire
large source files. Configuration, tests and unknown files cannot be reference overlays.

Generate the independent evaluator patch only from submitted test-file differences.
Never include the reference implementation. Keep the public base snapshot unchanged.

## Consequences
A green test on an agent's own reference is not independent semantic validation. A model
can propose a wrong reference and tests that agree with it. The external old/gold-code
evaluation remains necessary, and native trust still needs reviewer-owned alternatives
and activated semantic violations. A scripted engineering control is not model quality.
No green baseline here excludes memorized training data; gold_used=false describes
runtime input separation, not the model's training history.
