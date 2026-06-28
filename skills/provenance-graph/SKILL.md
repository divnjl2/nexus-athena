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
| `refines` (backedge) | `bd dep add <research-issue> <spec-node> --type supersedes` + bump spec_version |
| `verifies` (scenario->spec) | `bd dep add <scenario> <spec-node> --type validates` (v3.1) |
| `satisfies` (task->scenario) | `bd dep add <task> <scenario> --type tracks` (v3.1) |
| `implements` (commit->task) | git commit message with issue ID (native Beads convention) (Phase 10, DEFERRED) |

> bd v1.0.4 has NO labeled `related` command. Use the native typed-edge form
> `bd dep add <from> <to> --type <t>` where `<t>` is one of bd's built-in types:
> `blocks|tracks|related|parent-child|discovered-from|until|caused-by|validates|relates-to|supersedes`.
> Verified against bd v1.0.4: `validates` (verifies) and `tracks` (satisfies) are
> non-blocking edges; they do NOT gate `bd ready`. Typed edges between nodes already in
> a parent-child chain are rejected (deadlock guard) — scenario/task nodes are standalone
> so verifies/satisfies are safe.

## Multi-level parent-child

VERIFIED against bd v1.0.4: multi-level parent-child works natively via dotted child IDs
(spec `bd-d76` -> design `bd-d76.1` -> epic `bd-d76.1.1` -> task `bd-d76.1.1.1`).
spec -> design -> epic -> task is a valid 4-level hierarchy. No 2-level fallback needed.

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
