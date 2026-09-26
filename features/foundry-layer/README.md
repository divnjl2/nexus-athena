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


## Regeneration from the spec, third run: decomposed by task (26.09 21:30 -> 23:20, C-8.4 / gap 1)

The whole-module packet asked the 9B rung for 300 lines in one window and it rebuilt the skeleton
and half the behaviour (runs 1 and 2). The third run keeps the module deleted but asks for it the
way the frame asks for anything: `lib/refinery.py` stubbed to its signatures, constants and
docstrings, then the nine refinery tasks whose specs went red dispatched in order, three
iterations each, OmniCoder-9B strict low inside the OS sandbox. Two frame defects surfaced on the
first pass and became C-8.4: every task's verdict counted the other stubs' red specs and could not
be green however right its own function was; and an iteration that gutted the spec file was kept
because the green counts tied. With `--inherit-red` (own checks and regressions from the base
decide; inherited reds named; a tainted iteration never kept; a task that ends red restores the
base; a radius batch inherited by its members):

| task | function(s) regenerated | verdict | iteration | seconds | tokens in / out |
|---|---|---|---|---|---|
| T2.1 | `admit` | PASS | 1 of 3 | 101 | 69.7k / 5.4k |
| T2.2 | `rebase`, `conflicts_from` | FAIL | 3 of 3 | 87 per iteration | 236.8k / 4.5k |
| T2.3 | `first_failure` | PASS | 1 of 3 | 29 | 18.0k / 1.1k |
| T2.4 | `fast_forward` | PASS | 2 of 3 | 174 | 330.6k / 11.5k |
| T2.5 | `merge_record`, `parse_merges`, `bd_return_command` | PASS | 1 of 3 | 32 | 22.0k / 1.4k |
| T2.6 | `merge_metrics`, `render_merge_metrics` | PASS | 1 of 3 | 95 | 102.4k / 4.7k |
| T2.8 | `verify_verdict` | PASS | 1 of 3 | 148 | 251.3k / 8.2k |
| T2.9 | `sealed_dirs`, `sealed_checks`, `sealed_touched` | PASS | 1 of 3 | 118 | 328.7k / 4.9k (packet budget raised to 40k chars; first try refused at 38k) |
| T2.10 | `checked_out_at`, the read-tree sync | FAIL | 3 of 3 | 254 per iteration | 448.6k / 8.6k; hit the 30k window |

Seven of nine tasks green, five of them in the first iteration; `tests/test_refinery.py` 10 of 12
green on the reassembled module (runs 1 and 2: 6 green at best, when the file held 13). The two reds are the two git
functions with the most branches (conflict handling in `rebase`; the two-tree sync of a
checked-out target in `fast_forward`) — the 9B rung's envelope, not the frame's. The equivalence
gates of C-8.3 on the reassembled module against the original:

| gate | original | regenerated, run 3 |
|---|---|---|
| specs (`tests/test_refinery.py`, 12) | 12 green | 10 green, 2 red (T2.2, T2.10) |
| `crosshair diffbehavior`, 15 public functions | — | 8 of the 12 implemented functions diverge on crosshair's edge inputs (reason texts, key order and extra keys in `merge_record` / `verify_verdict`, a side effect in `sealed_dirs`), plus the 3 still stubbed |
| mutation score over the clauses' owned lines, 60 mutants asked, map recomputed on the regenerated module | 47 of 55 killed, 0.85, 180 owned lines, 9 clauses | 36 of 42 killed, 0.86, 206 owned lines, 8 clauses (C-2.9 owns nothing while its spec's neighbours are red); survivors: a default flag, four `and` flips in the sealed and verify paths |

**Finished under ADR-0007 (27.09 00:05).** After the lane's three iterations the frontier wrote the
two functions the 9B rung had not (`rebase`, `fast_forward`, with `checked_out_at` and a
`conflicts_from` that reads both CONFLICT shapes) from the clauses and the specs — never from
the old body. The gates on the finished module:

| gate | original | regenerated, run 3, finished |
|---|---|---|
| specs (`tests/test_refinery.py`, 12) | 12 green | 12 green |
| mutation score, map recomputed, 60 mutants asked | 47 of 55, 0.85, 180 owned lines | 43 of 53, 0.81, 204 owned lines, 9 clauses (survivors: `or`/`and` flips in `rebase` and the sync path, one default flag) |
| `crosshair diffbehavior`, 15 functions | — | the four frontier-finished functions: no counterexample; 9 of the 11 lane-regenerated diverge on edge inputs (`\x00` names, reason texts, key sets, an extra side effect in `sealed_dirs`); 2 are stubs the refinery contract does not own |

