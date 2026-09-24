# Contract: Athena Executor Layer (v3.12)

> The deferred piece, closed by the frame: work is poured into an executor as a PACKET
> derived from the contract, the scenarios and the plan; the executor may be a local lane, an
> OpenHands run or Claude Code; and the verdict comes from the workspace diff and the spec
> commands, never from the executor's report. The orchestrator writes clauses and reviews
> verdicts; it does not type the code. Ids are allocated once and never reused.

## C-1 — The work packet

- **C-1.1** — WHEN a task is dispatched THE SYSTEM SHALL build its packet from the contract,
  the scenarios and the plan: the clauses the task's specs verify, their run commands and the
  task's files.
  - see: ../../docs/adr/0006-executors-under-the-gate.md@0257c4b849eae98c
  - source: review
- **C-1.2** — WHEN a packet is rendered THE SYSTEM SHALL state the done criterion as the spec
  commands and tell the executor that its own report does not count.
- **C-1.3** — WHEN a task names a spec the scenarios do not hold THE SYSTEM SHALL refuse to
  build the packet.
- **C-1.4** — WHEN a packet exceeds the executor's context budget THE SYSTEM SHALL say so
  rather than shorten the clauses silently.
- **C-1.5** — WHEN a spec is a test node whose source can be read THE SYSTEM SHALL carry that
  test's source in the packet.
  - source: ledger
  - note: the three iterations that landed nothing spent 3, 4 and 9 turns on Read, one of
    them into the context ceiling; the one that landed did a single Read. With the spec's
    own source in the packet there is nothing left to go and read.
- **C-1.6** — WHEN a packet is about to be executed THE SYSTEM SHALL state each spec's current
  verdict in it, a red one with its output tail.
  - source: ledger
  - note: given the implementer prompt, the file and the test, the 27B viewed the file once
    and called finish: "already complete and correct". Nothing in the packet said the spec
    was red at that moment. Now the packet does.
- **C-1.7** — WHEN a packet is closed THE SYSTEM SHALL end it, after every inlined file and
  the spec status, with the order to act: the first action is an edit of a named file, and
  there is no user to ask.
  - source: ledger
  - note: on a 24k-char packet whose last 270 lines were the inlined lib/dispatch.py, the
    27B read the file and answered "Would you like me to: 1. Continue reading the file…":
    two iterations, no edit. The last thing in the window decides what the model thinks it
    is doing; the last thing is now the order.
- **C-1.8** — WHEN an inlined file is longer than the excerpt threshold THE SYSTEM SHALL carry
  its header, in full the definitions the task's specs import from it, only the signatures
  of the rest, and the imported names it does not define yet, said plainly.
  - source: ledger
  - note: the whole of a 20k-char module in the packet was eleven attempts by two lanes
    without a green: the models read it, summarised it, asked what to do, or rewrote what
    was there. The question is not how much the window holds but what of the module is the
    task's; the spec's imports say exactly that.

## C-2 — The verdict

- **C-2.1** — WHEN an executor returns THE SYSTEM SHALL decide from the workspace diff and the
  spec commands and ignore the executor's report.
  - source: ledger
  - note: measured twice on the local 27b lane: `ok: true`, eight files read, nothing
    changed. The report of an executor is a claim; the diff and the exit code are evidence.
- **C-2.2** — WHEN nothing changed in the workspace THE SYSTEM SHALL record the attempt as not
  landed.
- **C-2.3** — WHEN a spec command is red after the run THE SYSTEM SHALL record the attempt as
  red with that command's output tail.
- **C-2.4** — WHEN the run changed a derived artifact or a hand-written contract THE SYSTEM
  SHALL flag the attempt for review.
- **C-2.5** — WHEN the executor's claim carries a tool call as plain text THE SYSTEM SHALL
  name a tool-parser mismatch in the reason.
