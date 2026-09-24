# The refinery layer, contracting itself

Two holes the executor layer left in the judge, closed by the frame
([ADR-0008](../../docs/adr/0008-the-refinery-merges-nothing-by-hand.md)): a check that
skipped its test exited zero and was green; a green verdict in a worktree went nowhere until
the orchestrator rebased and merged by hand. Now **a skip is red** in the verdict, in the
junit attribution and in the per-command runner, and **a green workspace reaches the target
only through `athena merge`**: admit on the record, rebase, run every contract, fast-forward.

```bash
# offer a worktree whose task went green; the first failing stage refuses it
python athena.py merge features/refinery-layer/contract.md --front features/refinery-layer/plan.md \
    --task T2.1 --workspace <worktree> --target master --text

# the same, returning the task to bd with the stage and the reason on refusal
python athena.py merge <contract> --front <plan> --task T2.1 --workspace <worktree> --bd --text

# per executor: green dispatches, how many merged, refusals by stage
python athena.py metrics features/refinery-layer/contract.md --text

python athena.py check features/refinery-layer/contract.md --front features/refinery-layer/plan.md \
    --ledger features/refinery-layer/spec_ledger.json --map features/refinery-layer/clause_map.json --text
```

The four stages and what judges each:

| stage | judged by | refusal names |
|---|---|---|
| admit | the task's last line in `.athena/dispatch.jsonl` | what the record says (not green, no record) |
| rebase | `git rebase <target>` exit code, then `--abort` | the conflicting files |
| check | `athena check --run` on every contract in the workspace, specs executed now | the contract and its first cause |
| fast-forward | ancestry, then a compare-and-set on the target ref | that the target cannot be fast-forwarded |

Every offer ends in `.athena/merge.jsonl`. The orchestrator writes clauses and red specs,
dispatches, reads verdicts, offers workspaces. It merges nothing by hand.

## Measured on 2026-09-24 (this layer built by the lanes through the frame)

_(filled from `athena metrics` when the plan closes)_
