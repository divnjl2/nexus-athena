# Specification: Classic Snake Game

> Spec-Kit `/specify` output — the logical root of the provenance graph.
> Owns **what + why** only. No technology, framework, or implementation detail.
> EARS acceptance criteria map 1:1 to scenarios (`S<requirement#>.<index>`).

## Summary

A single-player Snake game played on a rectangular grid. A snake of connected cells
advances one cell per fixed tick in its current heading. The player steers with the four
arrow keys but can never reverse 180° into its own neck. Food appears on a random empty
cell; eating it grows the snake by one segment and raises the score. The run ends in a
**loss** when the head leaves the grid or enters its own body, and in a **win** when the
snake fills every cell. On game over the final score is shown and the player may restart.

---

## User Scenarios (User Stories)

- **US-1 — Start a game.** As a player, I start a new game and see the snake and a single
  food item placed on the grid with my score at zero, so I can begin playing immediately.
- **US-2 — Watch the snake move.** As a player, the snake advances on its own at a steady
  pace in its current direction, so the game has continuous motion without my input.
- **US-3 — Steer the snake.** As a player, I press the arrow keys to turn the snake left,
  right, up, or down, so I can navigate toward food and away from danger.
- **US-4 — Be protected from instant self-reversal.** As a player, when I press the key
  opposite my current heading, the snake keeps going instead of folding back onto itself,
  so a single misclick does not instantly kill me.
- **US-5 — Eat food and grow.** As a player, when the snake's head reaches the food, the
  snake grows by one segment and my score increases, so I am rewarded for skillful play.
- **US-6 — See food respawn.** As a player, after I eat food a new food appears somewhere
  empty, so play continues and the challenge escalates as the snake lengthens.
- **US-7 — Lose on a wall hit.** As a player, when I steer the head into a wall the game
  ends, so the grid boundary is a real constraint.
- **US-8 — Lose on a self hit.** As a player, when the head runs into the snake's own body
  the game ends, so the growing tail becomes the central hazard.
- **US-9 — Win by filling the grid.** As a player, if I grow the snake until it occupies
  every cell, I win the game, so there is a definitive victory condition.
- **US-10 — Review my final score.** As a player, when the game ends I see my final score
  on screen, so I know how well I did.
- **US-11 — Restart.** As a player, after game over I can start a fresh game with one
  action, so I can play again without relaunching anything.
- **US-12 — Pause and resume.** As a player, I can pause the game and resume it later,
  so I can step away without losing my run. *(clarified default — see Clarifications.)*

---

## Edge Cases

Each edge case below is something a competent implementation MUST handle deliberately.

- **EC-1 — Grid completely full.** The snake grows until no empty cell remains. There is
  nowhere to spawn food. This is treated as a **win**, not a crash or a stuck state.
- **EC-2 — Simultaneous opposite key.** The player presses the key directly opposite the
  current heading. The reversal MUST be rejected; the snake continues straight.
- **EC-3 — Two quick turns within one tick (reversal exploit).** While moving right, the
  player rapidly presses Up then Left before the next tick. Naively, the buffered "Left"
  would reverse into the neck. The reversal check MUST be evaluated against the
  **committed direction of travel**, not the last-buffered key, so this cannot fold the
  snake back on itself.
- **EC-4 — Rapid key presses within one tick.** Several arrow presses occur between two
  ticks. Only the **last valid (non-reversing)** input is applied on the next tick; the
  rest are discarded. No input queue accumulates a backlog of turns.
- **EC-5 — Holding a key down (auto-repeat).** OS key-repeat sends many identical events.
  This produces at most one direction change per tick and never accelerates the snake.
- **EC-6 — Pressing the current direction.** Pressing the key equal to the current heading
  is a no-op; the snake keeps moving in that direction.
- **EC-7 — Food spawns when the board is nearly full.** Exactly one empty cell remains.
  The new food MUST land on that single empty cell — never on a snake-occupied cell.
- **EC-8 — Eating the food on the last empty cell.** Eating fills the final empty cell.
  The system MUST declare a **win** instead of attempting (and failing) to spawn food.
- **EC-9 — Legal tail-chase.** When the snake is NOT growing, the tail vacates its cell on
  the same tick the head advances. The head moving into the cell the tail is leaving is a
  **legal** move, not a self-collision.
- **EC-10 — Tail-chase while growing.** When the snake IS growing this tick (it just ate),
  the tail does NOT vacate. The head moving into the still-occupied tail cell IS a
  self-collision and ends the game. Ordering of grow vs. tail-removal MUST be explicit.
- **EC-11 — Wall off-by-one.** Moving onto the last in-bounds cell along an axis is legal.
  Only the step that would place the head **beyond** the boundary is a loss.