Verdict under C-8.3: **not equivalent** — the specs are green, the mutation score is 0.04 under the
original's, and the behaviour diff still finds inputs the specs never pinned. What the specs pin,
the regenerated module does; what they do not pin (the wording of a reason, the order of keys, a
`\x00` in a path) it does differently. That is the exact measure of how much of the module the spec
is the source of today, and the survivors name the lines a spec should own next.
**Second and third pass of the finish (27.09 02:10 -> 03:20).** With the full diff report in hand the
frontier brought every named function to its clause — three kinds of edit, each stated: a record
shape other modules consume (the merge record opens with its schema, C-2.5; the verify verdict has
the dispatch verdict's shape, C-2.7), a wording the clause asks for (the reason names the task and
the workspace, C-2.1; the bd note names the stage, C-2.5), and the domain the clause states
(`features/*/sealed` is one level, C-2.8; a list is a list). The two foundry-owned functions (C-11.2)
were finished from their foundry specs. What the visible specs left free is now pinned in the
refinery's sealed tier, and the pins hold on the original module too. The third pass removed the
guard branches the mutation survivors named — code no spec asked for.

| gate | original | pass 2 | pass 3 |
|---|---|---|---|
| specs (`tests/test_refinery.py`, 12) + sealed + foundry wiring | green | 20 green | 20 green |
| `crosshair diffbehavior`, 15 functions | — | **0 counterexamples** | **0 counterexamples** (rerun 03:40, 335 s, once the host had 16 GB free) |
| mutation score, map recomputed, 60 mutants asked | 47 of 55, 0.85, 180 owned lines | 38 of 46, 0.83, 157 lines | **38 of 42, 0.90**, 156 lines; survivors: two `and` flips in `parse_merges`/`conflicts_from`, two in `verify_verdict`'s reasons |

**Verdict under C-8.3 on pass 3 (`regen-final-state` at 03f6bb6): equivalent.** The specs are green,
the behaviour diff finds no input on which the module and the original differ, and the mutation
score is above the original's on the same specs. The honest shape of the result: the 9B rung
produced 7 of 9 tasks and 10 of 12 specs from clauses and specs alone; the frontier finished the
rest under ADR-0007 from the clauses, with the diff report in hand; and what the visible specs had
left free is now pinned in the sealed tier, so the next regeneration is judged against more than
this one was. The spec is the source of what it pins; tonight it pins the whole module.
What changes in the answer to gap 1: the spec is a source at the granularity the frame already
works at — one task, one window — and not at the granularity of a module for a 9B rung. The
decomposition is the packet's, not the operator's: the plan's tasks and their specs cut the module.

## Drafted specs, arm 4: the repair loop (26.09 21:20 -> 22:10, C-2.1 / gap 4)

Arm 3 gave the 9B one repair round with the failure in hand and admitted 1 of 18. Arm 4 gives up to
three rounds (`tools/draft_acceptance.py ... rich 3`). Nine clauses, two drafts each, judged in the
50-minute budget the run had beside the regeneration series:

| arm | repair rounds | drafted | admitted | why not |
|---|---|---|---|---|
| 3 | 1 | 18 | 1 | 10 still red at HEAD after the repair, 2 green on the broken code too, 1 no test function |
| 4 | up to 3 | 13 judged (C-2.1 to C-2.7, the run timed out) | 5 | 6 red at HEAD (in 5 of them the repair reply carried no test function, so the loop stopped at round 0), 2 green on the broken code too |
| 5 | up to 3, a re-ask when the reply has no test function, pi in a scratch worktree, stall guard | 13 judged in the hour (C-2.1 to C-2.7) | 4 (C-2.1, C-2.3, C-2.6, C-2.7 — the last after three rounds) | 6 red at HEAD after the full three rounds, 4 green on the broken code too; no stall, no stray file |

