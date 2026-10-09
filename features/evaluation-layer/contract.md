# Contract: Athena Evaluation Foundation

> Experimental evidence is separate from the existing acceptance gates. A benchmark
> records outcomes; it cannot redefine what counts as correct.

## C-1 — Frozen task corpus

- **C-1.1** — WHEN the pilot corpus is frozen THE SYSTEM SHALL select 36 real tasks with
  two development tasks and one holdout task from each of 12 source repositories by a
  deterministic selection rule.
  - source: design
- **C-1.2** — WHEN the frozen corpus is verified THE SYSTEM SHALL reject a changed task
  input, base commit or independent acceptance material against the pinned manifest.
  - source: design
- **C-1.3** — WHEN the source dataset has fewer than 12 repositories with three tasks
  each THE SYSTEM SHALL refuse to produce a smaller corpus silently.
  - source: design

## C-2 — Run evidence and honest summary

- **C-2.1** — WHEN an experiment attempt is loaded THE SYSTEM SHALL reject a changed
  corpus fingerprint, input, base commit or gate artifact, and require the gate verdict
  to bind the task and candidate patch.
  - source: design
- **C-2.2** — WHEN a comparison is summarized THE SYSTEM SHALL count costs of failed
  attempts in the cost per verified success and report missing task-arm cells.
  - source: design
- **C-2.3** — WHEN a pilot report claims a complete comparison THE SYSTEM SHALL require
  all three named configurations on every frozen task.
  - source: design