- **EC-12 — Corner death (wall and self at once).** A move that is simultaneously a wall
  hit and a self hit produces exactly one game-over, not two, and the game still freezes.
- **EC-13 — Input during game over.** After the game ends, gameplay keys (arrows, pause)
  do nothing. Only the restart action has effect.
- **EC-14 — Restart during active play.** Pressing the restart key while the game is still
  running has no effect; restart only acts from the game-over/won state.
- **EC-15 — Repeated restarts.** Restarting multiple times in a row always yields a clean,
  fully reset initial state, including a freshly randomized food placement.
- **EC-16 — Direction input before the first tick.** A turn pressed before the first tick
  elapses is honored on that first tick (if non-reversing).
- **EC-17 — Pause on a tick boundary.** Pausing exactly as a tick is due MUST not advance
  the snake while paused and MUST not "owe" a skipped tick on resume.
- **EC-18 — Input while paused.** Arrow presses while paused do not move the snake; on
  resume the snake continues from the exact paused state.
- **EC-19 — Two foods never coexist.** At every moment of active play there is exactly one
  food on the board.
- **EC-20 — Score monotonic & non-negative.** The score starts at zero, only ever
  increases, and is never negative.
- **EC-21 — Minimum playable grid.** The grid MUST be large enough to hold the initial
  snake with room to move; an undersized configuration is rejected at start, not mid-play.
- **EC-22 — Length-1 reversal edge.** If the snake were ever length 1 it has no neck, so a
  reversal is physically harmless; the reversal rule is defined to be a no-risk no-op then.
  (Given the initial length and grow-only rule, the snake is always length ≥ initial.)
- **EC-23 — Eat then face a wall on the next tick.** Eating at a cell adjacent to the wall
  is legal; the loss only occurs on the subsequent tick if the player drives into the wall.
- **EC-24 — Window/focus loss.** Losing input focus is out of scope for game logic; the
  engine's behavior is defined purely by ticks and delivered inputs. *(See Out of Scope.)*

---

## Functional Requirements

### Grid & initial state
- **FR-001** — System MUST present a rectangular grid of fixed width (columns) and height
  (rows) for the duration of a game.
- **FR-002** — System MUST place the snake at a defined starting cell sequence with a
  defined initial length at the start of every game.
- **FR-003** — System MUST place exactly one food item on a uniformly random empty cell at
  the start of every game.
- **FR-004** — System MUST set the score to zero at the start of every game.
- **FR-005** — System MUST set the snake's heading to a defined initial direction at the
  start of every game.

### Movement & timing
- **FR-006** — System MUST advance the snake exactly one cell in its current heading on
  each game tick.
- **FR-007** — System MUST advance ticks at a constant interval (a fixed game speed).
- **FR-008** — System MUST represent the snake as an ordered sequence of occupied cells
  from head to tail.
- **FR-009** — On a tick where no food is eaten, System MUST move the head forward by one
  cell and remove the tail cell, keeping the snake's length unchanged.
- **FR-010** — When no directional input is pending, System MUST continue moving in the
  current heading on each tick.

### Steering & direction rules
- **FR-011** — System MUST accept the four arrow keys (Up, Down, Left, Right) as the
  intended heading.
- **FR-012** — System MUST reject any input that is the direct 180° reversal of the
  current committed heading and continue straight.
- **FR-013** — System MUST ignore keys that are not mapped game controls and retain the
  current heading.
- **FR-014** — System MUST apply at most one heading change per tick.
- **FR-015** — When multiple directional inputs arrive within one tick interval, System
  MUST apply only the last valid (non-reversing) input on the next tick and discard the
  others.
- **FR-016** — System MUST evaluate the reversal check against the committed heading of the
  last completed tick, not against the most recently buffered input, so chained turns
  within one tick cannot reverse the snake.
- **FR-017** — Pressing the key equal to the current heading MUST be a no-op (snake
  continues in that heading).

### Food, growth & scoring
- **FR-018** — When the head advances onto the food cell, System MUST grow the snake by one
  segment by retaining the tail cell on that tick (length increases by one).
- **FR-019** — When the head advances onto the food cell, System MUST increase the score by
  a fixed food value.
- **FR-020** — After food is eaten and at least one empty cell remains, System MUST spawn
  one new food on a uniformly random empty cell not occupied by the snake.
- **FR-021** — System MUST never place food on a cell occupied by the snake.
- **FR-022** — System MUST maintain exactly one food item on the board during active play.

### Collisions & end states
- **FR-023** — When the head would advance beyond the grid boundary, System MUST end the
  game as a loss.
