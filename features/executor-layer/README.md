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

python athena.py metrics <contract> --text        # runs to green + per-executor landed/green rates
python athena.py check features/executor-layer/contract.md --front features/executor-layer/plan.md \
    --ledger features/executor-layer/spec_ledger.json --map features/executor-layer/clause_map.json --text
```

The orchestrator's job is the top of the pyramid: write the clauses and the red specs,
dispatch, read the verdicts. Whoever typed the code is judged the same way.
