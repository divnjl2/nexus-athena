# Design Discussion: Classic Snake Game

> CRISP stage 3. Derived-from `spec.md`. This is the lowest-cost point for direction
> changes. The stage normally asks 3–5 questions and waits; since this run is
> non-interactive, each question is **stated and then answered** with a default + rationale.

## Current State

This is a greenfield feature — the workspace `D:\tmp\claude\snake_frame` contains only the
planning artifacts produced by this pipeline (`spec.md`, and this file). There is no
existing Snake implementation, no game engine, and no shared UI/render code to reuse, so
there are no in-repo `file:line` patterns to follow or avoid. The design therefore
establishes conventions rather than inheriting them.

Constraints inherited from the spec (the frozen contract):
- Tick-driven, single-cell-per-tick movement (FR-006, FR-007).
- Deterministic, seedable randomness for food (FR-042) — required for testable scenarios.
- Solid walls, 4-direction movement, grow-only snake (FR-039, FR-040).
- A clean separation between *game rules* (testable) and *presentation* is implied by the
  Success Criteria (SC-6 determinism, SC-2/SC-3 fuzzable invariants), which can only be met
  cheaply if the rules run headless.

## Desired End State

A playable, single-player Snake game plus a headless, fully unit-testable rules engine.
Verification of "correct":
- Every EARS criterion in `spec.md` has a passing Given-When-Then scenario (`scenarios.md`)
  backed by an executable `success_check` in `plan.md`.
- The engine is deterministic under a fixed seed + fixed input script (SC-6), so scenarios
  assert exact board states tick-for-tick.
- A thin UI layer renders the engine state and forwards keystrokes; the UI is smoke-tested
  but the *rules* carry the behavioral test weight.

## Patterns to Follow

No in-repo patterns exist (greenfield). The design adopts these conventions, to be applied
consistently by every downstream task:
- **Pure-core / imperative-shell.** All game rules live in a side-effect-free core that
  takes `(state, input, tick)` and returns the next state. I/O (keyboard, screen, wall
  clock) lives only in the shell. This is what makes SC-6 and the fuzz criteria cheap.
- **Value objects for geometry.** `Coord` and `Direction` are immutable; `Direction` knows
  its opposite and its delta. This localizes the reversal rule (FR-012, FR-016) to one place.
- **Explicit state machine.** A single `GameStatus` enum (`RUNNING | PAUSED | GAME_OVER |
  WON`) gates every transition, so "freeze after game over" (FR-028) and "ignore restart
  during play" (FR-034) are structural, not scattered `if` checks.
- **Seam for randomness.** Food placement receives an injected RNG so tests pin the seed
  (FR-042) and production uses an unpredictable one.

*Anti-pattern to avoid:* spreading collision/reversal/tail logic across the render loop.
Ticking and rules must never depend on real time inside the core.

## Design Decisions

1. **Pure headless engine + thin UI adapter** — chosen over a UI-coupled game loop.
   Why: the spec's determinism (SC-6) and zero-violation fuzz criteria (SC-2, SC-3) are
   only affordable if rules run without a screen or clock. The UI becomes a replaceable
   adapter over `Game.tick()` / `Game.handle_input()`.
2. **Snake as a double-ended queue of `Coord` + an occupied-cell set** — chosen over a
   list-only or a per-cell grid-matrix representation. Why: O(1) head-append / tail-pop for
   movement, and an O(1) membership set makes the self-collision check (FR-024) and the
   "empty cells" enumeration for food (FR-020) fast and obviously correct.
3. **`pending_direction` buffer resolved at tick start, reversal checked vs committed
   heading** — chosen over applying each keypress immediately. Why: directly implements
   FR-015/FR-016 and kills the two-quick-turns reversal exploit (EC-3) in one place.