- **FR-024** — When the head advances onto a cell occupied by the snake's own body, System
  MUST end the game as a loss.
- **FR-025** — When the snake is not growing on a tick, the cell vacated by the tail that
  same tick MUST be treated as empty for the head's collision check (legal tail-chase).
- **FR-026** — When the snake is growing on a tick, the tail cell remains occupied, so the
  head entering it MUST be detected as a self-collision (loss).
- **FR-027** — When the snake occupies every cell of the grid, System MUST end the game as
  a win.
- **FR-028** — On any game end (win or loss), System MUST stop advancing the snake on
  subsequent ticks (the board freezes).
- **FR-029** — On any game end, System MUST display the final score.
- **FR-030** — A single move that satisfies more than one end condition MUST produce exactly
  one game-over transition.

### Restart & game-over input handling
- **FR-031** — After game over, System MUST allow the player to start a fresh game via a
  single restart action.
- **FR-032** — On restart, System MUST reset the snake, food, score, and heading to the
  initial state and resume play.
- **FR-033** — After game over, System MUST ignore gameplay inputs (arrow keys, pause) and
  act only on the restart action.
- **FR-034** — While the game is actively running, System MUST ignore the restart action
  (no mid-game reset).

### Clarified defaults (folded back from /clarify — see Clarifications)
- **FR-035** — The default grid MUST be 20 columns × 20 rows.
- **FR-036** — The snake MUST start with length 3, positioned horizontally near the grid
  center, with initial heading Right (East).
- **FR-037** — The game speed MUST be a constant of approximately 8 ticks per second
  (~125 ms per tick) and MUST NOT auto-accelerate as the snake grows.
- **FR-038** — Eating one food MUST increase the score by exactly 1 point.
- **FR-039** — Walls MUST be solid: leaving the grid is a loss. There is NO wrap-around.
- **FR-040** — Movement MUST be restricted to the four orthogonal directions; diagonal
  movement is not supported.
- **FR-041** — System MUST support a pause toggle that halts and resumes tick advancement;
  while paused, no tick advances and gameplay inputs are buffered or ignored without moving
  the snake.
- **FR-042** — Random food placement MUST be reproducible from a fixed seed to allow
  deterministic testing, while defaulting to an unpredictable seed in normal play.
- **FR-043** — The game MUST run for a single local player using keyboard input only; no
  network, multiplayer, or persistent high-score storage is required.
- **FR-044** — System MUST reject a starting configuration whose grid cannot hold the
  initial snake plus at least one empty cell, before play begins.

---

## Success Criteria

- **SC-1** — A player can complete the full loop — start → steer → eat at least one food →
  die → see final score → restart — without errors or stuck states.
- **SC-2** — Across randomized fuzz play, the snake reverses 180° into its neck **zero**
  times.
- **SC-3** — Across randomized fuzz play, food spawns on a snake-occupied cell **zero**
  times, and exactly one food exists at all times during active play.
- **SC-4** — Wall and self collisions each end the game on the correct tick in 100% of
  constructed cases; the legal tail-chase case never ends the game.
- **SC-5** — Filling the grid produces a win (not a crash, freeze, or failed food spawn).
- **SC-6** — Given a fixed seed and a fixed input script, two runs produce identical board
  states tick-for-tick (determinism).
- **SC-7** — The score begins at 0, increases by exactly the food value per food, never
  decreases, and is shown correctly at game over.
- **SC-8** — Pause halts advancement with no skipped-tick debt on resume; restart yields a
  fully reset state every time.

---

## EARS Acceptance Criteria

> `WHEN <trigger> THE SYSTEM SHALL <response>`. Grouped by requirement number (R-n).
> Each criterion maps 1:1 to a scenario `S<n>.<index>` in `scenarios.md`.

### R1 — Initial state
- **R1.1** — WHEN a new game starts THE SYSTEM SHALL place the snake at its starting cells
  with the configured initial length and heading.
- **R1.2** — WHEN a new game starts THE SYSTEM SHALL place exactly one food item on a random
  empty cell.
- **R1.3** — WHEN a new game starts THE SYSTEM SHALL set the score to zero.
- **R1.4** — WHEN a new game starts THE SYSTEM SHALL set the heading to the configured
  initial direction (Right).

### R2 — Tick movement
- **R2.1** — WHEN a tick elapses and the head's next cell is empty THE SYSTEM SHALL move the
  head one cell forward and remove the tail.
- **R2.2** — WHEN a tick elapses and no new directional input is pending THE SYSTEM SHALL
  continue moving in the current heading.
- **R2.3** — WHEN the snake moves on a tick without eating THE SYSTEM SHALL keep the snake's
  length unchanged.

