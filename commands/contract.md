---
description: Query the requirement contract — coverage, what is left, and requirement/spec/code drift.
argument-hint: "[coverage|todo|drift|lint|pin|import|run] [path to contract.md]"
---

# /athena.contract — the requirement contract (v3.3 .. v3.5)

## 0. The two commands most of the time

```bash
python athena.py init features/my-feature --title "My Feature"   # scaffold, already wired
python athena.py check features/my-feature/contract.md        --front features/my-feature/plan.md --run --text          # the loop, one exit code
```

`check` folds everything below into one verdict and names the LEG that failed —
`specs_to_code` (is every requirement proved?) or `code_to_specs` (is the map still true,
and do those specs prove anything?). `--deep` adds mutation over the clauses that drifted;
`--strict` promotes wording findings and surviving mutants to blocking. Everything after
this section is the same loop taken apart, for when the verdict needs explaining.

`contract.md` holds numbered clauses with immutable ids; `scenarios.md` binds each clause to
an executable spec. That pairing makes three questions cheap enough to ask on every turn
instead of re-reading the codebase. Read `skills/contract-format/SKILL.md` before editing a
contract — the id and supersede rules are what all of this rests on.

Default paths: `contract.md`, its sibling `scenarios.md`, ledger `.athena/spec_ledger.json`.
Add `--text` for a human table, omit it for JSON (Hermes / CI).

## 1. Is the contract itself consistent?

```bash
python athena.py contract lint contract.md
```

Dangling supersede refs, cycles, withdrawn-and-superseded contradictions. Exit 1 on issues.

## 2. Which requirements have no executable spec?

```bash
python athena.py contract coverage contract.md --text
```

`uncovered` = live clauses nothing proves. `orphan_specs` = specs pointing at unknown or
withdrawn clauses. `redirected_specs` = specs still pointing at a superseded clause — the
reference resolves forward, but the successor needs its OWN proof, so it is not credited.
Add `--gate` in CI to exit 1.

## 3. Run the specs, then: what is left to implement?

```bash
python athena.py spec run scenarios.md -o .athena/spec_ledger.json     --skip-tag slow --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1   # fast lane: 47 specs in 2.1s
python athena.py contract todo contract.md --ledger .athena/spec_ledger.json --text
```

Every live clause lands in exactly one bucket — `unspecified` (write the spec), `red`
(implement; the failing run_cmds are in the payload), `unrun` (run them), `stale` (green, but
only against an older wording), `done`. `draft` clauses ride separately as `backlog`.

Filter the inner loop with `--clause C-3` or `--spec-id S3`.

## 4. Where did requirement, spec and code diverge?

```bash
python athena.py contract drift contract.md --ledger .athena/spec_ledger.json --text
```

- `spec_drift` — the clause moved after the spec was pinned to it
- `stale_proof` — the green was earned under an older clause version
- `missing_spec` / `extra_spec` — nothing proves a clause / a spec proves nothing real
- `unpinned` — advisory only (no pins = drift is undetectable, not divergent)

After reconciling, re-pin: `python athena.py contract pin scenarios.md --contract contract.md --write`

## 5. Line ownership — which requirement owns this line

```bash
python athena.py contract map contract.md --source lib                # full derive (~3 min / 98 specs)
python athena.py contract map contract.md --source lib --incremental  # only what drifted (~28 s / 12)
python athena.py contract owners lib/seams.py:230                     # -> C-5.8, C-5.9 + their text
```

Each clause is pinned to the CONTENT at the lines it owns, so editing elsewhere in the same
file costs nothing, and the drift list doubles as the work list for `--incremental`.

The map is DERIVED from clause -> spec -> run_cmd by running each spec alone under coverage,
so nobody annotates anything. It answers "I am about to change this line, what am I allowed
to break", and it splits a claimed file into code this contract owns, code another feature
owns, and code nothing reaches at all.

## 6. Gates + compile

```bash
python athena.py seam contract_bound plan.md --speckit off   # every live clause proved
python athena.py seam map_fresh      plan.md --speckit off   # the map still describes it
python athena.py compile plan.md --speckit off               # clause nodes + supersede edges
```

`map_fresh` fails closed on a map that is absent, pinned to another contract/spec version,
missing a live clause, or still holding a deleted one — a derived artifact nobody re-derives
answers with the confidence of a build product while pointing at lines two refactors old.

## Adding or changing a requirement

1. NEW requirement -> append a clause with the next free id (`draft` if not yet promised).
2. CHANGED requirement -> add a new clause, mark the old one `superseded-by <new id>`.
   Never edit a clause's meaning in place; never renumber.
3. Write/adjust the executable spec in `scenarios.md`, then `contract pin --write`.
4. `spec run` -> the clause is red until the code proves it.
5. `contract todo` is the work list; `contract drift` must come back `in_sync: true`.

## Worked example — this repo's own contract layer

`features/contract-layer/` carries `contract.md` (51 clauses, 48 live), `scenarios.md`
(48 specs, each a real pytest node), `plan.md` and a committed `spec_ledger.json`. It is the
frame applied to itself: `C-4.5` was superseded by `C-4.13` because running these very
reports on Athena exposed a bucket that answered "nothing left" while drift said otherwise.
