# ADR-0009: The foundry wraps maintained OSS and takes the loop out of the operator's session

- Status: accepted
- Date: 2026-09-25
- Deciders: operator
- Cited by: features/foundry-layer C-1.1, C-3.1, C-3.5

## Context

By 2026-09-25 the lanes land clauses: an agent-trained 3B holds 8 of 9 refinery clauses at
32k per slot, the vanilla 9B lands class A first time with strict tool calling, and Opus's
output rate while the lanes execute is 130k tokens per hour against 460k alone. What stops
this from being a factory is not the executors. Ten gaps were named and researched the same
day: mutation is a report and not a gate; model-drafted tests are trusted or not used; the
loop of pick, dispatch, verdict, offer, escalate lives in the frontier model's session;
lanes are fed blind to their own metrics; the escalation ladder is folklore; a verdict does
not name the model that produced it; the packet carries no memory; regeneration from the
spec is not proven; only a test command can be an oracle; the executor runs with the host's
shell. For seven of the ten a maintained, Windows-capable open-source project covers most
of the gap (cosmic-ray, beads, import-linter and pytest-benchmark and syrupy, in-toto
attestation, aider's repomap, CrossHair, anthropics/sandbox-runtime); for the ladder nothing
maintained fits and the logic is under two hundred lines; for lane admission llama-swap is
already deployed and the missing part is a small admission controller.

## Decision

The foundry layer closes the ten gaps as clause groups with red specs before the code, in
the order of leverage the research gave: the mutation gate and admitted drafts first (they
make every later green trustworthy), the daemon and lane admission second (they make the
loop run unattended), the ladder and provenance third (they need the verdict log the first
two produce), memory and regeneration and oracles and the sandbox last. Every group wraps
its OSS pick behind an injected runner and a pure function in `lib/`; the frame never
re-implements what the pick does, and the specs never execute the pick. The operator's
process is fixed with it: the frontier model researches and writes clauses and specs, the
lanes implement, the frontier model reviews and finishes only after the lanes' three
iterations (ADR-0007), and the Opus token cost per landed clause is measured and reported.

## Consequences

- The refinery gains a `mutation` stage and a stripped sealed tier; some offers that were
  green will be refused, on evidence, with the first survivor named.
- `athena daemon` becomes the way work runs; the operator's session becomes a reviewer's.
- Records grow a provenance block and merged verdicts an in-toto statement; the ledger of
  the first weeks stays as it is and is marked as pre-provenance.
- Two lanes are named in config with limits and cooldowns; a lane's crash under load is a
  scheduler defect from now on, not an incident.
- Three picks are alpha or Windows-sensitive (sandbox-runtime Windows, pytest-memray
  absent, mutmut absent): the contract says so and the frame degrades loudly, never silently.
