# Contract: Athena Foundry Layer (v3.16)

> Ten gaps between "the lanes land clauses" and "the factory runs itself, and the spec is the
> source", named on 2026-09-25 against the measurements of the week and the state of the art
> (research digest of the same day: OSS picks per gap, Windows-capable). Each gap is closed
> here as a clause group before the code exists; pure functions in `lib/` take injected
> runners, the CLI wires the real world. Ids are allocated once and never reused.

## C-1 — Mutation is a gate, not a report

- **C-1.1** — WHEN a workspace is checked by the refinery THE SYSTEM SHALL restrict the mutation
  sweep to the lines the task changed, mapped through the clause map to the clauses that own
  them, and report which changed lines no clause owns.
  - see: ../../docs/adr/0009-the-foundry-wraps-oss-and-runs-itself.md@364e242e5a983636
  - source: design
  - note: cosmic-ray (MIT, runs on native Windows; mutmut needs fork) has `cr-filter-git` for
    exactly this; the frame supplies the diff lines and the ownership. Whole-module sweeps are
    the mutation layer's business, not the merge queue's.
- **C-1.2** — WHEN the sweep ends THE SYSTEM SHALL compute a per-clause mutation score over the
  clause's owned lines and list the survivors by path, line and kind.
  - source: design
- **C-1.3** — WHEN a clause's score on lines the task added is under the threshold, or a mutant
  on an added line survives, THE SYSTEM SHALL refuse the offer at a `mutation` stage naming the
  clause and the first survivor, and only advise on lines the task did not touch.
  - source: design
  - note: hidden-test evidence (arXiv 2511.16858: 22-33% of patches green on visible tests
    fail hidden ones; 2604.01518: mutation-augmented tests take 4-9 points off top agents).
    The threshold starts at 0.7 and is a parameter, never a constant in code.
- **C-1.4** — WHEN a sealed acceptance run is shown to an executor or written into a checkpoint
  THE SYSTEM SHALL reduce it to pass or fail per test id, never the assertion text.
  - source: design
  - note: extends refinery C-2.8. Agents that read the grader learn the grader; the sealed
    tier leaks through error messages unless the frame strips them.

## C-2 — Drafted specs are admitted, not trusted

- **C-2.1** — WHEN a model drafts a test for a clause THE SYSTEM SHALL admit it only when it
  fails at the task's base, passes at its head, and covers at least one line the clause owns.
  - source: design
  - note: TDD-Bench-Verified's admissibility (fail-before, pass-after, covers the diff). A
    small model's favourite test asserts that the function returns something; that test is
    green at the base and is refused here.
- **C-2.2** — WHEN a clause draft is read THE SYSTEM SHALL accept only an EARS shape —
  ubiquitous, event-driven, state-driven, optional, unwanted, or complex — with exactly one
  SHALL, and name the defect otherwise.
  - source: design
  - note: no maintained OSS drafts EARS; the validator is ours (Kiro's requirements.md is the
    production example of the grammar).
- **C-2.3** — WHEN drafts are judged THE SYSTEM SHALL keep, per drafting model, the counts of
  drafted, admitted and accepted-without-edit, and render the acceptance rate.
  - source: review
  - note: the writer of specs is the measured bottleneck of the whole factory (Opus 460k
    output tokens per hour alone against 130k with the lanes executing); this is the number
    that says whether the 9B can carry part of it.

## C-3 — The daemon: the loop leaves the operator's session

- **C-3.1** — WHEN the daemon ticks THE SYSTEM SHALL take the ready task of highest priority
  that no lane is running, claim it, and name its worktree by task id and packet digest, so a
  restart finds the same worktree for the same work.
  - see: ../../docs/adr/0009-the-foundry-wraps-oss-and-runs-itself.md@364e242e5a983636
  - source: design
  - note: beads (`bd ready --json`, `bd update --claim`) is the ledger and the lease; Gas
    Town's Refinery and Witness are the reference design, not code to vendor.
- **C-3.2** — WHEN a claim's heartbeat is older than the lease THE SYSTEM SHALL release the
  claim, kill the attempt's process tree and count a crashed attempt against the task.
  - source: design
