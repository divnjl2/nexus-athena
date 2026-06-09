# Hermes Playbook — driving Athena v2 end to end (Phase 8)

Hermes (the NEXUS L2 orchestrator) drives the three planning layers through the Athena MCP
verbs to a populated, dependency-correct bd graph. Execution is **DEFERRED**
(`ralph/INTERFACE.md`) — Hermes hands off the queue, it does not run it.

## Registration (T8.1 — operator/checkpoint step, NOT applied automatically)

Add the `athena` MCP server to the live Hermes config (edits running infra → operator step):

```json
{ "mcpServers": { "athena": {
  "command": "uv", "args": ["run", "python", "-m", "athena_mcp.server"],
  "cwd": "<repo>/mcp/athena_mcp" } } }
```

## Flow — `ATHENA_SPECKIT=on` (primary, 3-layer)

1. **`planner_align(intent)`** — CRISP question → research (ticket hidden) → design → structure,
   under tier gates. AUTONOMOUS: Hermes answers Question-stage forks from project policy —
   never hang on "magic words".
2. **`planner_spec(intent)`** — seed Spec-Kit (phase-by-phase from CRISP, `speckit/seed.md`):
   specify → clarify → plan → tasks → **analyze**. `analyze` is a DENSE consistency gate.
3. **`planner_validate(tasks.md)`** — format + completeness; loop back on failure.
4. **`planner_compile(tasks.md, apply=True)`** — deterministic, idempotent bd graph.
5. **`planner_report()`** for progress; **`planner_replan(trigger)`** on discovered-from /
   analyze failure.
6. **`planner_export_ready()`** — hand the queue to the (deferred) executor. **STOP here** —
   this is the scope boundary.

## Flow — `ATHENA_SPECKIT=off` (2-layer fallback)

`planner_align` → **`planner_plan`** (CRISP `5_plan` → `plan.md`) → `planner_validate` →
`planner_compile` → `planner_report` → `planner_export_ready`.

## Tier gates

| Artifact | Review |
|---|---|
| question / research / design + **analyze** | dense |
| structure / plan / tasks | spot-check |
| code (per issue) | DEFERRED — external gate, see `ralph/INTERFACE.md` |

## Autonomous-mode rules

- Pre-seed Question forks or ensure Hermes answers `planner_question` (else hang — RPI bug #1).
- 3-layer is the most token-heavy; route routine work in `off` mode.
- Scope ends at the populated graph — **Athena never executes**.
