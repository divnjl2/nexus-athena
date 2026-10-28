# ADR-0023: Explicit Git new-file metadata

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
- Status: accepted

## Context
A scripted new-file calibration control exposed a real exporter defect. The canonical
patch contained diff --git and --- /dev/null but omitted new-file mode metadata. In the
official evaluator Git interpreted it as a rename from dev/null, failed to apply it and
the next harness step tried to parse a missing file as Python. The evaluator returned
ERROR, despite unit tests and the modified-existing-file protocol control being green.

## Decision
Emit new file mode 100644 for an added test file, before its unified headers. Do not emit
creation metadata for an existing-file edit. All generation modes use the canonical
exporter, so legacy final patches missing this metadata are normalized before prediction
publication. Candidate test semantics and the frozen cohort remain unchanged.

## Consequences
Preserve the original error, initial-script replay and corrected control as separate
runs. The live control uses a local scripted HTTP provider and a new always-green test
file in a calibration instance. The expected corrected outcome is a real PASS before and
after, with strict FAIL/score zero for vacuity. It is a protocol control, never a model
score. Official harness source stays frozen; Git operations occur only through its
previously authorized isolated scripts and functions.