- **C-2.6** — WHEN a run changed a file THE SYSTEM SHALL also run the specs of every clause
  whose map owns lines in that file before deciding.
  - source: ledger
  - note: the lane implemented C-4.4's grouping correctly and, in the same edit, broke the
    per-executor mean that C-4.2 proves. The task's own check was the only one run, so the
    regression was invisible to the verdict. The blast radius the pre-edit hook already
    computes is now part of the verdict.
- **C-2.7** — WHEN a run changed the file that holds a spec's test THE SYSTEM SHALL flag the
  attempt for review and refuse to call it green.
  - source: review
  - note: an executor with write access can make a spec pass by editing the spec. The
    verdict flagged contracts and derived files; the tests were the remaining door.
  - source: incident
  - note: the 27b lane through OpenHands answered the tool schema with
    `{"function": "glob", "parameter": {...}}`; vLLM's hermes parser raised KeyError 'name'
    and handed the text back as content. The run ended after 160 tokens with a claim and no
    edit. A silent failure with a known signature deserves its name.

## C-3 — Executors

- **C-3.1** — WHEN an executor is named THE SYSTEM SHALL resolve it from a registry holding
  the local lanes, OpenHands and Claude Code, and refuse an unknown name.
- **C-3.2** — WHEN the local-lane executor is prepared THE SYSTEM SHALL produce a command that
  grants only read and edit tools, caps the turns and points at the local gateway.
  - note: the 27b lane failed silently until two things changed: the files it needed were
    inlined so it spent no turns on Read, and its output cap rose from 2048 tokens, which
    had cut every multi-line Edit mid-call.
- **C-3.3** — WHEN the OpenHands executor is prepared THE SYSTEM SHALL produce a run whose
  workspace is the repository and whose model is the one named.
- **C-3.4** — WHEN an executor is not installed THE SYSTEM SHALL report it unavailable instead
  of failing the dispatch with a traceback.
- **C-3.5** — WHEN the OpenHands executor is prepared THE SYSTEM SHALL give it an
  implementer's prompt shaped like the packet, unless the stock prompt is asked for.
  - source: ledger
  - note: with the SDK's explorer prompt the 27B spent every turn on glob and view across
    eight dispatches and never attempted an edit; the packet already holds what an explorer
    would go looking for.
- **C-3.6** — WHEN a pi executor is chosen THE SYSTEM SHALL run pi in print mode with its four
  tools and no session, extensions, skills or context files, the lane named as its provider,
  the packet on stdin and the order as the prompt, and read the claim, the tokens and any
  error from its JSON events.
  - source: review
  - note: measured before the clause: the harness moved the same weights more than the
    packet did. Through pi the vanilla 27B edited a file in three turns on the first try and
    the vanilla 9B in two; pi's system prompt is ~200 tokens against Claude Code's thousands,
    and it speaks the lane's OpenAI shape directly, no gateway translation in between.
- **C-3.7** — WHEN a pi executor is run with hashline THE SYSTEM SHALL load the hashline
  extension, offer its anchored read and edit tools in place of the string-replace edit,
  leave the task's files out of the packet and name them for the read tool.
  - source: review
  - note: both lanes broke on edits inside large files — inserts at the top, syntax errors,
    duplicated functions — while new modules landed first time. Bölük's benchmark (16
    models, 180 tasks): anchored line edits beat patch for 14 of 16 models, the weakest
    gaining most; a stale anchor refuses the edit instead of missing silently.

## C-4 — The record

- **C-4.1** — WHEN a dispatch completes THE SYSTEM SHALL append one record with the executor,
  the task, whether it landed, whether it was green, the duration and the tokens.
- **C-4.2** — WHEN dispatch metrics are requested THE SYSTEM SHALL report per executor the
  attempts, the landed rate and the green rate.
- **C-4.3** — WHEN a packet is requested without an executor THE SYSTEM SHALL print it and
  record nothing.
- **C-4.4** — WHEN dispatch metrics are requested THE SYSTEM SHALL report per task the number
  of iterations it took to reach green or the number spent short of it.
  - see: ../../docs/adr/0007-qwopus-executes-through-claude-code.md@c0ff469190eeaf07
  - source: design

## C-5 — Iterations with checkpoints, so a small window is enough

