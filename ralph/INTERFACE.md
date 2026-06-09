# Ralph Executor Interface — DEFERRED (Phase 9 stub, NOT implemented in v2)

> v2 scope ends at a populated, dependency-correct Beads graph. The executor ("Ralph")
> is **DEFERRED** — this file is the CONTRACT only, so a later iteration can plug it in
> without changing the planner. A full reference implementation exists at git tag
> **`v1-full`** (`ralph/{loop,gate,run_openhands,run_claurst}.sh` + `AGENTS.md`).

## Contract

The executor consumes the graph the planner produced and drives it to done:

```
bd ready --json  →  claim issue  →  executor runs ONE issue  →  external gate  →  bd close
```

- **Queue handoff:** the planner exposes the queue via `planner_export_ready`
  (`bd ready --json`). The planner NEVER executes — it only hands off.
- **Routing:** `autonomy:high` label → OpenHands (sandboxed Docker, `--max-iterations`);
  else → Claurst (lightweight one-shot).
- **External gate is AUTHORITATIVE:** the issue's `success_check` is run by an external
  gate; the executor's self-report does NOT count. (Reference: `v1-full` `ralph/gate.sh`
  — timeout + restricted shell + optional `GATE_ALLOWLIST`.)
- **Fresh context per issue:** one issue = one iteration; the executor session is killed
  after each pass, so the next starts clean.
- **Discovered work:** out-of-scope findings → `bd create ... --label discovered-from:<id>`,
  never silent scope expansion.
- **Loop safety (from `v1-full` review):** claim-race guard, gate-failed livelock guard
  (`gate-failed` label + stop), `MAX_ITER` cap, `bd ready` JSON validation.

## Why DEFERRED

Keeping the scope boundary at "graph populated" lets the three planning layers
(CRISP → Spec-Kit → compile) stabilize before execution is wired. The interface above is
sufficient to graft Ralph later WITHOUT touching the planner (`plan2beads` / parsers / MCP).
