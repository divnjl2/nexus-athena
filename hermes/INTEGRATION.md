# Wiring Athena into cex-Hermes (master-plan bridge)

Athena = the deterministic front + seams. The **existing** Hermes `PLAN_RUN`
(`tools/hermes_plan_runner.py`) is the executor — Athena's deferred Ralph is *not* rebuilt,
it IS `PLAN_RUN`. Integration = a workflow that compiles a front into a Hermes master-plan
`.md`, with the seams as `quality_gates`.

## Flow

```
front (tasks.md | plan.md)
  └─ ATHENA_PLAN workflow  (athena.py hermes-plan)
       ├─ quality_gates = Athena seams (fail-closed)
       └─ emits docs/master_plans/<name>.md   (frontmatter + ## Tasks)
            └─ PLAN_RUN (existing)  →  autonomy queue → executes → checkbox writeback
```

## Drop-in steps (operator / live-Hermes — NOT auto-applied)

1. Copy `ATHENA_PLAN.yaml` → `apps/hermes/workflows/ATHENA_PLAN.yaml`. Replace `<ATHENA_REPO>`
   with the absolute path (e.g. `/path/to/nexus-athena`).
2. Register the three seam gates so Hermes can evaluate them. Each is a thin shell-exec of:
   ```bash
   python <ATHENA_REPO>/athena.py seam <name> "$CEX_HERMES_INPUT_FRONT"   # exit 0 = pass
   ```
   All three wire uniformly (exit 0 = pass, non-0 = fail):
   - `athena_seam_ast_wellformed` → `athena.py seam ast_wellformed <front>`
   - `athena_seam_compile_pure`   → `athena.py seam compile_pure <front>`
   - `athena_seam_speckit_schema` → `athena.py seam speckit_schema <front>` (front must parse
     under the pinned Spec-Kit schema; the repo's `pytest -k golden` guards the schema itself)
3. Provide the per-task executor workflow **`ATHENA_TASK`** (each emitted task binds to it):
   it receives `inputs: {success_check, title, files, autonomy, phase}` and must (a) do the
   work (route `autonomy:high` → OpenHands, else Claurst — see `ralph/INTERFACE.md`), then
   (b) run `success_check` through an **external** authoritative gate (self-report doesn't count).
   This is the one piece that still needs an executor decision — until then, point tasks at an
   existing generic executor workflow or stub `ATHENA_TASK` as manual.
4. Load into live Hermes (`:9583`) and dry-run on a small real front.

## Observability = quality_gates (the seam question, answered)

The seams ARE the observability: each is a Hermes `quality_gate`, so Hermes's existing
gate / `acceptance` / `escalation` machinery shows seam pass/fail per run — no parallel
observability layer. `lib/seams.py` also appends `SeamRecord`s to `.athena/seams.jsonl`
(+ `render_mermaid` for a waterfall) when driven directly; in Hermes the gate results are
the record. **`speckit_schema` fail → `spawn_opus` + halt** (Spec-Kit format drifted) — the
"halt + alert human" rule, encoded in `escalation`.

## Honest trade-off of this bridge

The master-plan `.md` runs from a **priority queue**, not a hard DAG. Athena topo-sorts the
phase DAG into ascending `priority` so order is preserved, but cross-task *blocking* is not
enforced by the runner. Hard dependency blocking + durable idempotent graph = the **bd path**
(option B), which this bridge intentionally defers.
