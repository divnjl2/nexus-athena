# The contract layer, contracting itself

This folder is the frame's own requirement contract. Every rule the contract layer enforces
was written here first, as a numbered clause, and is proved here by an executable spec that
runs in this repo's test suite. If you want to know what the layer does, read `contract.md`.
If you want to know whether it does it, run the loop at the bottom of this page.

An audit read these files with no access to the code and reconstructed the design correctly —
then said the honest part: everything about *how to use it* had to be inferred, because no
artifact said it in one place. This page is that place.

---

## The seven artifacts

| File | Written by | Answers |
|---|---|---|
| `contract.md` | a human | what is guaranteed — numbered clauses, ids never reused |
| `scenarios.md` | a human; `pins:` by the tool | how each clause is proved — one runnable command per clause |
| `plan.md` | a human | what work carries which spec |
| `spec_ledger.json` | `athena spec run` | which specs were green, and when |
| `clause_map.json` | `athena contract map` | which lines of which files each clause owns |
| `judge_corpus.json` | `athena judge corpus` | labelled spec pairs for measuring a judge |
| `judge_decisions.json` | `evals/judge_local.py` | what one judge said about them |

The first three are written by hand and are the only source of truth. The last four are
**derived** — delete any of them and one command rebuilds it. That asymmetry is the design:
a derived artifact may never be edited, and a hand-written one may never be inferred.

## The contract format, in one screen

```markdown
## C-3 — Executable specs and the ledger          <- group heading, human grouping only

- **C-3.1** — WHEN a spec is run THE SYSTEM SHALL record its exit code.
- **C-3.10** *(draft)* — WHEN a run_cmd contains a shell metacharacter ...
- **C-4.5** *(superseded-by C-4.13)* — WHEN nothing is left ...
- **C-1.9** *(withdrawn)* — WHEN ids are compared ...
  - note: free-form prose. Never normative — the SHALL sentence is the whole obligation.
```

- **The id is the identity.** `C-3.2` is allocated once and never reused, so a reference
  written months ago keeps resolving. A requirement that changes is **superseded** by a
  successor, never edited in place; naming two successors *branches* it, and `resolve()`
  follows the chain forward.
- **Four statuses:** `active` (the default, unmarked), `draft` (stated, not yet owed a
  proof), `superseded` (replaced — still readable, no longer live), `withdrawn` (retracted).
  Only live clauses are owed an executable spec.
- **One clause, one obligation,** in EARS shape (`WHEN <trigger> THE SYSTEM SHALL <act>`).
  `athena contract lint --strict` refuses the rest: two obligations joined by "and", vague
  words with no threshold, an implementation named where behaviour belongs.

A spec binds to a clause by id and pins the clause text it was written against:

```markdown
### S3.1 — the ledger records the exit code
- **verifies:** C-3.1
- **pins:** 9f1c4a02b7e3d5a8          <- sha16 of the clause text; the tool writes it
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_the_ledger_records_it -q`
- **Given** / **When** / **Then** ...
```

When the clause text changes, its hash changes, and the pin no longer matches: that is
`stale_proof` drift, and it is how the frame notices that a proof is proving the old wording.

## Running the loop

```bash
python athena.py check features/contract-layer/contract.md \
    --front features/contract-layer/plan.md \
    --map features/contract-layer/clause_map.json --run --text
