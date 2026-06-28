# Provenance Graph — Nodes, Edges, Beads Mapping (v3)

## Invariant: semantic edges -> native Beads primitives

Never invent edge types that `bd` doesn't support. Map everything to bd's built-in
parent-child + related/label conventions.

## Nodes

| Semantic node | Beads implementation |
|---|---|
| `spec` | issue with `--label kind:spec --label athena:spec:<spec_version>` |
| `design` | issue with `--label kind:design --label athena:design:<design_version>`, parent=spec-node |
| `scenario` | issue with `--label kind:scenario --label athena:scenario:<scenario_version>` (v3.1) |
| `epic` (phase) | epic with parent=design-node (v3) or standalone (v2 compat) |
| `task` | issue with parent=epic |

## Edges

| Semantic edge | Beads implementation |
|---|---|
| `derived-from` (spec->design) | parent-child: design.parent = spec-node |
| `derived-from` (design->epic) | parent-child: epic.parent = design-node |
| `derived-from` (epic->task) | parent-child: task.parent = epic |
| `refines` (backedge) | `bd related <research-issue> <spec-node> --label refines` + bump spec_version |
| `verifies` (scenario->spec) | `bd related <scenario> <spec-node> --label verifies` (v3.1) |
| `satisfies` (task->scenario) | `bd related <task> <scenario> --label satisfies` (v3.1) |
| `implements` (commit->task) | git commit message with issue ID + `--label implements` (Phase 10, DEFERRED) |

## Multi-level parent-child

If `bd` supports 3+ levels: spec -> design -> epic -> task (native parent-child).
If bd only supports 2 levels: spec->design via `related --label derived-from`, rest parent-child.
Check with `bd --help` before assuming depth.

## Traversal (query-able via bd)

- **Downstream** (`planner_trace_down`): from spec_version down derived-from chain
  -> "what grew from this requirement"
- **Upstream** (`planner_trace_up`): from task/commit up to spec
  -> "why does this code exist"
- **Proof axis** (`planner_trace_proof`): verifies/satisfies traversal
  -> "is requirement X currently satisfied" (v3.1)

## External key scheme

```
athena:<plan-slug>:spec:<spec_version>
athena:<plan-slug>:design:<design_version>
athena:<plan-slug>:scenario:<scenario_id>
athena:<plan-slug>:<phase_key>          (epic)
athena:<plan-slug>:<task_id>            (issue)
```

All keys are idempotent — creating the same key twice is a no-op (upsert via label lookup).
spec-node in particular MUST survive across multiple compile runs of the same spec_version.
