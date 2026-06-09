---
description: Compile the chosen front (Spec-Kit tasks.md OR canonical plan.md) into the bd graph.
argument-hint: "<path to tasks.md or plan.md>"
---

# /athena.compile — front -> Plan AST -> bd graph (toggle by ATHENA_SPECKIT)

Deterministically compile the planning front into Beads `bd` commands and apply them
idempotently. No LLM in this step — `lib/plan2beads.py` is a pure AST->commands transform,
so it is reproducible and golden-testable.

## Toggle (§6)

- `ATHENA_SPECKIT=on`  (primary): parse `tasks.md` with `lib/speckit_parser`.
- `ATHENA_SPECKIT=off` (fallback): parse `plan.md` with `lib/plan_parser`.

`lib/frontend.parse_source(path)` reads the env var and selects the parser. The compiler
never sees the toggle — it consumes only the shared `lib/ast.py` `Plan`.

## Process

1. **Validate** the chosen front before compiling — stop on any error:

   ```bash
   python -c "from lib.frontend import parse_source; parse_source('$ARGUMENTS')"
   ```

2. **Dry-run preview** (no bd writes):

   ```bash
   python -c "
   from lib.frontend import parse_source
   from lib.plan2beads import compile
   res = compile(parse_source('$ARGUMENTS'))
   for c in res.commands: print(c)
   print(f'-- epics={len(res.epic_keys)} issues={res.issue_count} commands={len(res.commands)}')
   "
   ```

3. **Apply idempotently** (fetch existing athena labels, skip what's already in the graph):

   ```bash
   python -c "
   import subprocess
   from lib.frontend import parse_source
   from lib.plan2beads import compile, _slugify
   from lib.bd_client import fetch_existing_keys, execute
   def run(argv): return subprocess.run(argv, capture_output=True, text=True, check=True).stdout
   plan = parse_source('$ARGUMENTS')
   res = compile(plan, existing_keys=fetch_existing_keys(_slugify(plan.title), run=run))
   execute(res, run=run)
   print(f'applied {len(res.commands)} commands ({res.issue_count} issues)')
   "
   ```

4. Report `epic_keys` + `issue_count`. The graph is ready to hand off to the (deferred)
   executor via `planner_export_ready` — see `ralph/INTERFACE.md`.

## Invariants

- Re-running on an unchanged front emits **zero** `bd create` (idempotent upsert).
- Deterministic: same front, same commands, same order.
- A front with a missing `success_check` or unresolved dependency is rejected at step 1/2.
- Both toggle paths produce the SAME compiler contract (the AST) — `tests/test_toggle.py`.