```

One verdict, one exit code, three legs:

- **contract** — do the clauses parse, are the ids sane, is the wording checkable
- **specs → code** — is every live clause proved by a spec that is bound, pinned and green
- **code → specs** — is the line map still true of the code, and do those specs prove
  anything at all (that last one is `athena mutate`)

A leg that produced no evidence reports `INCOMPLETE`, never `PASS`. A named-but-missing
input is a hard failure — silence is not proof, which is the whole point of the layer.

## The other commands

```bash
athena contract outline  <contract> --text   # the shape: what each group owns, derived
athena contract coverage <contract>          # which clauses have no spec
athena contract todo     <contract>          # what is left to implement
athena contract drift    <contract>          # where requirement, spec and proof disagree
athena contract map      <contract> --source lib --incremental   # rebuild line ownership
athena contract owners   lib/judge.py:271    # which clauses may I break by editing this
athena spec run          <scenarios> --jobs 12                   # run every spec
athena mutate            <contract> --only exclusive+half-proved   # do the specs notice
athena init              --dir features/my-feature               # start a new contract
```

`athena contract outline --text` is the fastest way in: it prints each clause group, how many
of its clauses are live and proved, and which modules its specs actually execute — the
architecture, measured rather than claimed.

## How deep is a proof? Two measures, cheap then expensive

Counting specs measures nothing — this contract had exactly one per clause for months. Counting
*owned lines* over-claims: the median clause "owns" 250 of the 1724 lines in the map, because
coverage credits everything its test executed on the way in. So depth is measured twice:

**Branch evidence (cheap, always on).** The map runs coverage with `--branch`, so a line whose
other arm no spec of that clause ever took is recorded as **half-proved**. On this contract
that is **231 of 1724 owned lines (13%)**. Partiality belongs to the clause, not the spec: if
one spec takes the true arm and another the false one, the branch is proved — which is the
first real reason to write more than one spec per clause (the report layer always accepted it).

**Mutation (expensive, aimed).** Break an owned line and see whether any bound spec goes red.
The selector is part of the measure, because a full sweep is unaffordable and a line owned by
twenty clauses costs twenty spec runs:

```bash
athena mutate contract.md --map clause_map.json --ledger spec_ledger.json \
    --only exclusive+half-proved     # 1724 owned -> 231 half-proved -> 26 lines
```

`exclusive` keeps lines exactly one clause owns (one spec decides, no attribution argument);
`half-proved` keeps the branch layer's suspects; `+` intersects them. Specs the ledger already
records as red are disqualified as witnesses — a spec failing on clean source cannot notice
anything. The first such run on this repo: **17 mutants, 7 killed, 7 survived**, and the seven
survivors are guards whose other arm nothing exercises — in `check.py`, `clause_map.py`,
`contract_report.py`, `coverage_backed.py`, `scenario_parser.py`. Every spec was green.

## The judge is a local model, and it is not a gate

`athena judge` is a **pilot**, not part of `check`. The corpus is built mechanically — take
pairs this repo already proves, degrade the spec in a known way (drop the assertion, swallow
the exception, bind it to the wrong clause), and label the result. A judge is then asked to
find the broken half.

Running it needs an OpenAI-compatible endpoint serving a local model:

```bash
python evals/judge_local.py --corpus features/contract-layer/judge_corpus.json \
    --endpoint http://127.0.0.1:8001 --model <served-model-id> \
    --out features/contract-layer/judge_decisions.json --resume
athena judge eval --corpus ... --decisions ...        # recall / false rejects vs thresholds
```

The thresholds (recall ≥ 0.95, false rejects ≤ 0.02) were fixed **before** the first run and
live in `lib/judge.py`. Nothing promotes the judge from advisory to gate except those
numbers. The deterministic mutation runner is the part that works today; the judge is the
part being measured.

### What the measurement says so far

A 9B local model, unmuzzled (no token cap, no forced JSON grammar), takes about a minute per
pair — the full 595-pair corpus is roughly ten hours of GPU time on one RTX 3060. Over the
first **411 scored pairs**: recall **0.954** (bar: 0.95), false rejects **0.469** (bar: 0.02).

- **Recall is not the problem, false rejects are.** The degraded halves get caught — weakest
  is the subtlest defect, `weakened`, at 0.87. The failure mode is calling a *valid* spec
  vacuous, and it does that to nearly half of them. The recurring reason it gives is "the
  test covers one case, the requirement is universal", which no single unit test satisfies;
  the deterministic answer to that same question is the mutation sweep above.
- **A partial run is biased, so it is never eligible.** The judge thinks about twice as long
  when there is nothing to refute (median 259s on a proving pair against 121s on a degraded
  one), so timeouts fall on the good half: three of the first four were proving pairs, which
  are only a fifth of the corpus. `score()` reports the unjudged count per label and refuses
  eligibility while any remain (C-10.24).
