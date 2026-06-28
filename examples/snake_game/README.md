# Showcase: "Classic Snake Game" through the full Athena frame

A single, real, end-to-end run of the **Claude Code plugin** (the canonical Spec-Kit
agent, driven headless via `claude -p`) over one 4-sentence intent. No implementation —
this is a **plan-quality probe**: what does the frame produce after every stage, and how
exhaustive is it?

## Input (the ONLY input)

> Build a classic Snake game on a rectangular grid. The snake moves one cell per tick in
> its current direction; the player steers with the arrow keys (cannot reverse 180° into
> itself). Food spawns at a random empty cell; eating it grows the snake by one segment and
> increases the score. The game ends when the snake hits a wall or its own body. On game
> over the final score is shown and the player can restart.

## Stages run (the whole pipeline)

`intent → /specify → /clarify → CRISP design → /athena.scenarios → CRISP plan → compile`

| Stage | Artifact | What it produced |
|-------|----------|------------------|
| `/specify` + `/clarify` | [`spec.md`](spec.md) | 12 user stories, **24 edge cases**, **44 functional requirements** (FR-001…FR-044), 8 success criteria, **31 EARS criteria** (R1.1…R13.2), 12 clarifications folded back as FRs |
| CRISP design | [`design.md`](design.md) | pure-core/shell split, deque+set model, move-ordering decision, RNG seam; every decision traced to FR/EC and to mitigating scenarios; 5 open risks |
| `/athena.scenarios` | [`scenarios.md`](scenarios.md) | **31 Given-When-Then scenarios**, 1:1 with the EARS criteria, each with `verifies:` back-link + an executable `run_cmd` (pytest) |
| CRISP plan | [`plan.md`](plan.md) | **8 phases, 27 tasks**, each with an executable `success_check`, `files`, `verifies`, and a phase DAG (`Depends on:`) |
| compile | [`compiled_graph.txt`](compiled_graph.txt) | deterministic `lib/plan2beads` → **8 epics + 27 issues + 26 dependency edges = 61 bd commands**, parser-valid |

## Why it's "exhaustive"

The frame caught the **non-obvious** edge cases that separate a correct Snake from a toy:

- **EC-3** — two quick turns within one tick (the classic reversal exploit) → reversal
  checked against the *committed* heading, not the last-buffered key.
- **EC-9 / EC-10** — legal tail-chase vs. growing-tail collision → explicit move ordering
  (drop tail before the head collision check, but only on non-growing ticks).
- **EC-8** — eating the food on the last empty cell is a **win**, not a failed food spawn.
- **EC-11 / EC-12** — wall off-by-one (last in-bounds cell is legal) and corner death
  (a move that is both a wall and a self hit yields exactly one game-over).

Every one of those flows forward: edge case → FR → EARS criterion → GWT scenario with an
executable test → task whose `success_check` runs that test. `success_check = requirement
proved`, not merely "a test passed."

## Honest limitations of THIS run

- The bare canonical `plan.md → bd` path does **not** materialize the task→scenario
  `verifies:` edges as graph edges (the canonical `lib/plan_parser` has no `verifies`
  field — that binding lives in the Spec-Kit `tasks.md` + `.athena/seams.jsonl` pinning
  path, v3.1). The links are present and complete in `plan.md`/`scenarios.md` **text**
  (31 scenarios ↔ 31 EARS, 1:1); they are just not compiled into bd edges here.
- No spec/scenario provenance **nodes** were emitted because this standalone demo did not
  pin `spec_version`/`scenario_version` via `seams.jsonl`.

## Run cost (unrestricted, no throttle)

Single headless `claude -p` session: 18 turns, ~11 min, 54k output tokens, ≈ $2.65.
