# Contract: Athena Evaluation Foundation

> Experimental evidence is separate from the existing acceptance gates. A benchmark
> records outcomes; it cannot redefine what counts as correct.

## C-1 — Frozen task corpus

- **C-1.1** *(superseded-by C-1.4)* — WHEN the pilot corpus is frozen THE SYSTEM SHALL select 36 real tasks with
  two development tasks and one holdout task from each of 12 source repositories by a
  deterministic selection rule.
  - source: design
- **C-1.2** — WHEN the frozen corpus is verified THE SYSTEM SHALL reject a changed task
  input, base commit or independent acceptance material against the pinned manifest.
  - source: design
- **C-1.3** *(superseded-by C-1.5)* — WHEN the source dataset has fewer than 12 repositories with three tasks
  each THE SYSTEM SHALL refuse to produce a smaller corpus silently.
  - source: design
- **C-1.4** *(supersedes C-1.1)* — WHEN the Verified pilot corpus is frozen THE SYSTEM
  SHALL select 40 real tasks with three development tasks and one holdout task from
  each of ten eligible source repositories by a deterministic selection rule.
  - source: audit
- **C-1.5** *(supersedes C-1.3)* — WHEN the Verified source has fewer than ten
  repositories with four tasks each THE SYSTEM SHALL refuse to produce a smaller
  corpus silently.
  - source: audit

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
- **C-2.4** — BEFORE optimizer evaluation WHEN baseline is reported THE SYSTEM SHALL
  require both original configurations on every frozen task without requiring an
  optimizer result.
  - source: review
- **C-2.5** — WHEN a complete comparison is summarized THE SYSTEM SHALL report
  paired success differences, confidence intervals, discordant tasks and causes
  of failed attempts.
  - source: design
- **C-2.6** *(superseded-by C-2.7)* — WHEN report completeness is calculated THE SYSTEM SHALL reject an
  empty or shrunken replacement for the frozen 36-task pilot corpus.
  - source: review
- **C-2.7** *(supersedes C-2.6)* — WHEN report completeness is calculated THE SYSTEM
  SHALL reject an empty or shrunken replacement for the frozen 40-task Verified
  pilot corpus.
  - source: audit

## C-3 — Isolated candidates

- **C-3.1** — BEFORE an optimizer run THE SYSTEM SHALL plan the Codex and Codex plus
  Athena baseline cells separately from optimizer cells.
  - source: design
- **C-3.2** — WHEN a task-arm attempt starts THE SYSTEM SHALL create a fresh Git
  worktree at the pinned base commit and refuse to reuse an existing attempt.
  - source: design
- **C-3.3** — WHEN workspace paths are constructed THE SYSTEM SHALL reject task and
  repository identifiers that could escape the experiment root.
  - source: design
- **C-3.4** — WHEN Codex trace usage is counted THE SYSTEM SHALL count completed turns,
  including cached input and output tokens, and reject missing usage evidence.
  - source: design
- **C-3.5** — WHEN a candidate is captured THE SYSTEM SHALL preserve a patch including
  new files without treating the candidate as verified by that capture.
  - source: design
- **C-3.6** — WHEN task prompts are built THE SYSTEM SHALL expose only the issue input
  to every arm and keep optimizer instructions out of both baseline arms.
  - source: design
- **C-3.7** — BEFORE an optimizer candidate is run on holdout THE SYSTEM SHALL require
  a frozen instruction fingerprint bound to complete baseline and development reports.
  - source: design

## C-4 — Independent acceptance

- **C-4.1** *(superseded-by C-4.7)* — WHEN an official SWE-bench report is read THE SYSTEM SHALL obtain the
  boolean verdict from the entry keyed by the task instance id.
  - source: review
- **C-4.2** — WHEN a candidate is submitted to SWE-bench THE SYSTEM SHALL bind its
  prediction and run id to the exact task, patch and attempt so cached verdicts
  cannot cross candidates.
  - source: design
- **C-4.3** — WHEN the official harness produces a report THE SYSTEM SHALL preserve
  its bytes and bind its fingerprint and the candidate patch to a gate envelope.
  - source: design
- **C-4.4** — WHEN an attempt record is read THE SYSTEM SHALL reject an altered
  official harness report even if its gate envelope remains unchanged.
  - source: design
- **C-4.5** — WHEN an attempt is recorded THE SYSTEM SHALL first verify its frozen
  source row and independent gate evidence, then create a unique record file.
  - source: design
- **C-4.6** — WHEN the official harness runs THE SYSTEM SHALL use a pinned local
  task snapshot and the compatible pinned harness version, then read the resulting
  per-instance report from that harness's output path.
  - source: audit
- **C-4.7** *(supersedes C-4.1)* — WHEN an official SWE-bench result is read THE
  SYSTEM SHALL use the task-keyed boolean in a per-instance report, or classify an
  empty patch as unresolved only when the pinned v5 harness's single-task summary
  names that task as its sole submitted empty patch without an error.
  - source: audit
