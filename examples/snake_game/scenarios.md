# Scenarios: Classic Snake Game

> `/athena.scenarios` output. One executable Given-When-Then scenario per EARS acceptance
> criterion in `spec.md`. Stable IDs `S<requirement#>.<index>` map 1:1 to the EARS list.
> Prose Given/When/Then (NO Gherkin/Cucumber). Each scenario carries a `run_cmd` — a native
> `pytest` invocation that proves it. `verifies` back-links the criterion.

---

## R1 — Initial state

### S1.1 — New game places the snake
- **verifies:** R1.1
- **run_cmd:** `pytest tests/test_snake_body.py::test_initial_placement -q`
- **Given** a new game configured with grid 20×20, initial length 3, heading Right, centered
- **When** the game is initialized
- **Then** the snake occupies exactly 3 contiguous horizontal cells near the center with the
  head as the right-most cell and the heading set to Right.

### S1.2 — New game places exactly one food on an empty cell
- **verifies:** R1.2
- **run_cmd:** `pytest tests/test_game.py::test_init_one_food_on_empty_cell -q`
- **Given** a new game seeded deterministically
- **When** the game is initialized
- **Then** exactly one food exists and its cell is not occupied by the snake.

### S1.3 — New game starts at score zero
- **verifies:** R1.3
- **run_cmd:** `pytest tests/test_game.py::test_init_score_zero -q`
- **Given** a new game
- **When** the game is initialized
- **Then** the score equals 0.

### S1.4 — New game uses the configured initial heading
- **verifies:** R1.4
- **run_cmd:** `pytest tests/test_game.py::test_init_heading_right -q`
- **Given** a new game with default config
- **When** the game is initialized
- **Then** the committed heading is Right (East).

---

## R2 — Tick movement

### S2.1 — A tick moves the head forward and drops the tail
- **verifies:** R2.1
- **run_cmd:** `pytest tests/test_snake_body.py::test_advance_moves_head_drops_tail -q`
- **Given** a snake of length 3 heading Right with an empty cell ahead
- **When** one tick elapses
- **Then** the head has advanced one cell Right and the former tail cell is now empty.

### S2.2 — With no input the snake keeps its heading
- **verifies:** R2.2
- **run_cmd:** `pytest tests/test_game.py::test_tick_continues_same_heading -q`
- **Given** a running game with heading Right and no pending input
- **When** three ticks elapse
- **Then** the snake has moved three cells Right and the heading is still Right.

### S2.3 — A non-eating move preserves length
- **verifies:** R2.3
- **run_cmd:** `pytest tests/test_snake_body.py::test_move_preserves_length -q`
- **Given** a snake of length 3 with no food ahead
- **When** one tick elapses
- **Then** the snake's length is still 3.

---

## R3 — Steering

### S3.1 — An orthogonal arrow turns the snake on the next tick
- **verifies:** R3.1
- **run_cmd:** `pytest tests/test_input.py::test_orthogonal_turn_applied -q`
- **Given** a running game heading Right
- **When** the player presses Up and one tick elapses
- **Then** the snake moves one cell Up and the committed heading is Up.

### S3.2 — An unmapped key is ignored
- **verifies:** R3.2
- **run_cmd:** `pytest tests/test_input.py::test_unmapped_key_ignored -q`
- **Given** a running game heading Right
- **When** the player presses an unmapped key (e.g. "q") and one tick elapses
- **Then** the heading is still Right and the snake moved one cell Right.

### S3.3 — Pressing the current direction is a no-op
- **verifies:** R3.3
- **run_cmd:** `pytest tests/test_input.py::test_same_direction_noop -q`
- **Given** a running game heading Right
- **When** the player presses Right and one tick elapses
- **Then** the heading is still Right and the snake advanced one cell Right.

---

## R4 — 180° reversal protection

### S4.1 — The directly opposite arrow is rejected
- **verifies:** R4.1
- **run_cmd:** `pytest tests/test_input.py::test_reverse_rejected -q`
- **Given** a running game heading Right
- **When** the player presses Left and one tick elapses
- **Then** the heading is still Right and the snake advanced one cell Right (no reversal).

### S4.2 — Chained turns within one tick cannot reverse the snake
- **verifies:** R4.2
- **run_cmd:** `pytest tests/test_input.py::test_chained_turns_no_reverse -q`
- **Given** a running game heading Right
- **When** the player presses Up then Left within the same tick interval and one tick elapses
- **Then** the snake does not reverse onto its neck; the committed heading is Up (the last
  valid non-reversing input relative to the committed Right heading), not Left.

---

## R5 — Eating, growth & score

### S5.1 — Eating food grows the snake by one
- **verifies:** R5.1
- **run_cmd:** `pytest tests/test_game.py::test_eat_grows_by_one -q`
- **Given** a running game with food in the cell directly ahead of the head and length 3
- **When** one tick elapses and the head enters the food cell
- **Then** the snake's length is 4 and the tail cell from the previous tick is still occupied.

### S5.2 — Eating food increases the score
- **verifies:** R5.2
- **run_cmd:** `pytest tests/test_game.py::test_eat_increments_score -q`
- **Given** a running game at score 0 with food directly ahead
- **When** the head enters the food cell
- **Then** the score equals the configured food value (1).

---

## R6 — Food spawning

### S6.1 — A new food spawns on a random empty cell after eating
- **verifies:** R6.1
- **run_cmd:** `pytest tests/test_food.py::test_respawn_on_empty_cell -q`
- **Given** a seeded running game with empty cells remaining and food directly ahead
- **When** the head eats the food
- **Then** exactly one new food exists, on a cell that is empty and not occupied by the snake.

