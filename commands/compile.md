---
description: Compile the canonical plan.md into the bd task-graph (deterministic, idempotent)
argument-hint: "<path to plan.md>"
---

# /athena.compile — plan.md -> bd graph

Deterministically compile a canonical `plan.md` into Beads `bd` commands (epics +
issues + dependency edges) and apply them idempotently. No LLM in this step — it is a
pure transformation (`lib/plan2beads.py`), so the result is reproducible and golden-testable.

## Process

1. **Validate** the format first — stop on any error, do NOT compile a malformed plan:

   ```bash
   python -c "from lib.plan_parser import parse; parse(open('$ARGUMENTS', encoding='utf-8').read())"
   ```

2. **Dry-run preview** — print the commands without touching bd:

   ```bash
   python -c "
   import pathlib
   from lib.plan_parser import parse
   from lib.plan2beads import compile
   res = compile(parse(pathlib.Path('$ARGUMENTS').read_text(encoding='utf-8')))
   for c in res.commands: print(c)
   print(f'-- epics={len(res.epic_keys)} issues={res.issue_count} commands={len(res.commands)}')
   "
   ```

3. **Apply idempotently** — fetch existing athena labels, skip anything already in the graph:

   ```bash
   python -c "
   import pathlib, subprocess
   from lib.plan_parser import parse
   from lib.plan2beads import compile, _slugify
   from lib.bd_client import fetch_existing_keys, execute
   def run(argv): return subprocess.run(argv, capture_output=True, text=True, check=True).stdout
   plan = parse(pathlib.Path('$ARGUMENTS').read_text(encoding='utf-8'))
   existing = fetch_existing_keys(_slugify(plan.title), run=run)
   res = compile(plan, existing_keys=existing)
   execute(res, run=run)
   print(f'applied {len(res.commands)} commands ({res.issue_count} issues)')
   "
   ```

4. Report `epic_keys` + `issue_count`. The graph is now ready for the Ralph loop (`ralph/loop.sh`).

## Invariants

- Re-running on an unchanged plan emits **zero** `bd create` (idempotent upsert via `athena:<slug>:*` labels).
- The compiler is deterministic — same `plan.md`, same commands, same order.
- A plan with a missing `success_check` or an unresolved dependency is rejected at
  step 1/2 and never half-applied.
