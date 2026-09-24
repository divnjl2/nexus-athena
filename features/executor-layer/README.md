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

# the lanes are the operator's and are never touched: a model whose tool-call shape the
# lane's parser refuses is absorbed by a relay in front of the gateway
python athena.py relay --port 8414                 # then point an executor at it:
python athena.py dispatch <contract> --front <plan> --task T1.1 --executor openhands \
    --base-url http://127.0.0.1:8414/v1 --iterations 3 --text

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
| local-27b through `athena dispatch`, incl. `--iterations 3` with checkpoints | 8 | **2 landed, green** | first landing: one Read, one Edit at 30 turns. Three iterations at 20 turns: 3, 4 and 9 Reads, one ContextWindowExceeded, no edit. With the spec's own test source in the packet and 30 turns: iteration 3 of 3 landed a correct cap (sorted by lines, twelve shown, "(8 more)") and the spec went green; the two failed iterations left checkpoints the third one continued from. `athena metrics`: landed 0.25, green 0.25, mean 6 min per attempt Earlier in the same series: the whole T5.1 packet was over budget (112k chars: refused, as C-1.4 says); on T5.2 the worker read a memorised path 28 times; with the root named absolutely and the task sliced to one clause and one file it did one Read, one Edit, and the spec went green (9.5 min, 86k in / 13k out tokens) |
| openhands, 27b, terminal tool | 1 | 0 | bash spoken to PowerShell, stuck detector |
| openhands, 27b, guessed tool calling | 1 | 0 | `{"function": ...}` text, hermes parser KeyError (C-2.5) |
| openhands, 27b, native tools | 3 | 0 | context window exceeded once; then the condenser summary lost the task ("the user sent a greeting") |
| openhands, 27b, `--iterations 3` with checkpoints, 12 turns each | 3 | 0 | the loop worked (three fresh contexts, three records, the checkpoint carried); the model spent all 31 actions on glob, grep and view and never attempted an edit. With this model OpenHands explores; it does not implement |
| openhands, 27b, through the relay: implementer prompt, inlined file, test source, red status in the packet, thinking off (vLLM #42021) | 4 runs × 3 iterations | edits landed in 3 of 3 iterations of one run, 0 green; the thinking-off run alone: 27 actions of view, glob and grep, no edit | the red status in the packet turned the explorer into an editor: `str_replace` in every iteration, the checkpoint carried, but the cap went into `owners_for` instead of the context line and the spec stayed red. The OpenHands docs say it themselves: what remains is model capability; they recommend Qwen3.6-35B-A3B and 32k+ context |
| local-27b on a second, different task: C-4.4 per-task metrics, three iterations, 30 turns | 3 | landed 3 of 3, 0 green | the grouping logic was right in iteration 1; the render never got its lines, and the same edit broke the per-executor mean that a sibling spec proves — invisible to a verdict that ran only the task's own check. Two clauses came out of it: C-2.6 (the blast radius is run) and C-2.7 (an edited spec file is never green). Finished by Claude, as ADR-0007 says after three iterations |
| claude (subscription) from inside a Claude Code session | 1 | 0 | `403 Request not allowed` (nested auth), not a pipeline fault |

Every failure was reported with its cause by the verdict, none by the executor. What each
attempt changed in the frame is a clause or a default: C-2.5, no terminal for OpenHands,
native tools on, the input cap and condenser, the absolute root in the packet, tree-kill on
timeout, task slicing to one clause per dispatch. The recipe that made a 27B model on a 30k
window land a green edit through Claude Code: **one clause, one spec, one file per task;
the file inlined; the root named absolutely; output cap above 2048; the verdict, not the
worker, runs the spec.** OpenHands with the same model has not landed one yet. The numbers
to decide with are in `athena metrics`.

## Measured on 2026-09-24, evening: vanilla weights through pi (C-3.6), the same packets

The operator put vanilla Qwen on the lanes (qwen3.8-27b on :8000, qwen3.5-9b on :8001); pi in
print mode became an executor; the 13 tasks of the refinery layer and the ceiling were rerun
from the commits where their specs were red. Per (task, executor), iterations to green:

| task | class | pi-9b | pi-27b medium | pi-27b low | morning: distillates via Claude Code |
|---|---|---|---|---|---|
| C-2.1 admit | new pure fn | green@1, 40 s | green@2 | - | 9b green@1; 27b green then hung 900 s |
| C-2.3 first_failure | new pure fn | green@1, 106 s | green@1, 580 s | - | 9b green@3 |
| C-2.5 record, bd return | new pure fns | green@1, 241 s | red x1 | - | Claude after 3 red |
| C-2.6 merge metrics | new pure fn | green@1, 279 s | red x2 | - | Claude after 3 red |
| C-1.2 junit skip | 4-line edit | green@1, 172 s | - | - | 9b green@1 |
| C-1.3 per-command skip | ~15-line edit | green@1, 123 s | - | - | Claude after 7 red |
| T7.1 bench module | new module, 154 lines | green@1, 223 s | red x3 | - | - |
| T7.3 queue module | new module, 56 lines | green@1, 236 s | (no record) | - | - |
| C-1.1 skip in the verdict | edit in a 20k module | red x3 | - | - | Claude after 12 red |
| C-2.2 rebase, real git | integration | red x3 | red x3 | red x3 | Claude after 3 red |
| C-2.4 fast-forward | integration | red x3 | running | red x3 | Claude |
| T7.2 witness | threads inside a 2,400-line module | red x3 | red x6 | red x3 | Claude |
| T7.4 bench command | two files | red x3 | red x3 | red x3 | Claude |

`reasoning_effort` on the 27B, one coding prompt on the lane itself: default (xhigh) 214 s,
6,000 tokens of reasoning, no answer; low 13 s; medium 46 s; "high" rejected with a 400.
pi sends the effort only when `--thinking` is given, so the executors name it (27b low,
9b medium).

Reading: the envelope of a local worker today is one goal, one file, one spec, up to
~150 lines of new code or ~15 lines of edit in a known place, checked by a pure test. The
9B fills that envelope first time; the 27B fills it slower and does not reach past it at
either effort. Past the envelope — concurrency inside a large module, two-file wiring,
integration with real git — both are red after three iterations and Claude finishes
(ADR-0007). The 27B's place is `athena locate` (reading, not editing) and low-effort text.

Two harness levers measured after that, on the 9B:
- **hashline** (C-3.7, anchored read/replace instead of str_replace, files left out of the
  packet): C-1.1 landed a sane parser where str_replace had left syntax errors, but not the
  second half (the verdict wiring) and broke sibling specs; C-1.3, green first time with the
  inlined packet, went red twice without it; T7.2 nothing. At this model size the failures
  are semantic, not format: hashline stays an option, default off.
- **strict tool calling** (C-6.7, the relay marks tools strict; the lane's grammar applies):
  the smoke went read -> edit -> DONE in two clean calls where the plain run had fumbled a
  `replacement_lines` argument three times. Default for the next batch.
