# The contract layer, contracting itself

This folder is the frame's own requirement contract. Every rule the contract layer enforces
was written here first, as a numbered clause, and is checked here by an executable spec that
runs in this repo's test suite. If you want to know what the layer does, read `contract.md`.
If you want to know whether it does it, run the loop at the bottom of this page.

An audit read these files with no access to the code and reconstructed the design correctly —
then said the honest part: everything about *how to use it* had to be inferred, because no
artifact said it in one place. This page is that place.

---

## The eight artifacts

| File | Written by | Answers |
|---|---|---|
| `contract.md` | an author | declared obligations — numbered clauses, ids never reused |
| `scenarios.md` | an author; `pins:` by the tool | runnable checks bound to clauses |
| `plan.md` | a human | what work carries which spec |
| `spec_ledger.json` | `athena spec run` | which specs were green, and when |
| `clause_map.json` | `athena contract map` | execution reach attributed through bound specs |
| `judge_corpus.json` | `athena judge corpus` | labelled spec pairs for measuring a judge |
| `judge_decisions.json` | `evals/judge_local.py` | what one judge said about them |
| `clauses.needs.json` | `athena contract export` | the index another repository references |

The first three are authored declarations requiring review. The last five are
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
athena contract sources  <contract> --text   # where each clause came from (v3.10)
athena lessons rerun     <contract> --text   # rerun the proofs of every lesson (v3.10)
athena gate --text                           # every contract in the repo, the cheap lane (v3.10)
```

`athena contract outline --text` prints each clause group, its clause statuses, how many live
clauses have declared spec bindings, and the execution reach recorded in its map. A binding
may name a check that has never run; this outline does not assess execution or semantics.
The `home` and `shared` rankings help navigation and do not establish architecture.

## Living apart from the code

A contract that shares a checkout with its code can leave everything implicit. One that lives
in a docs repository, a wiki or a vault cannot — so three links are made explicit, each using
a notation that already exists rather than a new one.

**Clause to document.** A clause may cite an ADR, a runbook, a standard. The mechanism and the
word are Doorstop's: the reference carries the fingerprint of what was reviewed, and a target
that changed since is a **suspect link**.

```markdown
- **C-9.22** — WHEN a spec is run under coverage THE SYSTEM SHALL ...
  - see: docs/adr/0007-branch-evidence.md@3f9a1c02b7e3d5a8
  - see: https://coverage.readthedocs.io/en/latest/branch.html
```

```bash
athena contract refs contract.md --text       # suspect / broken / unpinned / external
athena contract refs contract.md --write      # re-pin: that is a REVIEW, read the diff
```

**Code to clause.** The notation is StrictDoc's; what is ours is refusing to believe it. A
marker names a clause, and the clause map must show that clause actually reaching the lines
the marker claims — otherwise the annotation is decoration and the report says `unbacked`.

```python
def partial_lines(files, branches):
    """...

    @relation(C-9.22, scope=function)
    """
