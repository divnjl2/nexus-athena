# ADR-0008: A green workspace reaches the target only through the refinery

- Status: accepted
- Date: 2026-09-24
- Deciders: operator
- Cited by: features/refinery-layer C-2.1, C-2.4

## Context

The executor layer judged an executor's work by diff and specs and stopped there: a green
verdict sat in a worktree until the orchestrator rebased, re-ran what it remembered to
re-run and merged by hand. That step was the one Gas Town names the Refinery and the one
we did with the most expensive model in the loop and no record. Two things were measured
before this decision: a lane's green edit that broke a sibling spec (C-2.6 of the executor
layer now runs the blast radius), and a check that exited zero on a skipped test (C-1 of
the refinery layer). Both say the same thing: what is merged must be judged again, in the
workspace, on everything.

## Decision

`athena merge` is the only path from a workspace to the target branch. It admits an offer
on the task's last dispatch record, rebases the workspace onto the target and aborts on
conflict, runs the check of every contract in the workspace with the specs executed now
(never the committed ledger), and fast-forwards the target with a compare-and-set on the
ref. The first stage that fails refuses the offer; every offer ends in a merge record; a
refusal emits the bd command that returns the task with the stage and the reason. The
orchestrator does not merge by hand, and a merge commit is never made: history on the
target is the executors' rebased commits.

## Consequences

- `athena metrics` reports per executor how many of its green dispatches were merged and
  at which stage the rest were refused: the number that says whether a lane's green is
  worth anything past its own spec.
- A skipped test is red in the verdict, in the junit attribution and in the per-command
  runner; a spec cannot be silenced into green.
- The target may be checked out in another worktree: the fast-forward moves the ref, that
  worktree's files stay where they were until it is updated. The merge says so in its record.
- A stalled executor is still ended by the timeout only; a witness on output needs the
  worker's streaming format first and is out of this layer's scope.
