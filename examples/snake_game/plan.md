# Plan: Classic Snake Game

## Overview
Build a single-player Snake game as a pure, headless, deterministic rules engine plus a thin
keyboard/terminal UI adapter. The engine advances the snake one cell per tick, steers via the
arrow keys with 180° reversal protection and within-tick input buffering, spawns food on
random empty cells, scores on eating, and ends the run on wall/self collision (loss) or a
full grid (win), with freeze-and-restart afterward. The end state is every EARS criterion in
`scenarios.md` proven by an executable `success_check`.

## Out of Scope
- Speed-up / difficulty ramp as the snake grows (constant tick rate only).
- Wrap-around walls, diagonal movement, multiple food items, power-ups, or obstacles.
- Persistence: saved high scores, profiles, or settings files.
- Multiplayer, networking, AI opponents, replays, sound, or theming.
- Window/focus-loss handling inside the rules engine; mouse/touch input.

## Phase 1: Geometry, grid & config foundation
**Goal:** Establish immutable coordinate/direction primitives, grid bounds, and validated config defaults.
**Depends on:** none
### Tasks
- [ ] T1.1 Implement immutable Coord and Direction with opposite() and orthogonality/delta helpers
  - success_check: `pytest tests/test_geometry.py -q`
  - files: `snake/geometry.py, tests/test_geometry.py`
  - verifies: S3.1
  - autonomy: high
- [ ] T1.2 Implement Grid with width/height, in_bounds(), and all_cells() enumeration
  - success_check: `pytest tests/test_grid.py -q`
  - files: `snake/grid.py, tests/test_grid.py`
  - verifies: S7.2
  - autonomy: high
- [ ] T1.3 Implement Config defaults (20x20, length 3, heading Right, ~8 ticks/s, food value 1) with min-grid validation
  - success_check: `pytest tests/test_config.py -q`
  - files: `snake/config.py, tests/test_config.py`
  - verifies: S1.4
### Manual Verification
- Open `snake/config.py` and confirm defaults match FR-035..FR-040 and FR-044.
- Confirm an undersized grid raises a clear validation error before play.

## Phase 2: Snake body & movement
**Goal:** Represent the snake and implement tick-based advance, tail-drop, and growth.
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 Implement Snake body as an ordered deque + occupancy set with initial centered placement
  - success_check: `pytest tests/test_snake_body.py::test_initial_placement -q`
  - files: `snake/snake_body.py, tests/test_snake_body.py`
  - verifies: S1.1
  - autonomy: high
- [ ] T2.2 Implement advance(direction): append head, pop tail, preserve length on non-eating ticks
  - success_check: `pytest tests/test_snake_body.py -q -k "advance or preserves or drops"`
  - files: `snake/snake_body.py, tests/test_snake_body.py`
  - verifies: S2.1
- [ ] T2.3 Implement grow(): retain tail on the next advance so length increases by one
  - success_check: `pytest tests/test_snake_body.py::test_grow_increases_length -q`
  - files: `snake/snake_body.py, tests/test_snake_body.py`
  - verifies: S2.3
### Manual Verification
- Trace a 3-segment snake through 5 advances on paper; confirm head/tail cells match.

## Phase 3: Input handling & direction control
**Goal:** Map keys to directions, reject 180° reversals against the committed heading, and buffer within a tick.
**Depends on:** Phase 1
### Tasks
- [ ] T3.1 Build the key->direction map; ignore unmapped keys and retain heading
  - success_check: `pytest tests/test_input.py::test_unmapped_key_ignored -q`
  - files: `snake/input.py, tests/test_input.py`
  - verifies: S3.2
  - autonomy: high
- [ ] T3.2 Apply orthogonal turns on the next tick; pressing the current direction is a no-op
  - success_check: `pytest tests/test_input.py -q -k "orthogonal_turn or same_direction_noop"`
  - files: `snake/input.py, tests/test_input.py`
  - verifies: S3.1
- [ ] T3.3 Reject the directly-opposite arrow (180 reversal) checked against the committed heading
  - success_check: `pytest tests/test_input.py::test_reverse_rejected -q`
  - files: `snake/input.py, tests/test_input.py`
  - verifies: S4.1
- [ ] T3.4 Buffer multiple inputs per tick: apply last valid, discard buffered reversals (anti two-turn exploit)
  - success_check: `pytest tests/test_input.py -q -k "last_valid_input_wins or buffered_reversal_discarded or chained_turns_no_reverse"`
  - files: `snake/input.py, tests/test_input.py`
  - verifies: S13.1
### Manual Verification
- While moving Right, press Up then Left fast; confirm the snake turns Up and never folds.

## Phase 4: Food, growth & scoring
**Goal:** Spawn food on a random empty cell, maintain the single-food invariant, and score on eating.
**Depends on:** Phase 2
### Tasks
- [ ] T4.1 Implement seeded uniform food spawn over empty (non-snake) cells
  - success_check: `pytest tests/test_food.py::test_respawn_on_empty_cell -q`
  - files: `snake/food.py, tests/test_food.py`
  - verifies: S6.1
  - autonomy: high
