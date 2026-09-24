# The executor layer, contracting itself

The deferred piece, closed by the frame ([ADR-0006](../../docs/adr/0006-executors-under-the-gate.md)):
work is poured into an executor as a **packet** derived from contract, scenarios and plan; the
executor may be a local lane, an OpenHands run or Claude Code; the **verdict** comes from the
workspace diff and the spec commands, never from the executor's report; every attempt lands
in a **record** that says, per executor, how often the work landed and went green.

```bash
# the packet for one task, to paste into any lane by hand
python athena.py dispatch features/team-layer/contract.md --front features/team-layer/plan.md \
    --task T5.1 --executor none

# the same task poured into a local lane, judged by diff + specs, recorded
python athena.py dispatch features/team-layer/contract.md --front features/team-layer/plan.md \
    --task T5.1 --executor local-27b --workspace <worktree> --text

# OpenHands (SDK, in-process, no Docker) on a local model through the gateway
python athena.py dispatch <contract> --front <plan> --task T1.1 --executor openhands \
    --model openai/qwopus-27b --workspace <worktree> --text

# long work on a small window: fresh-context iterations, a checkpoint (files changed, red
# commands, last words) carried in the packet, optionally appended to the bd task's notes
python athena.py dispatch <contract> --front <plan> --task T1.1 --executor local-27b \
    --iterations 3 --bd --workspace <worktree> --text

python athena.py metrics <contract> --text        # runs to green + per-executor landed/green rates
python athena.py check features/executor-layer/contract.md --front features/executor-layer/plan.md \
    --ledger features/executor-layer/spec_ledger.json --map features/executor-layer/clause_map.json --text
```

The orchestrator's job is the top of the pyramid: write the clauses and the red specs,
dispatch, read the verdicts. Whoever typed the code is judged the same way.

## Measured on 2026-09-23/24 (task: one clause, C-5.7, one file, local qwopus-27b)

| executor | attempts | landed | what the verdict said |
|---|---|---|---|
| local-27b through the lanes bridge | 3 | 0 | ten turns spent on Read; `response exceeded the 2048 output token maximum`; a 15-minute timeout that hung for 30 (pipes inherited by a grandchild) |
| local-27b through `athena dispatch`, then `--iterations 3` with checkpoints | 6 | **1 landed, green** | the landing: one Read, one Edit at 30 turns. The three iterations at 20 turns: 3, 4 and 9 Reads, one ContextWindowExceeded, no edit; the checkpoint carried, the records show iteration 1..3, the verdict named each. The reads are the window killer: the packet now carries the spec's own test source so there is nothing left to read | the whole T5.1 packet was over budget (112k chars: refused, as C-1.4 says); on T5.2 the worker read a memorised path 28 times; with the root named absolutely and the task sliced to one clause and one file it did one Read, one Edit, and the spec went green (9.5 min, 86k in / 13k out tokens) |
| openhands, 27b, terminal tool | 1 | 0 | bash spoken to PowerShell, stuck detector |
| openhands, 27b, guessed tool calling | 1 | 0 | `{"function": ...}` text, hermes parser KeyError (C-2.5) |
| openhands, 27b, native tools | 3 | 0 | context window exceeded once; then the condenser summary lost the task ("the user sent a greeting") |
| claude (subscription) from inside a Claude Code session | 1 | 0 | `403 Request not allowed` (nested auth), not a pipeline fault |

Every failure was reported with its cause by the verdict, none by the executor. What each
attempt changed in the frame is a clause or a default: C-2.5, no terminal for OpenHands,
native tools on, the input cap and condenser, the absolute root in the packet, tree-kill on
timeout, task slicing to one clause per dispatch. The recipe that made a 27B model on a 30k
window land a green edit through Claude Code: **one clause, one spec, one file per task;
the file inlined; the root named absolutely; output cap above 2048; the verdict, not the
worker, runs the spec.** OpenHands with the same model has not landed one yet. The numbers
to decide with are in `athena metrics`.
