# Contract: Athena Refinery Layer (v3.13)

> Two holes the executor layer left in the judge, closed by the frame. A check that skipped
> its test exits zero and was green: a skip is not proof. A green verdict in a worktree went
> nowhere on its own: the orchestrator rebased and merged by hand. The refinery takes an
> offered workspace, admits it on its record, rebases it, runs every contract, fast-forwards
> the target — and refuses at the first stage that fails, with the reason in the record and
> the task back in bd. Ids are allocated once and never reused.

## C-1 — A skip is not proof

- **C-1.1** — WHEN a check exits zero but its output reports skipped tests or no passed test
  THE SYSTEM SHALL judge the check red, with the reason naming the skip.
  - source: review
  - note: `@pytest.mark.skip` on the spec's own test exits 0; the verdict of the executor
    layer called that green.
- **C-1.2** — WHEN the runner's report marks a spec's node as skipped THE SYSTEM SHALL record
  the spec as not passed, with the reason naming the skip.
  - source: review
- **C-1.3** — WHEN a spec is run by its own command and exits zero with output reporting a
  skip or no passed test THE SYSTEM SHALL record the spec as not passed.
  - source: review

## C-2 — The merge queue

- **C-2.1** — WHEN a workspace is offered to the queue THE SYSTEM SHALL admit it only when the
  last record for its task in the workspace's dispatch record is green, and refuse it
  otherwise, saying what the record says.
  - see: ../../docs/adr/0006-executors-under-the-gate.md@0257c4b849eae98c
  - source: review
- **C-2.2** — WHEN an admitted workspace is rebased onto the target branch and the rebase
  stops THE SYSTEM SHALL abort the rebase, refuse the offer and name the conflicting files.
  - source: review
- **C-2.3** — WHEN the rebase lands THE SYSTEM SHALL run the check of every contract in the
  workspace and refuse the offer when any contract fails, naming the contract and its first
  cause.
  - source: review
- **C-2.4** — WHEN every contract holds THE SYSTEM SHALL fast-forward the target branch to the
  workspace head, and refuse when the target cannot be fast-forwarded.
  - source: review
- **C-2.5** — WHEN an offer ends THE SYSTEM SHALL append a merge record with its task,
  executor, stage and reason, and for a refusal emit the command that returns the task to bd
  with that reason.
  - source: review
- **C-2.6** — WHEN metrics are rendered THE SYSTEM SHALL report per executor how many of its
  green dispatches were merged and at which stage the others were refused.
  - source: review