- **C-5.1** — WHEN an iteration ends short of green THE SYSTEM SHALL write a checkpoint naming
  the files changed, the red commands and the executor's last words.
  - source: review
  - note: the operator's call: keep the 30k window and six slots for multitasking, and let
    long work cross iterations through checkpoints instead of a bigger context.
- **C-5.2** — WHEN the next iteration starts THE SYSTEM SHALL carry the checkpoint into the
  packet and give the executor a fresh context.
- **C-5.3** — WHEN an iteration passes THE SYSTEM SHALL stop the loop and record the number of
  iterations it took.
- **C-5.4** — WHEN a checkpoint is written THE SYSTEM SHALL emit the command that appends it
  to the task's notes in the task graph.
- **C-5.5** — WHEN the iteration budget is spent short of green THE SYSTEM SHALL keep the last
  checkpoint and report the dispatch red.
- **C-5.6** — WHEN a dispatch is fanned out THE SYSTEM SHALL run the attempts of one iteration
  concurrently, each in its own copy of the workspace, and take the first green verdict as
  the iteration's result.
  - source: review
  - note: reasoning models in agentic loops overthink — analysis paralysis, rogue actions,
    premature disengagement — and picking the lower-overthinking trajectory out of several
    gave about +30% on SWE tasks at -43% cost (arXiv 2502.08235). The lanes think before
    every action; a second attempt costs a slot, not a subscription.
- **C-5.7** — WHEN no fanned attempt is green THE SYSTEM SHALL carry forward the attempt that
  landed with the fewest red checks, the quicker one on a tie, and record every attempt.
  - source: review
- **C-5.8** — WHEN several fanned attempts have landed THE SYSTEM SHALL cluster them by
  behaviour — which checks passed and the normalised patch — keep one representative per
  cluster for review, and choose the largest green cluster, else the largest cluster with the
  most passed checks.
  - source: review
  - note: CodeMonkeys: coverage ceiling 69.8%, random pick 45.8%, real selection 57.4% — the
    gap between coverage and selection is the reserve. Agentless votes over normalised
    patches; Self-MoA says the copies of one model, not a mixture, are what to vote over.

## C-6 — The gateway relay: adapt on the client side, never on the lanes

- **C-6.1** — WHEN a completion carries a tool call as plain text THE SYSTEM SHALL return it
  as a structured tool call with the text before it kept as content.
  - source: incident
  - note: the operator's hard rule is that the inference lanes are not touched. The local
    27b answered OpenHands' schemas in a shape vLLM's hermes parser refused, 73 times in one
    night; a relay in front of the gateway is where the frame absorbs that.
- **C-6.2** — WHEN a completion is already well formed, plain prose, or holds tags nothing
  can parse THE SYSTEM SHALL pass it through unchanged.
- **C-6.3** — WHEN the OpenHands executor is given the relay as its base url THE SYSTEM SHALL
  use it and leave the gateway address as the operator set it.
- **C-6.4** — WHEN a request through the relay carries tools THE SYSTEM SHALL turn the model's
  thinking off for it unless the caller decided otherwise.
  - superseded-by: C-6.6
  - source: review
  - see: https://github.com/vllm-project/vllm/issues/42021
  - note: found by searching before inventing: Qwen3.5 under vLLM's qwen3 reasoning parser
    with thinking on writes its tool calls inside the reasoning in a non-standard shape and
    the tool parser never sees them; `enable_thinking=false` per request is the workaround
    the issue names. Our lane answers with reasoning_content present, so this was our bug.
- **C-6.5** — WHEN a response on the messages path carries a tool call as text THE SYSTEM SHALL
  return it as tool_use blocks with stop_reason tool_use, streamed as the client asked, and a
  local lane may be pointed at the relay.
  - source: ledger
  - note: measured with the excerpted packet and no tools: Qwopus 27B wrote
    `<tool_call><function=Read>...` as text, 8330 output tokens. Behind Claude Code that text
    is a turn with no tool_use, and the worker reports instead of editing. The relay already
    knew the shape on the OpenAI path; Claude Code speaks the Anthropic one.
