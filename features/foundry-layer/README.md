# Foundry layer (v3.16) — the factory runs itself, and the spec is the source

Ten gaps named on 2026-09-25, each a clause group in `contract.md` with a red spec before the
code. The process the operator fixed the same day: the frontier model researches and writes
clauses and specs, the lanes implement, the frontier model reviews and finishes only after
three lane iterations (ADR-0007), and the Opus token cost per landed clause is measured.

## The gaps, the OSS pick, the module

| group | gap | OSS pick (license) | module |
|---|---|---|---|
| C-1 | mutation is a gate on changed lines; sealed runs stripped | cosmic-ray (MIT, native Windows, `cr-filter-git`) | `lib/mutgate.py` |
| C-2 | model-drafted tests admitted fail-before/pass-after; EARS validator; acceptance rate | TDD-Bench-Verified semantics (Apache-2.0); validator is ours | `lib/drafts.py` |
| C-3 | the daemon: tick, lease, resume, capped ledger, `athena daemon` | beads `bd ready --json` / `--claim` (MIT); Gas Town as design | `lib/daemon.py`, `athena.py` |
| C-4 | lanes admit by their own metrics; prefix affinity; cooldown; speculation oracle | llama-swap (deployed) + vLLM `/metrics`, llama.cpp `/slots` | `lib/lanes.py` |
| C-5 | the ladder: logged features, escalation with a handoff, rung table | build (<200 LOC); FrugalGPT, SWE-Router, Fail-Fast as sources | `lib/ladder.py` |
| C-6 | provenance block; in-toto statement; missing fields named | in-toto/attestation (Apache-2.0), SLSA v1 vocabulary | `lib/provenance.py` |
| C-7 | repo map after the prefix; lessons from red verdicts, selected by clause and file, decayed | aider `repomap.py` (Apache-2.0) vendored; plain JSONL | `lib/memory.py` |
| C-8 | regeneration packet; behaviour diff; equivalence verdict | CrossHair `diffbehavior` (MIT), Hypothesis | `lib/regen.py` |
| C-9 | import-linter and benchmark commands from clauses; refused baseline updates | import-linter (BSD-2), pytest-benchmark (BSD-2), syrupy (MIT) | `lib/oracles.py` |
| C-10 | sandbox config, argv, decision | anthropics/sandbox-runtime (Apache-2.0, Windows alpha) | `lib/sandbox.py` |

Research digest with sources: the session `docs/research/2026-09-25-ten-gaps-oss-first.md` (58 URLs);
the decision: `docs/adr/0009-the-foundry-wraps-oss-and-runs-itself.md`.

## Order of work (by leverage, from the digest)

1. C-1 and C-2: every later green becomes trustworthy, and the forge gets SWE-smith-style tasks.
2. C-3 and C-4: the loop runs unattended; lanes stop crashing under load.
3. C-5 and C-6: both need the verdict log the first two produce; provenance fields fixed
   before the log grows.
4. C-7, C-8, C-9, C-10: memory, regeneration, second-kind oracles, sandbox behind a flag.

## Measured (2026-09-25 19:58 -> 2026-09-26 15:40)

Eighteen tasks, all written by Claude as clauses and red specs, executed by three lanes in
parallel (vanilla 9B on the 3060, OmniCoder-9B and Nanbeige-3B on the 3090), low + strict,
three iterations each, then assembled by cherry-pick, verified and merged by the refinery
(`merge: merged — T5.2 by verify -> master`, 6 contracts held).

| task | executor | result |
|---|---|---|
| T1.1 mutation targets and scores | pi-9b | green @2 |
| T1.2 mutation verdict, sealed summary | pi-9b | green @2 |
| T1.3 draft admission, EARS validator | pi-3b | green @1 |
| T1.4 acceptance per model | pi-3b | green @1 |
| T2.1 the tick, worktree name, stale claims | pi-9b | green @5 (priority inverted twice) |
| T2.2 resume, capped ledger | pi-9b | green @1 |
| T2.3 lane state, admission | pi-3b | green @1 |
| T2.4 prefix affinity, cooldown | pi-3b red x5 | Claude (ADR-0007) |
| T2.5 `athena daemon` | pi-omni9 red x3 | Claude (ADR-0007) |
| T2.6 speculation oracle | pi-3b | green @3 |
| T3.1 features, escalation, handoff | pi-3b | green @1 |
| T3.2 rung table | pi-3b | green @1 |
| T3.3 provenance, in-toto statement | pi-omni9 | green @1 |
| T4.1 repo map in the packet | pi-9b | green @3 |
| T4.2 lessons | pi-9b | green @1 |
| T4.3 regeneration packet, diff, verdict | pi-omni9 2 of 3 specs, red x3 | Claude (the crosshair parse) |
| T5.1 import-linter, benchmark, refused updates | pi-3b @1, pi-omni9 @1 | green |
| T5.2 sandbox config, argv, decision | pi-3b @1, pi-omni9 @1 | green |

Lanes landed 15 of 18 (39 attempts, 344 GPU-minutes); Claude finished 3 after the lanes'
three iterations and fixed two things the specs did not see: effect imports a lane left in
`lib/regen.py` (the repository's own architecture lint caught them) and the registry spec.
The 3B took 8 of its 9 first time; the class it cannot do is the same as before (a two-file
change, a 3k-line CLI file).

**Opus tokens for the block** (transcript, 25.09 19:27 -> 26.09 15:47, the overnight gap
included): 511k output tokens for 34 clauses and 18 tasks, that is 15k per clause, against
29k per clause on 23.09 when Claude wrote contract and code alone. Half the frontier cost
per clause, with the research digest, the contract, the specs, the lane operations of a
reboot day and the three finished tasks inside the 511k.
