---
description: Plan — emit the canonical Athena plan.md (the compiler contract)
model: opus
argument-hint: "thoughts/qrspi/<id>/"
---

# Plan — Emit the Canonical `plan.md`

Expand the structure outline into the **canonical Athena `plan.md`** — the single
contract consumed by the deterministic compiler (`lib/plan2beads.py`). Unlike upstream
QRSPI, the output format here is FIXED and parsed strictly (`lib/plan_parser.py`). The
full spec is `skills/plan-format/SKILL.md`. Any deviation is rejected by the parser,
never fixed downstream. By this stage alignment is already done — this is a mechanical
translation of the agreed design into phases + tasks, not where decisions are made.

## Input

Read `$ARGUMENTS/structure.md`, `$ARGUMENTS/design.md`, and `$ARGUMENTS/research.md`.

## Process

1. Read all three artifacts fully.
2. For each phase in `structure.md`, produce one `## Phase N:` block with atomic tasks.
3. Write `$ARGUMENTS/plan.md` in EXACTLY this format:

```markdown
# Plan: <name>
## Overview
<2-4 sentences: goal + desired end state>

## Out of Scope
- <what we do NOT do>

## Phase 1: <name>
**Goal:** <one sentence>
**Depends on:** none            # or "Phase N"
### Tasks
- [ ] T1.1 <atomic task>
  - success_check: `<executable command, exit 0 = passed>`
  - files: `path/a.py, path/b.py`
  - autonomy: high              # optional: high -> OpenHands, else Claurst
### Manual Verification
- <manual steps>
```

## Hard rules (the parser WILL reject otherwise)

- `# Plan:` title is mandatory.
- Every task is `- [ ] T<phase>.<n> <title>` with a NON-EMPTY `success_check` on the
  next indented line.
- `success_check` must be an executable command whose exit 0 means the task passed —
  it IS the gate. No prose, no "verify that…".
- `Depends on:` is `none` or `Phase N` (N must exist, else the compiler errors).
- Task ids are unique across the whole plan.
- `autonomy: high` is optional; it routes that issue to OpenHands (else Claurst).
- One task = one Ralph iteration. Keep tasks atomic and independently checkable.

## Output

- File written: `$ARGUMENTS/plan.md`
- Validate immediately (must exit 0):
  `python -c "from lib.plan_parser import parse; parse(open('$ARGUMENTS/plan.md', encoding='utf-8').read())"`
- Tell the user: "Next: `/athena.compile $ARGUMENTS/plan.md`"

## When to Go Back

If a phase can't be expressed as atomic tasks with executable `success_check`s, the
design/structure is too vague — re-run `/qrspi/4_structure` or `/qrspi/3_design`
rather than emitting a plan the compiler will reject.