- **C-6.6** — WHEN a request through the relay carries tools THE SYSTEM SHALL leave the
  model's thinking as the lane has it and turn it off only when the caller asks.
  - supersedes: C-6.4
  - source: review
  - note: the operator's decision: the lanes think; the frame adapts the budget and the
    packet, not the model.
- **C-6.7** — WHEN a request through a strict relay carries function tools THE SYSTEM SHALL mark
  every tool strict so the lane applies its grammar to the call under automatic tool choice,
  and a pi executor may be pointed at that relay by name.
  - source: review
  - note: vLLM's enforce flag defaults to on, but under tool_choice=auto the grammar is
    applied only to tools that set strict; most clients never set it, and a broken call
    shape leaks into the text (the morning's C-2.5). The lane keeps its flags; the relay
    sets the field.

## C-7 — The ceiling: graded tasks a local model in a harness is measured against

- **C-7.1** — WHEN a bench matrix is planned THE SYSTEM SHALL list the runs of the tasks
  across the executors, each executor in its own workspace, and fold the dispatch record
  back into one table per task and executor: the iteration it went green at, attempts,
  landings, seconds and tokens.
  - source: review
  - note: the rung a new module sits on — three pure functions, one file, about a hundred
    lines. The bench loops were shell one-liners until this clause.
- **C-7.2** — WHEN a worker emits nothing for the stall window THE SYSTEM SHALL end its
  process tree well before the timeout and report the iteration as stalled, distinct from
  a timeout.
  - source: ledger
  - note: the rung an edit inside a 2,400-line module sits on. Measured: workers that had
    finished thinking and hung were held to the 900-second timeout, and their orphaned
    requests kept the lane's slots; pi's JSON events make silence measurable.
- **C-7.3** — WHEN `athena next` is asked for a slug THE SYSTEM SHALL take that slug's first
  ready task from bd — lowest priority number first, the earlier created on a tie — claim
  it, and dispatch it with the flags given; with nothing ready it says so.
  - source: review
  - note: the rung a new module plus a CLI command sits on; it is the Gas Town rule "if
    there is work on your hook, run it", with bd as the hook.
- **C-7.4** — WHEN `athena bench` is run THE SYSTEM SHALL execute the planned matrix, each run
  through dispatch in its executor's workspace, and print the table; with `--dry-run` it
  prints the plan and dispatches nothing.
  - source: review
  - note: the rung a change across two files sits on: the module of C-7.1 and the CLI.

## C-8 — The swarm's second source: tests and locations the orchestrator did not write

- **C-8.1** — WHEN candidate reproduction tests are written for a clause THE SYSTEM SHALL keep
  only those that parse, define one test naming the clause and fail on the current code for
  a failure rather than an error or a skip, cluster the rest by normalised source and choose
  the largest cluster's representative.
  - source: review
  - note: the orchestrator writing every red spec by hand is the factory's ceiling; a test
    that fails on the code as it is, chosen by agreement, is the cheapest way to raise the
    verifier's quality (Agentless reproduction tests; CodeMonkeys' selector).
- **C-8.2** — WHEN a clause has no files named THE SYSTEM SHALL build a repo map of Python
  files with their top-level definitions within a character budget, ask the localiser for
  the files, and merge several samples' votes by count then first mention.
  - source: review
  - note: Agentless with better localisation went from 32.0% to 38.3% and empty patches fell
    2.7x; localisation is a lever of its own, and one a 27B is good at without editing.
- **C-8.4** — WHEN a task is briefed THE SYSTEM SHALL ask a stronger reader for a plan without
  code from the packet and the task's last checkpoint, and carry that brief in the next
  packet as its own section ahead of the spec status.
  - source: review
  - note: AI21's junior/senior/principal: the seniors do not type, they read the juniors'
    attempts and hand the writer a brief. Here the senior is the 27B at low effort — the
    reading role it measured well in (locate) — and the writer the 9B, or Claude.