4. **Move order: compute next head → resolve grow/no-grow → drop tail if not growing →
   collision check against the resulting body** — chosen over checking collisions before
   moving the tail. Why: this is the only ordering that makes legal tail-chase (EC-9,
   FR-025) and growing-tail collision (EC-10, FR-026) both correct without special cases.
5. **Win detected as `len(snake) == grid.width * grid.height`, checked before food respawn**
   — chosen over treating "no empty cell for food" as an error. Why: implements EC-8 / FR-027
   so filling the board is a victory, not a failed spawn.

## What We're NOT Doing

- No speed-up / difficulty curve as the snake grows (FR-037 fixes constant speed).
- No wrap-around walls (FR-039); no diagonal movement (FR-040).
- No persistence: no saved high scores, profiles, or settings files (FR-043).
- No multiplayer, network, AI opponent, or replays.
- No multiple simultaneous food items, power-ups, obstacles, or portals.
- No window/focus-loss handling in the rules engine (EC-24, out of scope); the shell may
  pause on blur but the engine does not depend on it.
- No mouse/touch input; keyboard only (FR-043).
- No configurable themes or sound.

## Design Questions (stated and self-answered)

**Q1 — Engine/UI split: pure-core or UI-coupled loop?**
*Answer: Pure headless core + thin adapter.* Rationale: it is the only structure that makes
the spec's determinism and fuzz invariants testable at low cost; a UI-coupled loop would
force the test suite to drive a screen and a clock. (Drives Decision 1.)

**Q2 — UI/runtime technology for the shell?**
*Answer: Python 3 standard library, with a text/terminal renderer as the default shell and
the core importable without any UI dependency.* Rationale: zero third-party install for the
core and tests (`pytest` only); a terminal renderer is sufficient for a 20×20 grid and keeps
the playable surface trivial. A richer renderer (e.g. a windowed GUI) can be added later
behind the same adapter seam without touching the engine.

**Q3 — Snake & board data structures?**
*Answer: `deque[Coord]` for ordered segments + a `set[Coord]` occupancy index; the grid is
implicit (width × height bounds), not a materialized matrix.* Rationale: O(1) move and O(1)
collision membership; empty-cell enumeration for food is `all_cells − occupied`. (Decision 2.)

**Q4 — How is input timing reconciled with ticks?**
*Answer: a single `pending_direction` slot updated by `handle_input`, consumed at the start
of each tick, with the reversal test taken against the last committed heading.* Rationale:
deterministic, matches FR-014/FR-015/FR-016, and closes the EC-3 exploit. (Decision 3.)

**Q5 — How is randomness made testable while still random in play?**
*Answer: inject an RNG (a `random.Random` instance) into the engine; tests pass a fixed
seed, production passes a default-seeded instance.* Rationale: satisfies FR-042 and SC-6
without a global mutable random source. Per the stdlib note, `random` is fine here because
food placement is a game mechanic, not a security/token context. (Decision 5.)

## Open Risks

- **R-A — Tail-chase ordering bug.** The most error-prone area; if collision is checked
  before the tail is removed, legal tail-chase (EC-9) is misreported as a loss. Mitigated by
  Decision 4 and dedicated scenarios S8.1/S8.2.
- **R-B — Reversal exploit via buffered double-turn (EC-3).** If the reversal test is taken
  against `pending_direction` instead of the committed heading, the snake can fold. Mitigated
  by Decision 3 and scenario S4.2/S13.2.
- **R-C — Terminal input latency / key-repeat.** Real terminals deliver key-repeat and may
  buffer; the shell must collapse repeats to one pending direction per tick (EC-4, EC-5).
  This is a shell concern, smoke-tested only; the core is unaffected.
- **R-D — Win-state performance.** Enumerating empty cells naively on a nearly-full board is
  O(W·H) per food; acceptable at 20×20 but noted if the grid is later enlarged.
- **R-E — Non-blocking keyboard reads across OSes.** Terminal raw-mode input differs on
  Windows vs POSIX; isolated to the shell adapter so it never blocks engine tests.