### R3 — Steering
- **R3.1** — WHEN the player presses an arrow orthogonal to the current heading THE SYSTEM
  SHALL change the heading to that direction on the next tick.
- **R3.2** — WHEN the player presses a key that is not a mapped control THE SYSTEM SHALL
  ignore it and retain the current heading.
- **R3.3** — WHEN the player presses the arrow equal to the current heading THE SYSTEM SHALL
  continue in that heading (no-op).

### R4 — 180° reversal protection
- **R4.1** — WHEN the player presses the arrow directly opposite the current heading THE
  SYSTEM SHALL ignore the input and continue straight.
- **R4.2** — WHEN the player chains two turns within one tick that would together reverse
  the heading THE SYSTEM SHALL reject the reversing result (checked vs the committed
  heading) and not fold onto the neck.

### R5 — Eating, growth & score
- **R5.1** — WHEN the head advances onto the food cell THE SYSTEM SHALL grow the snake by
  one segment (retain the tail that tick).
- **R5.2** — WHEN the head advances onto the food cell THE SYSTEM SHALL increase the score
  by the configured food value.

### R6 — Food spawning
- **R6.1** — WHEN food is eaten and at least one empty cell remains THE SYSTEM SHALL spawn a
  new food on a uniformly random empty cell not occupied by the snake.
- **R6.2** — WHEN the game is in active play THE SYSTEM SHALL maintain exactly one food on
  the board.

### R7 — Wall collision
- **R7.1** — WHEN the head would move beyond the grid boundary THE SYSTEM SHALL end the game
  as a loss.
- **R7.2** — WHEN the head moves onto the last in-bounds cell along an axis THE SYSTEM SHALL
  allow the move without ending the game.

### R8 — Self collision
- **R8.1** — WHEN the head moves onto a cell occupied by its own body THE SYSTEM SHALL end
  the game as a loss.
- **R8.2** — WHEN the head moves into the cell the tail vacates on the same non-growing tick
  THE SYSTEM SHALL treat the move as legal (no collision).

### R9 — Game over presentation & freeze
- **R9.1** — WHEN the game ends THE SYSTEM SHALL display the final score.
- **R9.2** — WHEN the game has ended THE SYSTEM SHALL stop advancing the snake on subsequent
  ticks.
- **R9.3** — WHEN the game has ended and the player presses a gameplay key other than
  restart THE SYSTEM SHALL not move the snake.

### R10 — Restart
- **R10.1** — WHEN the player issues the restart action after game over THE SYSTEM SHALL
  reset to the initial state and resume play.
- **R10.2** — WHEN the player issues the restart action during active play THE SYSTEM SHALL
  ignore it.

### R11 — Win
- **R11.1** — WHEN the snake occupies every cell of the grid THE SYSTEM SHALL end the game
  as a win and display the final score.

### R12 — Pause
- **R12.1** — WHEN the player presses the pause control during active play THE SYSTEM SHALL
  halt tick advancement.
- **R12.2** — WHEN the player presses the pause control while paused THE SYSTEM SHALL resume
  tick advancement from the current state.
- **R12.3** — WHEN the player presses a directional input while paused THE SYSTEM SHALL not
  move the snake until play resumes.

### R13 — Input buffering within a tick
- **R13.1** — WHEN multiple directional inputs arrive within one tick interval THE SYSTEM
  SHALL apply only the last valid (non-reversing) input on the next tick.
- **R13.2** — WHEN a buffered directional input would reverse the committed heading THE
  SYSTEM SHALL discard it during buffering.

---

## Clarifications (resolved by /clarify)

Each ambiguity below was resolved with an industry-standard default and folded into the
Functional Requirements (FR-035 – FR-044). The assumptions are restated here for the record:

1. **Grid size** → 20×20 cells (FR-035).
2. **Initial snake** → length 3, horizontal, near center, heading Right (FR-036).
3. **Game speed** → constant ~8 ticks/sec, no auto-acceleration (FR-037).
4. **Score value** → +1 per food (FR-038).
5. **Walls** → solid, no wrap-around (FR-039).
6. **Directions** → 4 orthogonal only, no diagonals (FR-040).
7. **Pause** → supported as a toggle (FR-041).
8. **Randomness** → uniform over empty cells, seedable for tests (FR-042).
9. **Scope** → single local player, keyboard only, no persistence/multiplayer (FR-043).
10. **Config validation** → reject grids too small for the initial snake (FR-044).
11. **Restart trigger** → a single dedicated action, effective only at game over (FR-031, FR-034).
12. **Tail-chase ordering** → tail removed before head-collision check on non-growing ticks;
    retained on growing ticks (FR-025, FR-026).