- **C-3.3** — WHEN the daemon starts and finds a worktree whose last record for its task is
  green THE SYSTEM SHALL offer it to the refinery instead of running the task again.
  - source: design
  - note: idempotency under `kill -9`: the smallest experiment is ten tasks, two workers,
    the daemon killed twice, no task lost or run twice to completion.
- **C-3.4** — WHEN the daemon acts THE SYSTEM SHALL append one line to its ledger with tick,
  task, action and reason, and cap its actions per task per hour.
  - source: design
  - note: nudge storms are Gas Town's measured failure mode of a Witness.
- **C-3.5** — WHEN `athena daemon` runs THE SYSTEM SHALL loop tick, dispatch, verdict, offer
  and escalation over the plan's tasks with the lane admission of C-4 and the ladder of C-5,
  and stop cleanly on a stop file.
  - see: ../../docs/adr/0009-the-foundry-wraps-oss-and-runs-itself.md@364e242e5a983636
  - source: review

## C-4 — Lanes admit by capacity

- **C-4.1** — WHEN lane metrics are read THE SYSTEM SHALL parse vLLM's `/metrics` (requests
  running and waiting, KV usage, prefix-cache queries and hits) and llama.cpp's `/slots` into
  one lane state.
  - source: design
- **C-4.2** — WHEN a task is offered to a lane THE SYSTEM SHALL admit it only when nothing is
  waiting, KV usage is under the ceiling and the running count stays under the limit less
  one, and park it otherwise with the reason.
  - source: ledger
  - note: the KV-headroom rule measured on 23.09 (concurrency at the slot count overflows the
    pool and the lane dies, not unloads); `kv_cache_usage_perc` lags, so two samples decide.
- **C-4.3** — WHEN two tasks share a packet prefix THE SYSTEM SHALL route the second to the
  lane that last served that prefix while the lane is warm.
  - source: ledger
  - note: pi's prefix is byte-stable between turns (traced); the 13-23% prefix-cache hit rate
    in production was the pool being evicted by unrelated contexts.
- **C-4.4** — WHEN a lane answers with a server error twice in a row THE SYSTEM SHALL cool it
  down for a period and route around it until the period ends.
  - source: design

- **C-4.5** — WHEN a lane is offered a speculative-decoding flag THE SYSTEM SHALL admit the flag
  only after the same tasks land the same verdicts with and without it and temperature-zero
  outputs are token-identical, and name the first divergence otherwise.
  - source: design
  - note: SuffixDecoding (Arctic Inference, in vLLM as `method: suffix`) is lossless by
    construction and up to 5x on agentic loops — and on our GDN hybrids (Qwen3.5/3.8) vLLM's
    ngram and suffix paths silently corrupt output until PR #56531 or #55504 lands (Sept
    2026: unmerged). A speed flag enters through this oracle, never through a blog post.

## C-5 — The ladder: cheap first, escalate on evidence

- **C-5.1** — WHEN a task is dispatched THE SYSTEM SHALL log its pre-dispatch features: packet
  tokens, files owned, clause count, spec count, lines owned and prior attempts.
  - source: design
  - note: SWE-Router and Fail-Fast/Restart-Smart route on trajectory and packet features; the
    log comes first, the model on top of it after a hundred verdicts.
- **C-5.2** — WHEN a rung's attempt is red twice, or an attempt shows a fail-fast signal — turns
  past the p90 for its clause size, the same tool call repeated, no write after the median
  turn — THE SYSTEM SHALL escalate to the next rung and hand it the attempt's files touched,
  last test output and notes.
  - source: design
  - note: Scrouting's ablation: the handoff, not the router, carried the gain (the cheapest
    fixer with the scout's handoff matched the learned router).
- **C-5.3** — WHEN the ladder's records reach a sample THE SYSTEM SHALL report per rung and
  clause class the win rate and GPU minutes per green, and disable a rung whose win rate for a
  class is under the floor.
  - source: design
  - note: measured 25.09: the 3B rung wins class A first time and never class B with git; a
    cascade multiplies cost where the small rung nearly always fails.

## C-6 — Provenance: a verdict names what produced it

