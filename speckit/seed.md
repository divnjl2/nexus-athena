# Spec-Kit seed — what/how boundary contract (v3)

## Spec is the logical root

`/athena.spec` (`/specify`) produces `spec.md` — the "what + why".
Everything below is `derived-from` the spec:

```
spec.md  (what + why, EARS criteria)  <- ROOT, spec_version
  -> scenarios.md  (EARS->GWT, scenario_version)   [v3.1]
  -> design.md     (how, via QRSPI, design_version)
  -> tasks.md      (checklist, derived from design)
  -> graph         (Beads provenance tree)
```

## Invariant: what/how boundary is iron

- **Spec-Kit owns "what + why"**: requirements, user stories, acceptance criteria.
  NO tech stack, NO implementation details in spec.md.
- **QRSPI owns "how"**: architecture, tech choices, open questions.
  QRSPI reads spec as a frozen contract — it does NOT rewrite "why".
- If QRSPI research reveals the spec is wrong: `planner_replan(trigger="spec_invalid")`
  fires the backedge (research -> /specify), bumps spec_version, then re-runs QRSPI.

## Seeding QRSPI from spec (phase by phase)

Feed the frozen spec.md into QRSPI's question stage with context scoped to "how":

- `question` (CRISP 1): "how do we build this / what are the technical unknowns?"
  NOT "what do we want" — the spec already answers that.
- `research` (CRISP 2): technical investigation, fed by frozen spec (not the ticket)
- `design` (CRISP 3): produces `design.md`, versioned + pinned to `(spec_version, run_id)`

## Seeding tasks from design

- `plan` + `tasks` (Spec-Kit, `ATHENA_SPECKIT=on`): produce `tasks.md` from design.md
  Each task has `success_check` (in v3.1: = `run_cmd` of its bound scenario)
- CRISP's own `5_plan` is NOT used in 3-layer mode — Spec-Kit does the planning.
- Spec-Kit's `implement` is NOT used — execution is deferred to `ralph/INTERFACE.md`.

## 2-layer fallback (`ATHENA_SPECKIT=off`)

Skip Spec-Kit; write spec manually or via CRISP artifacts. Spec is still the logical root
but managed by the operator. CRISP `5_plan` produces canonical `plan.md`; `plan_parser`
compiles it. Provenance fields can still be populated manually.