```

```bash
athena contract markers contract.md --map clause_map.json --source lib
```

Scopes are `line`, `function`, `class`, `range_start`/`range_end`, `file`. A marker shown
inside backticks or a fenced block is a mention, not a marker — the same distinction the
wording critique already draws.

**Another repository referencing us.** Nobody clones anything: the contract publishes an index
and the other side consumes it, exactly as sphinx-needs and intersphinx do.

```bash
athena contract export contract.md --project nexus-athena -o clauses.needs.json
athena contract export contract.md --format oft        # OpenFastTrace specobject XML
```

The index records whether each clause has a declared spec binding, the lines reached in the
supplied map, and lines with unobserved branch arms. It does not receive an execution ledger
and cannot establish successful execution, intent fidelity, check adequacy or code correspondence.

The `needs.json/2` format replaces the misleading `proved` field with `spec_bound`.
The `athena.outline/2` format replaces `proved` and `unproved` with `bound` and `unbound`;
`bound` counts only live clauses, so bound draft clauses cannot inflate the displayed ratio.
There are no proof aliases. Consumers of version 1 must migrate these field names and their
interpretation; saved exports must be regenerated. Legacy `owns_*` and `half_proved*` fields
remain coverage observations, as the output limitations state, and confer no semantic ownership.

**Which codebase a map is about.** Recorded as a package URL (`pkg:github/owner/repo`), derived
from the git remote by default. A map naming a different project fails the freshness gate — an
audit once had this repo's map silently judging a scaffolded project elsewhere. Version is
ignored on purpose: the per-clause digests already answer whether the code moved.

## Two evidence measures: branch reach and mutation sensitivity

Counting specs measures nothing — this contract had exactly one per clause for months. Counting
*owned lines* over-claims: the median clause "owns" 250 of the 1724 lines in the map, because
coverage credits everything its test executed on the way in. So depth is measured twice:

**Branch evidence (cheap, always on).** The map runs coverage with `--branch`, so a line whose
other arm no spec of that clause ever took retains the legacy label **half-proved**, meaning
partial observed branch coverage. The historical measurement was **231 of 1724 attributed
lines (13%)**. Observations combine per clause: when its specs take opposite arms, that
branch is no longer partial. Both arms can execute while the returned result is wrong;
complete branch reach does not establish a requirement or the adequacy of its assertions.

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
anything.

The first run on this repo found **7 survivors out of 17 mutants with every spec green** —
guards whose other arm nothing exercised, in `check.py`, `clause_map.py`, `contract_report.py`,
`coverage_backed.py` and `scenario_parser.py`. Closing them meant strengthening seven specs,
after which the same sweep scores **11 killed of 14**. What remains is two lines of
`bd_client.py` whose guard the real-`bd` spec cannot reach without inventing a command shape:
the argv rewriter needs a unit-level spec, not a bigger integration one.

One of the seven took two attempts, and the second attempt is the lesson: the assertion first
landed in a NEARBY test that no clause binds, so it passed, proved nothing to the frame, and
the mutant lived on. A test outside the contract is not evidence the contract can use.

## The judge is a local model, and it is not a gate

`athena judge` is a **pilot** whose score remains advisory. The corpus preserves declared
baseline labels and mechanically transforms their specs (drop an assertion, weaken a check,
or bind it to another clause). Corpus construction does not execute or certify the baseline.
The legacy labels `proves` and `vacuous` are corpus categories; reports carry their declared
basis and `semantic_validity: NOT_ASSESSED`. Recall and false-reject rates measure agreement
with those labels. A faulty oracle labelled `proves` can yield perfect label agreement.

Running it needs an OpenAI-compatible endpoint serving a local model:

```bash
python evals/judge_local.py --corpus features/contract-layer/judge_corpus.json \
    --endpoint http://127.0.0.1:8001 --model <served-model-id> \
    --out features/contract-layer/judge_decisions.json --resume
athena judge eval --corpus ... --decisions ...        # recall / false rejects vs thresholds
```

The thresholds (recall ≥ 0.95, false rejects ≤ 0.02) were fixed **before** the first run and
live in `lib/judge.py`. Eligibility from these numbers is relative to the declared corpus;
it does not establish intent fidelity, check adequacy or code correspondence. The advisory
policy and score calculation are unchanged; semantic labels require separate review.

### What the measurement says so far

A 9B local model, unmuzzled (no token cap, no forced JSON grammar), takes about a minute per
pair — the full 595-pair corpus is roughly ten hours of GPU time on one RTX 3060. Over the
first **411 scored pairs**: recall **0.954** (bar: 0.95), false rejects **0.469** (bar: 0.02).
These are archived agreements with that corpus's declared labels, not independently
established rates of semantic error. The original results are retained without regrading.

- **Recall is not the problem, false rejects are.** The degraded halves get caught — weakest
  is the subtlest defect, `weakened`, at 0.87. The measured disagreement is calling a baseline
  labelled `proves` vacuous, for nearly half of those labels. The recurring reason is "the
  test covers one case, the requirement is universal", which no single unit test satisfies;
  a mutation sweep supplies additional finite evidence, not a universal semantic answer.
- **A partial run is biased, so it is never eligible.** The judge thinks about twice as long
  when there is nothing to refute (median 259s on a proving pair against 121s on a degraded
  one), so timeouts fall on the good half: three of the first four were proving pairs, which
  are only a fifth of the corpus. `score()` reports the unjudged count per label and refuses
  eligibility while any remain (C-10.24).