- **C-6.1** — WHEN a verdict is recorded THE SYSTEM SHALL carry the model identity (id and
  weights digest or pinned revision), the runtime and its version, the sampling parameters
  and seed, the rendered packet's digest, the tool set digest and the relay version.
  - source: ledger
  - note: 25.09 alone: four executors and two runtimes in one day; the records say `pi-4b#gpu`
    and a month later that is not reproducible. A model's name is not its identity.
- **C-6.2** — WHEN a merged verdict is written THE SYSTEM SHALL emit an in-toto statement with a
  SLSA-shaped predicate `athena/verdict/v1` whose subject is the merged tree digest.
  - source: design
  - note: in-toto/attestation (Apache-2.0) for the envelope; SLSA v1 field vocabulary;
    `openfab/generation` fields for authorship where SLSA has none. Signing only for merges.
- **C-6.3** — WHEN a record lacks a provenance field THE SYSTEM SHALL name the missing field,
  so a replay that diverges can say why.
  - source: design

## C-7 — Memory rides in the packet, capped

- **C-7.1** — WHEN a packet is packed THE SYSTEM SHALL add a repository map seeded from the
  task's files and clauses within a token budget, placed after the static prefix.
  - source: design
  - note: aider's repomap (Apache-2.0, tree-sitter tags and personalised PageRank) vendored
    and trimmed; after the prefix so the lane's cache keeps its hits (C-4.3).
- **C-7.2** — WHEN a verdict is red THE SYSTEM SHALL append a lesson: clause id, file, failure
  class, a one-line rule and the verdict id — never the diff.
  - source: design
  - note: DreamBench-SWE shows no robust win for conversation-memory servers on SWE tasks;
    verbatim past patches induce copy-paste of stale code. Rules, not diffs.
- **C-7.3** — WHEN a packet is packed THE SYSTEM SHALL include at most N lessons chosen by exact
  clause id and file match, each capped in length, and retire a lesson that rode along in ten
  green packets.
  - source: design

## C-8 — Regeneration from the spec

- **C-8.1** — WHEN a module is regenerated THE SYSTEM SHALL pack its clauses, its specs and its
  public signatures only, never the old body.
  - source: design
  - note: the proof that the spec is the source: the same behaviour from clauses and specs
    alone. CrossHair `diffbehavior` (MIT) finds inputs where old and new diverge; absence
    of a counterexample is not proof, the spec is the oracle and the diff a smell detector.
- **C-8.2** — WHEN a regenerated module lands green THE SYSTEM SHALL run the behaviour diff per
  public typed function against the old module and record every counterexample.
  - source: design
- **C-8.3** — WHEN equivalence is judged THE SYSTEM SHALL require the specs green, no
  counterexample and a per-clause mutation score not under the original module's.
  - source: design

## C-9 — Oracles of the second kind

- **C-9.1** — WHEN a clause says a package shall not import another, or names layers, THE
  SYSTEM SHALL render an import-linter contract and the run command that checks it.
  - source: design
  - note: import-linter (BSD-2) for structure; Tach is the alternative, the two disagree on
    namespace packages, pick one.
- **C-9.2** — WHEN a clause names a time budget for a command THE SYSTEM SHALL render a benchmark
  run command that fails on a regression past the budget against a stored baseline.
  - source: design
  - note: pytest-benchmark (BSD-2) works on Windows; memray does not — memory budgets go
    through `tracemalloc` in a fixture. Benchmarks beside a vLLM lane are noisy: medians,
    minimum rounds, two consecutive failures.
- **C-9.3** — WHEN an executor's command would update a snapshot baseline THE SYSTEM SHALL
  refuse the command.
  - source: design
  - note: golden files through syrupy invite "update the snapshot" as the fix.

## C-10 — The sandbox

- **C-10.1** — WHEN the sandbox flag is on THE SYSTEM SHALL wrap every executor command in
  the sandbox runtime with write access to the worktree only, read access to the toolchain,
  and network limited to the lane ports.
  - source: design
  - note: anthropics/sandbox-runtime (Apache-2.0) has a Windows alpha: dedicated local user,
    WFP egress fence, NTFS ACEs; both OpenAI and Anthropic rejected AppContainer for a
    shell-driving agent. Behind a flag until the alpha settles.
- **C-10.2** — WHEN the sandbox is unavailable THE SYSTEM SHALL say so and run unsandboxed only
  when the flag allows it explicitly.
  - source: review
