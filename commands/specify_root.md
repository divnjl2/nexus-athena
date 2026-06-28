# /athena.spec — Spec-Kit specify (ROOT)

Invoke Spec-Kit `/specify` to produce `spec.md` — the logical root of the provenance graph.
Everything else (design, scenarios, tasks, graph) is `derived-from` the spec.

## When to use

Use this FIRST, before any CRISP/QRSPI or planning steps. The spec defines "what + why";
CRISP/QRSPI answers "how" from the frozen spec.

## What it produces

- `spec.md` — requirements, user stories, acceptance criteria (EARS format preferred)
- `spec_version` — SHA prefix of spec.md, written to `.athena/seams.jsonl`

## Invocation

```
/specify
```

Then pin the output:
```python
from lib.versioning import pin_output
spec_version = pin_output("spec", run_id, "spec.md", ts=<iso_ts>)
```

## Invariants

- Spec owns "what + why" — NO tech stack details in spec.md
- QRSPI owns "how" — reads spec as a frozen contract, does NOT rewrite "why"
- If research reveals the spec is wrong: use `planner_replan(trigger="spec_invalid")`
  to bump spec_version via the backedge, then re-run QRSPI from the new spec

## Acceptance criteria format (EARS)

Prefer EARS-style criteria that translate directly to scenarios:
```
WHEN <trigger> THE SYSTEM SHALL <response>
```
These map 1:1 to `Scenario.gwt_text` in `/athena.scenarios`.
