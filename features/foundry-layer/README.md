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

Research digest with sources: the session scratchpad `research_gaps_digest.md` (58 URLs);
the decision: `docs/adr/0009-the-foundry-wraps-oss-and-runs-itself.md`.

## Order of work (by leverage, from the digest)

1. C-1 and C-2: every later green becomes trustworthy, and the forge gets SWE-smith-style tasks.
2. C-3 and C-4: the loop runs unattended; lanes stop crashing under load.
3. C-5 and C-6: both need the verdict log the first two produce; provenance fields fixed
   before the log grows.
4. C-7, C-8, C-9, C-10: memory, regeneration, second-kind oracles, sandbox behind a flag.

## Measured

(Filled by the lanes' verdicts; the first tasks went to the vanilla 9B on 2026-09-25 at
19:58 and to OmniCoder-9B after its A/B against the vanilla weights.)