- [ ] T4.2 Enforce invariants: food never on the snake; exactly one food during active play
  - success_check: `pytest tests/test_food.py::test_single_food_invariant -q`
  - files: `snake/food.py, tests/test_food.py`
  - verifies: S6.2
- [ ] T4.3 Increment score by the configured food value when the head eats food
  - success_check: `pytest tests/test_game.py -q -k "eat_increments_score or eat_grows_by_one"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S5.2
### Manual Verification
- Run a seeded game; confirm each eat raises the score by exactly 1 and spawns one food.

## Phase 5: Collision, game over & win
**Goal:** Detect wall and self collisions (with correct tail ordering) and full-grid win.
**Depends on:** Phase 2
### Tasks
- [ ] T5.1 Detect wall collision when the head leaves bounds; allow the last in-bounds cell
  - success_check: `pytest tests/test_game.py -q -k "wall_collision_game_over or last_inbounds_cell_legal"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S7.1
- [ ] T5.2 Detect self collision; treat the vacating tail cell as empty on non-growing ticks
  - success_check: `pytest tests/test_game.py -q -k "self_collision_game_over or tail_chase_legal"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S8.1
- [ ] T5.3 Detect win when the snake fills the grid; skip food respawn and display final score
  - success_check: `pytest tests/test_game.py::test_fill_grid_wins -q`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S11.1
### Manual Verification
- Construct a near-full board fixture; confirm the final eat yields WON, not a spawn failure.
- Construct a tail-chase fixture; confirm it does NOT end the game.

## Phase 6: Game state machine — init, tick, pause, freeze, restart
**Goal:** Orchestrate the engine across RUNNING/PAUSED/GAME_OVER/WON with deterministic init and restart.
**Depends on:** Phase 3
### Tasks
- [ ] T6.1 Initialize Game: snake, exactly one seeded food, score 0, heading Right, status RUNNING
  - success_check: `pytest tests/test_game.py -q -k "init_one_food_on_empty_cell or init_score_zero or init_heading_right"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S1.2
  - autonomy: high
- [ ] T6.2 Implement tick(): consume pending direction, advance, resolve eat/grow/respawn, continue heading with no input
  - success_check: `pytest tests/test_game.py::test_tick_continues_same_heading -q`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S2.2
- [ ] T6.3 Implement pause toggle: halt ticks while PAUSED; directional input does not move the snake
  - success_check: `pytest tests/test_game.py -q -k "pause_halts_ticks or pause_toggle_resumes or input_while_paused_no_move"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S12.1
- [ ] T6.4 Freeze after game over: ignore ticks and gameplay keys once GAME_OVER/WON
  - success_check: `pytest tests/test_game.py -q -k "frozen_after_game_over or gameplay_keys_ignored_after_over"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S9.2
- [ ] T6.5 Implement restart: reset to initial state from game over; ignore restart during active play
  - success_check: `pytest tests/test_game.py -q -k "restart_resets_state or restart_ignored_when_running"`
  - files: `snake/game.py, tests/test_game.py`
  - verifies: S10.1
### Manual Verification
- Pause/resume mid-run; confirm no skipped-tick debt on resume.
- Restart several times; confirm a clean reset and a freshly randomized food each time.

## Phase 7: Rendering, UI loop & end-to-end integration
**Goal:** Wire the engine to a keyboard-driven terminal render loop and prove the full playable loop.
**Depends on:** Phase 6
### Tasks
- [ ] T7.1 Implement a pure renderer that draws grid, snake, food, score, and game-over/win banner to a buffer
  - success_check: `pytest tests/test_render.py -q -k "render_frame or game_over_shows_score"`
  - files: `snake/render.py, tests/test_render.py`
  - verifies: S9.1
- [ ] T7.2 Implement the main loop: fixed-interval ticks, non-blocking key polling, pause/restart wiring
  - success_check: `python -c "import snake.main"`
  - files: `snake/main.py`
  - verifies: S2.2
- [ ] T7.3 End-to-end seeded smoke: scripted game eats, dies, shows score, and restarts cleanly
  - success_check: `pytest tests/test_e2e.py::test_full_game_loop -q`
  - files: `tests/test_e2e.py`
  - verifies: S10.1
### Manual Verification
- Launch `python -m snake.main`; play a full round: steer, eat, die, read final score, restart.
- Confirm constant speed (no acceleration) and that held keys never speed the snake up.

## Phase 8: Verification harness & invariant fuzz
**Goal:** Lock the Success Criteria as automated checks across the whole suite.
**Depends on:** Phase 7
### Tasks
- [ ] T8.1 Add deterministic-replay test: same seed + same input script yields identical states
  - success_check: `pytest tests/test_determinism.py::test_seeded_replay_identical -q`
  - files: `tests/test_determinism.py`
  - verifies: S6.2
- [ ] T8.2 Add fuzz test asserting invariants: no 180 reversal and food never on snake over random play
  - success_check: `pytest tests/test_fuzz.py -q -k "no_reverse or food_never_on_snake"`
  - files: `tests/test_fuzz.py`
  - verifies: S4.2
- [ ] T8.3 Full suite gate: run the entire test suite green
  - success_check: `pytest -q`
  - files: `tests/`
  - verifies: S1.1
### Manual Verification
- Run `pytest -q` and confirm zero failures; review fuzz seeds logged on any failure.
