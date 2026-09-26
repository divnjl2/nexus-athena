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

## Regeneration from the spec, first run (26.09, C-8 / gap 1)

`lib/refinery.py` deleted in a worktree; the packet = the refinery contract's clauses, the
executable specs (tests/test_refinery.py) and a brief of the fourteen public signatures with
one line each; the executor OmniCoder-9B, low + strict, three iterations, verdict
`pytest tests/test_refinery.py`:

| iteration | seconds | what the module held after it | specs green |
|---|---|---|---|
| 1 | 462 | a first draft | red |
| 2 | 902 | all 14 public functions and the constants, 301 lines | 5 of 11 |
| 3 | 511 | one function, 35 lines: the model rewrote the file from scratch | 1 of 11 |

The 9B rung regenerates the skeleton and about half the behaviour from clauses and specs
alone; it does not reach equivalence in three iterations. The third iteration is a frame
defect, not a model result: the checkpoint said "continue from this state", the workspace
was not committed per iteration, and the better state was lost. Recorded as C-11.6
(iterations never regress; the better iteration is restored). The run is repeated after
C-11.6 lands; the equivalence gate (specs, `crosshair diffbehavior`, per-clause mutation
score against the original) is measured on that run. The same experiment on the 3B rung is
recorded when it lands.

## Regeneration from the spec, second run through the daemon (26.09, C-8 / gap 1)

The first real tick of `athena daemon` on the beads queue (issue `nexus-athena-v6x`, label
`athena:regeneration:T9.1`): claim by the bd id, admission by OmniCoder's live `/metrics`,
three iterations with the packet memory, provenance in every record, the workspace committed
per iteration. Iteration 2 lost the one green spec of iteration 1 and the frame restored
iteration 1 before iteration 3 started (C-11.6 in production). The result, judged by the
three gates of C-8.3:

| gate | original `lib/refinery.py` | regenerated by OmniCoder-9B |
|---|---|---|
| specs (`tests/test_refinery.py`, 13) | 13 green | 6 green, 7 red |
| `crosshair diffbehavior`, 15 public functions | — | 8 diverge (reason texts; `merge_record` without `schema`; `bd_return_command` takes 3 arguments, not 4; `merge_metrics` keys) |
| mutation score over the clauses' owned lines, 60 mutants asked | 47 of 55 killed, 0.85, 180 owned lines, 9 clauses | 26 of 30 killed, 0.87, 120 owned lines, 7 clauses (the red specs own nothing) |

Verdict: not equivalent. The score of the regenerated module is not comparable while its
specs are red — a red spec witnesses nothing, so the sweep only sees the lines the six green
ones cover. What the run proved: the loop runs itself end to end (queue, admission,
dispatch, rollback, provenance, release of the claim on red), and the spec alone is not yet
the source for a 9B rung: clauses and executable specs get the skeleton and about half the
behaviour; the rest is the frontier's, or a bigger rung's. The 3B rung wrote nothing at all
(three attempts, `changed 0`): a module from scratch is past its envelope.

## Drafted specs, admitted not trusted (26.09, C-2.1 / gap 4)

`tools/draft_acceptance.py`: the 9B drafts a pytest test per clause from the clause text and
the module's public signatures; a draft is admitted when it passes at HEAD, fails on a forged
break of a line the clause owns (the forge as the base: SWE-smith's fail-to-pass rule) and
covers an owned line. Nine clauses of the refinery layer, two drafts each:

| arm | in the prompt | drafted | admitted | why not |
|---|---|---|---|---|
| 1 | clause + signatures | 18 | 0 | 16 red at HEAD (invented result keys, keyword-only `ts` ignored), 2 no test function |
| 2 | + docstrings + one existing spec as the example | 18 | 0 | 15 red at HEAD, 1 green on the broken code too, 2 no test function |
| 3 | arm 2 + one repair round with the failure (Otter++) | 18 | 1 (C-2.8, after repair) | 11 repaired, 10 of them still red at HEAD; 2 green on the broken code too; 1 no test function |

The one admitted draft is a real test of `sealed_touched` and `verify_verdict` that a reviewer
would keep with two lines cut (it documents a behaviour it observed rather than the clause).
The bottleneck of the factory does not move to the 9B by prompting or one repair round: it does not read a
signature's keyword-only marker and it invents the shape of a result it never saw. The
admission rule caught every one of them, which is the point of C-2.1; the drafting rung is
the frontier until a repair loop or a bigger local rung changes the number.

**Opus tokens for the whole goal block** (25.09 19:27 -> 26.09 18:55, transcript): 1,053,837 output
tokens for the research digest, 41 clauses with red specs, the review of six lane
implementations, the wiring of `athena.py`, two merges through the refinery and the day's
lane operations.

## The ten gaps on 2026-09-26 18:20 — measured state

| gap | state | evidence |
|---|---|---|
| 1 regeneration from the spec | measured, not yet equivalent for a 9B rung | two runs; three gates (specs 6/13, diffbehavior 8/15 diverge, mutation on partial coverage); C-11.6 born from run 1 |
| 2 oracles of the second kind | one live | C-9.4 `lint-imports` on the frame's own structure, 2 contracts kept; the binding guard binds through the config; perf and golden renderers exist, no clause yet |
| 3 mutation in the gate, sealed tier | live | `athena merge` runs the `mutation` stage on changed lines (first merge through it: no survivor on an added line); `features/foundry-layer/sealed/` with three second readings |
| 4 authorship throughput | measured, negative for the 9B | 1 of 54 drafts admitted over three arms (signatures; + docstrings and an example; + one repair round); the admission rule caught the rest |
| 5 the daemon | live | `athena daemon --once` on the real beads queue: claim by bd id, live admission, dispatch, rollback, provenance, release on red |
| 6 the ladder | live | `--ladder pi-3b,pi-omni9` on T9.1: the 3B red three times, the daemon released the claim and escalated to OmniCoder with the handoff (`red twice on pi-3b`), recorded in the ledger |
| 7 provenance | in every record | model through the registry, runtime and its version from the lane, packet and tool digests; `missing_provenance` names weights and seed |
| 8 capacity-aware lanes | live | the daemon admits by `/metrics` or `/slots`; with `--executors` it routes by prefix affinity among the admitted lanes (C-11.7), warmth table beside the ledger |
| 9 sandbox | **live**: the OS sandbox runs the executor; the relay fence on every lane | C-10.1: `--sandbox required` — OmniCoder inside sandbox-runtime (account `srt-sandbox`, WFP fence, loopback only to the fenced relay 60081) regenerated `pick_admitted` from C-11.7, spec green in 51 s, 1 iteration (20:52). Probed from inside: writes to the lane, model and secret trees on D: refused, the caller's profile unreadable, github and the lane's direct port blocked, the relay reachable. C-10.3: all three executor relays (8417, 60081, 60083) refuse a `write` outside the worktree. Residual, said out loud: `D:/tmp` (where the worktrees live) stays writable to the account — the drive grants Authenticated Users modify and a deny on its root needs elevation |
| 10 memory in the packet | live | repo map after the prefix, lessons appended on red (three from the regeneration run) and selected by clause and file |

What stays open, in order: the OS sandbox's spawn on this box (logon of `srt-sandbox` refused; the
relay fence holds meanwhile), a perf clause with pytest-benchmark (gap 2), and
the two things the measurements say about the rungs: regeneration needs a bigger rung or the
frontier's finish, and spec drafting stays the frontier's.


