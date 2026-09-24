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
- **C-1.6** — WHEN a packet is about to be executed THE SYSTEM SHALL state each spec's current
  verdict in it, a red one with its output tail.
  - source: ledger
  - note: given the implementer prompt, the file and the test, the 27B viewed the file once
    and called finish: "already complete and correct". Nothing in the packet said the spec
    was red at that moment. Now the packet does.
  - source: ledger
  - note: the three iterations that landed nothing spent 3, 4 and 9 turns on Read, one of
    them into the context ceiling; the one that landed did a single Read. With the spec's
    own source in the packet there is nothing left to go and read.

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

## C-4 — The record

- **C-4.1** — WHEN a dispatch completes THE SYSTEM SHALL append one record with the executor,
  the task, whether it landed, whether it was green, the duration and the tokens.
- **C-4.2** — WHEN dispatch metrics are requested THE SYSTEM SHALL report per executor the
  attempts, the landed rate and the green rate.
- **C-4.3** — WHEN a packet is requested without an executor THE SYSTEM SHALL print it and
  record nothing.

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
  - source: review
  - see: https://github.com/vllm-project/vllm/issues/42021
  - note: found by searching before inventing: Qwen3.5 under vLLM's qwen3 reasoning parser
    with thinking on writes its tool calls inside the reasoning in a non-standard shape and
    the tool parser never sees them; `enable_thinking=false` per request is the workaround
    the issue names. Our lane answers with reasoning_content present, so this was our bug.
