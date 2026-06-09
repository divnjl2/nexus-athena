---
name: plan-format
description: Canonical plan.md format — the only contract between QRSPI 5_plan and the deterministic compiler.
---

# Canonical `plan.md` Format (Athena contract §4)

This is the **fallback** contract (`ATHENA_SPECKIT=off`): the CRISP stage `5_plan` emits
this, `lib/plan_parser.py` parses it into the shared `lib/ast.py` `Plan`, and
`lib/plan2beads.py` compiles the AST. (The **primary** path is Spec-Kit `tasks.md` —
see `skills/speckit-tasks-format/SKILL.md`.) Both parsers emit the same AST, so the
compiler never changes. The parser is strict: any deviation is rejected BEFORE
compilation, never "fixed" downstream.

## Format

```markdown
# Plan: <name>
## Overview
<2-4 sentences: goal + desired end state>

## Out of Scope
- <what we do NOT do>

## Phase 1: <name>
**Goal:** <one sentence>
**Depends on:** none                 # or "Phase N"
### Tasks
- [ ] T1.1 [P] <atomic task>         # [P] optional: parallelizable -> no intra-phase edge
  - success_check: `<executable command, exit 0 = passed>`
  - files: `path/a.py, path/b.py`
  - autonomy: high                   # optional: high|low|default (default -> no routing label)
### Manual Verification
- <manual steps>

## Phase 2: <...>
**Depends on:** Phase 1
...
```

## Hard parsing rules

- `## Phase N:` -> epic (1-based index N).
- `T<phase>.<n>` -> child issue under that phase's epic.
- `**Depends on:** Phase K` -> blocks-edge at epic level; `none` -> no edge.
- `success_check:` is **mandatory and non-empty**. Missing -> `PlanParseError` (rejected at parse time).
- `autonomy:` optional -> routing label (`high` -> OpenHands, else Claurst).
- `files:` -> recorded in the issue body.
- `## Out of Scope` -> note carried on the plan.
- Duplicate `T#.#` anywhere in the plan -> `PlanParseError`.
- `Depends on` referencing a non-existent phase -> `CompileError` (compile time).

## Why strict

The compiler is the freeze line between fuzzy (LLM above) and mechanical (graph
below). A lenient parser would let a malformed plan compile into a wrong task graph
that a nightly Ralph run would then faithfully execute. Reject early, loudly — a
rejected plan is cheap; a wrong graph executed overnight is not.