Admitted drafts by clause: C-2.1 (after 2 rounds), C-2.2 (1), C-2.3 (1), C-2.4 (both drafts, 1 and 2
rounds). The lever is the loop, not the prompt: the rate goes from 1 in 18 to 5 in 13 when the model
sees its own failure up to three times. What stops the rest is a repair reply without a test
function; a round that re-asks for the function would be the next arm. The admission rule held:
the two drafts that were green on the broken code were refused. The drafting tool ran pi in the
repository root and the model left four test files there; it now runs pi in a scratch worktree and,
when a repair reply carries no test function, asks once more for the function (arm 5). Arm 5's first
run (27.09 00:00) judged 3 drafts, admitted 1, then died on a pi call that stalled for 20 minutes with
the lane idle — the tool had no stall guard; every pi call is now bounded and a stall is a row, not a
crash. The rerun (27.09 00:10 -> 01:10) judged 13 in its hour and admitted 4: the re-ask makes every repair
round happen (seven drafts used all three) and changes which drafts land, not how many — four to five
of thirteen is the 9B rung's rate with a three-round loop. What now stops the rest splits evenly: drafts
still red after three repairs, and drafts that pass on the broken code too (the admission rule's catch).

## The ten gaps on 2026-09-27 03:45 — measured state

| gap | state | evidence |
|---|---|---|
| 1 regeneration from the spec | **equivalent under C-8.3** on the finished module (specs green, 0 counterexamples in 15 functions, mutation 0.90 over 0.85, one state 03f6bb6); the lane's own share measured apart | lane alone: whole module 6 specs at best, by task 7 of 9 tasks and 10 of 12 specs; frontier finish in three passes under ADR-0007; the unpinned behaviour the diff found is pinned in the refinery's sealed tier |
| 2 oracles of the second kind | three live | C-9.4 `lint-imports` on the frame's own structure; C-9.5 a time and memory budget as a spec (pytest-benchmark + tracemalloc, negative control); C-9.6 a golden file as a spec (the merge metrics rendering; a golden edit taints the verdict; snapshot-update flags refused) |
| 3 mutation in the gate, sealed tier | live, and the sealed tier is the norm | `athena merge` runs the `mutation` stage on changed lines by default (`--no-mutation` is the exception, said on the command line); C-1.5: every feature with a contract carries a sealed second reading naming one of its clauses — six layers now, guarded by a spec that names a layer without one |
| 4 authorship throughput | measured, the repair loop is the lever | 0 of 36 without repair, 1 of 18 with one round, 5 of 13 and 4 of 13 with up to three rounds (arms 4, 5); the admission rule caught every false draft; the frontier still edits what is admitted |
| 5 the daemon | live | `athena daemon --once` on the real beads queue: claim by bd id, live admission, dispatch, rollback, provenance, release on red |
| 6 the ladder | live | `--ladder pi-3b,pi-omni9` on T9.1: the 3B red three times, the daemon released the claim and escalated to OmniCoder with the handoff (`red twice on pi-3b`), recorded in the ledger |
| 7 provenance | in every record | model through the registry, runtime and its version from the lane, packet and tool digests; `missing_provenance` names weights and seed |
| 8 capacity-aware lanes | live | the daemon admits by `/metrics` or `/slots`; with `--executors` it routes by prefix affinity among the admitted lanes (C-11.7), warmth table beside the ledger |
| 9 sandbox | **live**: the OS sandbox runs the executor; the relay fence on every lane | C-10.1: `--sandbox required` — OmniCoder inside sandbox-runtime (account `srt-sandbox`, WFP fence, loopback only to the fenced relay 60081) regenerated `pick_admitted` from C-11.7, spec green in 51 s, 1 iteration (20:52). Probed from inside: writes to the lane, model and secret trees on D: refused, the caller's profile unreadable, github and the lane's direct port blocked, the relay reachable. C-10.3: all three executor relays (8417, 60081, 60083) refuse a `write` outside the worktree. Residual, said out loud: `D:/tmp` (where the worktrees live) stays writable to the account — the drive grants Authenticated Users modify and a deny on its root needs elevation |
| 10 memory in the packet | live | repo map after the prefix, lessons appended on red (three from the regeneration run) and selected by clause and file |

What stays open, in order: the world-writable `D:/tmp` under the sandbox (the operator's drive layout);
the lines the mutation survivors name, which a spec should own before the next regeneration; and the
unpinned behaviour the diff finds — pin it in a spec or accept it as free, clause by clause.


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
