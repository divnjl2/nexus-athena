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

Nine clauses, one clause per dispatch, the packet as the executor layer now shapes it
(spec source, red status, closing order, output budget, excerpt). 40 lane attempts:

| task | what | closed by | attempts before it |
|---|---|---|---|
| C-2.1 admit | new pure function | local-9b, iteration 1, 50 s; local-27b also, then hung 900 s | 0 |
| C-2.3 first_failure | pure function | local-9b, iteration 3 | 2 |
| C-1.2 skipped junit node | 4 lines in the runner | local-9b, iteration 1 | 3 (27b, whole file inlined) |
| C-2.5 record + bd return | pure functions | Claude | 3 (9b, cut at a 1024 output cap) |
| C-2.6 merge metrics | pure function | Claude | 3 (9b; one iteration lost an hour to 288 radius processes) |
| C-2.2, C-2.4 rebase, fast-forward | real git through a runner | Claude | 3 (27b wrote `conflicts_from` twice, never `rebase`) |
| C-1.1 skip is red in the verdict | edit in a 20k-char module | Claude | 12 (6 27b, 6 9b; syntax errors, top-of-file inserts) |
| C-1.3 per-command skip | edit in a 21k-char module | Claude | 10 (fanned 3 on 9b, 2x2 on 27b; 27b asked "what would you like help with") |

`athena metrics`: local-9b landed 0.74, green 0.13, mean 8.5 min; local-27b landed 0.29,
green 0.06, mean 8.5 min. Merge: 9b green tasks 3, merged 1, refused check=1 rebase=1.

The refinery's own record of its first three offers, all on the same assembled worktree:

1. **refused at check**, `features/contract-layer/contract.md: spec.run` — the binding guard
   found the new specs' docstrings naming their clause as `C-1.2:` instead of `C-1.2 —`.
   A real defect in the offer, invisible to the task's own specs.
2. **refused at rebase**, "You have unstaged changes" — the check the refinery itself ran had
   rewritten five committed ledgers. A defect in the refinery, fixed: the run's ledger goes
   under `.athena`.
3. **merged**, master fast-forwarded, 5 contracts held, 3 min 29 s.

What each failure changed in the frame: C-1.7 (the order at the end of the packet), the 8192
cap with the budget stated, the packet on stdin (WinError 206 at 32k), C-5.6/C-5.7 (fanned
attempts) and their copies told their own root, the radius batched per module, C-1.8 (the
module excerpt), C-6.5 (the relay on the messages path) and C-6.6 (thinking stays on).
