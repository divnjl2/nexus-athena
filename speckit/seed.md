# Seeding Spec-Kit from CRISP — phase by phase (§5)

Avoid the impedance mismatch of dumping one big document into Spec-Kit. Seed it per CRISP
phase, matching each CRISP artifact to the Spec-Kit step that consumes it:

- CRISP **Q + R** (problem understanding) → seed `specify` → `spec.md`
  (requirements / user stories) → `clarify`.
- CRISP **D + S** (the solution) → seed `plan` → `plan.md` (architecture).
- then `tasks` → `tasks.md` — strict checklist with `[P]` + `[Story]` markers and the
  Athena preset's per-task `success_check`.
- `analyze` → consistency gate (dense-reviewed, like the alignment artifacts).

## Overlap cut (invariant §5)

In 3-layer mode (`ATHENA_SPECKIT=on`):
- CRISP's own `5_plan` is **NOT used** — Spec-Kit does the planning.
- Spec-Kit's `implement` is **NOT used** — execution is deferred to our Ralph (`ralph/INTERFACE.md`).

In 2-layer fallback (`ATHENA_SPECKIT=off`): skip Spec-Kit entirely; CRISP runs through
`5_plan.md` (canonical format) and `plan_parser` compiles it.