## The OS sandbox, live (26.09 19:00 -> 20:55, gap 9 / C-10.1)

The morning's verdict was wrong about the cause: `CreateProcessWithLogonW(srt-sandbox)` failed
with 0x80070005 not for logon rights or seclogon but because the sandbox account could not read the
srt package under the caller's profile. Each blocker after that was measured and closed the same
evening; `tools/sandbox_install.ps1` replays the host preparation.

| blocker (measured) | cause | closed by |
|---|---|---|
| spawn refused 0x80070005 | the runner image under `C:/Users/<me>/AppData/Roaming/npm` unreadable to `srt-sandbox` | `icacls <npm> /grant <sid>:(OI)(CI)RX /T`; spawn in 3 s |
| `srt-win acl grant` timed out at 60 s | an inheritable ACE walks the whole subtree (Python311: 234k files, 446 s) | toolchain trees granted once at install; per run only the worktree is stamped |
| `denyWrite: ["D:/"]` failed 0x5, per-tree denies timed out | the drive root needs elevation; big trees again | persistent `icacls /deny (OI)(CI)W` on the lane, model and secret trees, outside srt |
| node `EPERM lstat C:/Users/<me>/AppData` | realpath lstats every ancestor of a per-user install | pi installed machine-wide under `C:/ProgramData/athena/npm` (same 0.73.1) |
| pi died on `npm install -g pi-hashline-edit-pro` | the seeded settings listed a package; the fence blocks npm | seed settings without packages |
| `PI_CODING_AGENT_DIR` never arrived | the sandbox drops the environment; srt splits `-c` on `&&`; positional args are option-parsed; the .cmd shims re-parse `\"` and a `\|` in the packet became a pipe | node + cli.js for srt and pi, a launcher `.cmd` in `<worktree>/.athena` |
| instruction text corrupted (em-dashes) | cmd reads a batch file in the OEM code page; text mode doubled the CR | launcher written as UTF-8 bytes with `chcp 65001` first |
| the packet never reached pi | the sandbox does not forward stdin | packet written to `<worktree>/.athena/packet.txt`, redirected by the launcher |
| a C: working directory refused (`mapped_drive_cwd`, exit 16) | srt sees C: as a remote drive on this box | availability probed in the workspace; worktrees on D: |

Probes from inside the sandbox after the fixes: `whoami` = `srt-sandbox`; write inside the
worktree ok; writes to `D:/llama-swap`, `D:/models`, `D:/llm-lanes`, `D:/secrets` refused;
`~/.pi/agent/models.json` of the caller unreadable; github 000; the lane's direct port 8006 000;
the fenced relay 60081 200 from curl and from node. Residual: `D:/tmp/lanes` writable (the drive's
Authenticated Users modify) — the worktrees' own drive is the one hole left, said out loud in C-10.1.

The dispatch (T6.6 seeded red: `pick_admitted` body removed, `--sandbox required`, OmniCoder via
60081): PASS in iteration 1 of 3, 51 s, 32.9k in / 1.4k out, one file changed, keep-best committed.

## The ladder, live (26.09 18:09 -> 18:51)

`athena daemon --once --executor pi-3b --ladder pi-3b,pi-omni9` on the same regeneration task:
the 3B red three times without writing a file (234, 356, 170 s), the daemon released the claim,
escalated with the handoff (`pi-3b -> pi-omni9: red twice on pi-3b` in `daemon.jsonl`), and
OmniCoder ran its three iterations (250, 197, 108 s) to 7 of 13 specs green, every iteration
committed in the worktree. The bead is open again with the checkpoints in its notes. The loop
of gap 5, the ladder of gap 6, the provenance of gap 7, the admission of gap 8 and the memory
of gap 10 all ran in this one tick without the operator or the frontier model in it.
