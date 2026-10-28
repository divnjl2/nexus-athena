# ADR-0018: Test-only prediction patches

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

## Context
The direct generator previously required only a diff header and final newline. That
allowed implementation changes, unsupported metadata or malformed hunks to enter an
evaluation intended to compare regression-test generation. Native proposals already
exported test content only, so this was also an asymmetry between the compared arms.

## Decision
All generation modes now validate the complete final patch against the verified public
base without invoking Git or executing submitted code. Admit bounded same-path Python
test diffs only; reject implementation, configuration, linked paths, renames, binary or
mode-changing payloads, duplicate files and unexplained trailing text. Hunk counts,
positions and removed/context text must match the base exactly. Re-emit canonical diffs
from the reconstructed test contents, leaving public files unchanged.

## Consequences
The original response remains in the transcript. The prediction receipt hashes the
canonical evaluator payload. Invalid submissions consume the attempted model turn and
receive a diagnostic; they cannot publish a prediction. This structural boundary does
not establish semantic relevance or nonvacuity; external evaluation and trust challenges
still supply that evidence.