### S6.2 — Exactly one food exists during active play
- **verifies:** R6.2
- **run_cmd:** `pytest tests/test_food.py::test_single_food_invariant -q`
- **Given** a seeded running game played for many ticks including several eats
- **When** the board is inspected after each tick
- **Then** exactly one food cell exists on every tick of active play.

---

## R7 — Wall collision

### S7.1 — Moving beyond the boundary ends the game
- **verifies:** R7.1
- **run_cmd:** `pytest tests/test_game.py::test_wall_collision_game_over -q`
- **Given** a running game with the head on the right-most column heading Right
- **When** one tick elapses
- **Then** the game status is GAME_OVER (loss) and the snake did not advance off the grid.

### S7.2 — Moving onto the last in-bounds cell is legal
- **verifies:** R7.2
- **run_cmd:** `pytest tests/test_game.py::test_last_inbounds_cell_legal -q`
- **Given** a running game with the head one cell before the right-most column heading Right
- **When** one tick elapses
- **Then** the head is on the right-most column and the game is still RUNNING.

---

## R8 — Self collision

### S8.1 — Running into the body ends the game
- **verifies:** R8.1
- **run_cmd:** `pytest tests/test_game.py::test_self_collision_game_over -q`
- **Given** a snake long enough to curl into itself, positioned so the next head cell is a
  body cell that will not vacate this tick
- **When** one tick elapses
- **Then** the game status is GAME_OVER (loss).

### S8.2 — Entering the vacating tail cell is legal (tail-chase)
- **verifies:** R8.2
- **run_cmd:** `pytest tests/test_game.py::test_tail_chase_legal -q`
- **Given** a non-growing snake whose head's next cell is the current tail cell (which
  vacates this tick)
- **When** one tick elapses
- **Then** the move succeeds, the game is still RUNNING, and length is unchanged.

---

## R9 — Game over presentation & freeze

### S9.1 — Game over displays the final score
- **verifies:** R9.1
- **run_cmd:** `pytest tests/test_render.py::test_game_over_shows_score -q`
- **Given** a finished game with a known final score
- **When** the game-over frame is rendered
- **Then** the rendered output contains the final score value.

### S9.2 — Ticks after game over do not advance the snake
- **verifies:** R9.2
- **run_cmd:** `pytest tests/test_game.py::test_frozen_after_game_over -q`
- **Given** a game already in GAME_OVER
- **When** additional ticks are requested
- **Then** the snake's cells and score are unchanged.

### S9.3 — Gameplay keys are ignored after game over
- **verifies:** R9.3
- **run_cmd:** `pytest tests/test_game.py::test_gameplay_keys_ignored_after_over -q`
- **Given** a game in GAME_OVER
- **When** the player presses arrow and pause keys
- **Then** the snake does not move and the status remains GAME_OVER.

---

## R10 — Restart

### S10.1 — Restart after game over resets to initial state
- **verifies:** R10.1
- **run_cmd:** `pytest tests/test_game.py::test_restart_resets_state -q`
- **Given** a finished game with score > 0 and a grown snake
- **When** the player issues restart
- **Then** the status is RUNNING, score is 0, the snake is at initial length/position/heading,
  and exactly one food exists.

### S10.2 — Restart during active play is ignored
- **verifies:** R10.2
- **run_cmd:** `pytest tests/test_game.py::test_restart_ignored_when_running -q`
- **Given** a RUNNING game mid-play with score > 0
- **When** the player issues restart
- **Then** the game state (snake, score, food) is unchanged and status is still RUNNING.

---

## R11 — Win

### S11.1 — Filling the grid wins the game
- **verifies:** R11.1
- **run_cmd:** `pytest tests/test_game.py::test_fill_grid_wins -q`
- **Given** a game state one eat away from the snake occupying every cell
- **When** the head eats the food on the last empty cell
- **Then** the status is WON, no new food is spawned, and the final score is displayed.

---

## R12 — Pause

### S12.1 — Pause halts tick advancement
- **verifies:** R12.1
- **run_cmd:** `pytest tests/test_game.py::test_pause_halts_ticks -q`
- **Given** a RUNNING game
- **When** the player presses pause and several ticks are requested
- **Then** the snake's cells are unchanged and the status is PAUSED.

### S12.2 — Pausing while paused resumes play
- **verifies:** R12.2
- **run_cmd:** `pytest tests/test_game.py::test_pause_toggle_resumes -q`
- **Given** a PAUSED game
- **When** the player presses pause again and one tick elapses
- **Then** the status is RUNNING and the snake advanced one cell.

### S12.3 — Directional input while paused does not move the snake
- **verifies:** R12.3
- **run_cmd:** `pytest tests/test_game.py::test_input_while_paused_no_move -q`
- **Given** a PAUSED game heading Right
- **When** the player presses Up and ticks are requested
- **Then** the snake's cells are unchanged while paused.

---

## R13 — Input buffering within a tick

### S13.1 — Only the last valid input within a tick is applied
- **verifies:** R13.1
- **run_cmd:** `pytest tests/test_input.py::test_last_valid_input_wins -q`
- **Given** a running game heading Right
- **When** the player presses Up then Down within one tick interval and one tick elapses
- **Then** the snake turns Down (the last valid input), not Up.

### S13.2 — A buffered reversal is discarded
- **verifies:** R13.2
- **run_cmd:** `pytest tests/test_input.py::test_buffered_reversal_discarded -q`
- **Given** a running game heading Right
- **When** the player presses Up then Left within one tick interval and one tick elapses
- **Then** the buffered Left (a reversal of the committed Right heading) is discarded and the
  snake turns Up.
