# Contract Format — numbered clauses as the requirement root (v3.3)

## Rule: a clause id is allocated once and never reused

`contract.md` is the requirement registry. Every clause gets `C-<n>(.<n>)*`. Once written,
the id is frozen: never renumber, never reuse, never repurpose. Every reference in the repo
(`verifies:`, a bd label, a commit message, a review comment) is only as good as that rule.

## Rule: a requirement is never edited in place — it is superseded

Wording changed? Add a NEW clause and mark the old one:

```markdown
- **C-1.3** *(superseded-by C-1.4 C-1.5)* — WHEN a game starts THE SYSTEM SHALL set the score to zero.
- **C-1.4** *(supersedes C-1.3)* — WHEN a game starts THE SYSTEM SHALL set the score to zero.
- **C-1.5** *(supersedes C-1.3)* — WHEN a game starts THE SYSTEM SHALL set the multiplier to one.
```

`Contract.resolve("C-1.3")` now returns `(C-1.4, C-1.5)` — an old reference still lands
somewhere current, which is exactly what renumbering destroys. Declare the link on either
end; the parser reconstructs the other direction.

Typo fixes and re-wrapping are NOT changes: the version hashes whitespace-normalized text.

## Statuses

| status | meaning | owed a passing spec? |
|---|---|---|
| `active` (default) | live requirement | **yes** — gate fails without one |
| `draft` | written down, not yet promised | no — shows up as `backlog` in `todo` |
| `superseded` | replaced by >=1 successor (implied by the link) | no |
| `withdrawn` | dropped; a spec still pointing here is an orphan | no |

## Syntax

- Group heading: `## C-1 — Initial state` (grouping only; identity is the clause id).
- Clause: `- **C-1.1** *(markers)* — WHEN <event> THE SYSTEM SHALL <response>.`
- Markers, `;`-separated: `draft`, `withdrawn`, `superseded-by <ids>`, `supersedes <ids>`.
- Sub-bullets: `- status:`, `- supersedes:`, `- superseded-by:`, `- tags:`, `- note:`.
- An indented line that is none of those CONTINUES the clause text (wrapped prose is joined).

## Binding: one clause, one or more executable specs

`scenarios.md` binds a spec to a clause and pins the wording it was written against:

```markdown
### S1.1 — new game places the snake
- **verifies:** C-1.1
- **pins:** 4f1c2b9ad3e77a10          <- written by `athena contract pin --write`
- **run_cmd:** `pytest tests/test_snake_body.py::test_initial_placement -q`
- **Given** ... - **When** ... - **Then** ...
```

Re-pin whenever a clause is superseded or a spec is rewritten. An unpinned spec is legal —
drift simply cannot be detected for it.

## The three questions (each a linear scan, no LLM)

```bash
athena contract coverage contract.md          # which clauses have no executable spec
athena spec run scenarios.md                  # -> .athena/spec_ledger.json (red/green)
athena contract todo contract.md --ledger ... # unspecified / red / unrun / stale / done + draft
athena contract drift contract.md --ledger ... # spec_drift / stale_proof / missing / extra
```

`stale` and `stale_proof` are the ones no test suite can tell you: every spec is green, but
it is proving an older wording of the requirement.

## Gate

`athena seam contract_bound <front>` fails closed when a live clause has no spec or a spec
names an unknown/withdrawn clause. Wire it before `compile` in CI.

## Migration (never renumber)

```bash
athena contract import spec.md -o contract.md   # keeps R1.1 as R1.1 — refs keep resolving
```

## In the graph

A pinned contract compiles to `kind:clause` nodes under the spec node, `related` edges along
the supersede chain, and re-roots each scenario's `validates` edge from the spec document
onto the clause it actually proves. With no contract attached the compiler output is
byte-identical to v3.1 — adoption is per project.
