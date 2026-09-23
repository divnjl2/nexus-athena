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

## C-4 — The record

- **C-4.1** — WHEN a dispatch completes THE SYSTEM SHALL append one record with the executor,
  the task, whether it landed, whether it was green, the duration and the tokens.
- **C-4.2** — WHEN dispatch metrics are requested THE SYSTEM SHALL report per executor the
  attempts, the landed rate and the green rate.
- **C-4.3** — WHEN a packet is requested without an executor THE SYSTEM SHALL print it and
  record nothing.
