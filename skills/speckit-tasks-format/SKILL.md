---
name: speckit-tasks-format
description: The Spec-Kit tasks.md schema Athena parses (PRIMARY contract, ATHENA_SPECKIT=on).
---

# Spec-Kit `tasks.md` Schema (Athena PRIMARY contract §5)

When `ATHENA_SPECKIT=on`, layer ② emits `tasks.md` (Spec-Kit + the Athena preset).
`lib/speckit_parser.py` reads it into the shared `lib/ast.py` `Plan`. This schema is
PINNED — the golden test `tests/test_speckit_parser.py::test_golden_ast` fails if the
Spec-Kit format drifts (v2 §10's top risk). The Spec-Kit ref is pinned in `vendor/spec-kit/`.

## Format

```markdown
# Tasks: <feature>

## Phase 1: Setup
- [ ] T001 <task with file path>
  - success_check: `<command, exit 0 = passed>`   # injected by the Athena preset
- [ ] T002 [P] <parallelizable task>
  - success_check: `<command>`

## Phase 2: Foundational
- [ ] T003 <task>
  - success_check: `<command>`

## Phase 3: User Story 1 - <title> (Priority: P1)
**Goal:** <one sentence>
- [ ] T004 [P] [US1] <task>
  - success_check: `<command>`
- [ ] T005 [US1] <task>
  - success_check: `<command>`
**Checkpoint:** `<phase gate command>`

## Phase N: Polish
- [ ] T0NN [P] <task>
  - success_check: `<command>`
```

## Markers & mapping to the AST

- `[P]` → `Task.parallel=True` (no intra-phase edge between `[P]` siblings).
- `[US1]` / `[Story]` → user-story tag (phase key becomes `US1`); stripped from the title.
- `**Checkpoint:**` → `Phase.checkpoint` (epic-level gate command).
- `success_check:` per task comes from the **Athena preset** (primary). If absent, the
  parser falls back to the phase `Checkpoint`. Neither present → reject.
- **Setup** and **Foundational** phases block every **User Story** phase; **Polish** blocks
  on all User Story phases.

## Why pinned

Spec-Kit's `tasks.md` template evolves. The parser targets THIS schema; the version-guard
golden test must fail on drift so we re-pin deliberately, never silently mis-parse.
