# Hermes Playbook — driving Athena end to end (Phase 6)

Hermes (the NEXUS L2 orchestrator) drives the full planning + execution cycle through
the Athena MCP verbs. Goal: one Hermes prompt -> a populated `bd` graph -> an autonomous
Ralph run that closes the queue.

## Registration (T6.1 — operator/checkpoint step, NOT applied automatically)

Add the `athena` MCP server to the Hermes client config (e.g. `.mcp.json` or the Hermes
MCP registry). This edits live Hermes config, so it is left to the operator:

```json
{
  "mcpServers": {
    "athena": {
      "command": "uv",
      "args": ["run", "python", "-m", "athena_mcp.server"],
      "cwd": "<repo>/mcp/athena_mcp"
    }
  }
}
```

Verify with the MCP inspector / Hermes tool list that `planner_*` verbs appear.

## Flow (T6.2)

1. **`planner_align(intent, repo_path)`** — runs Question -> Research (ticket hidden) ->
   Design -> Structure under tier gates. AUTONOMOUS: Hermes answers Question-stage forks
   from project policy/context — never hang on "magic words".
2. **`planner_plan(structure_path)`** — emit the canonical `plan.md` (the compiler contract).
3. **`planner_validate(plan_path)`** — format + completeness gate; loop back to plan on failure.
4. **`planner_compile(plan_path, apply=True)`** — deterministic, idempotent `bd` graph
   (epics / issues / dependency edges).
5. **Loop**: `planner_next()` -> [executor runs the issue via `ralph/loop.sh`] ->
   `gate.sh` -> `planner_complete(id, gate_passed)`. Repeat until `next()` returns null.
6. **`planner_report()`** for progress; **`planner_replan(trigger)`** on discovered-from
   issues / gate failures to backtrack to the right QRSPI stage.

## Autonomous-mode rules

- Pre-seed design-fork answers in the ticket OR ensure Hermes answers `planner_question`
  (else the run hangs — RPI failure mode #1).
- Hard caps so it can't burn the night: `MAX_ITER` (loop.sh), `--max-iterations`
  (OpenHands), `GATE_TIMEOUT` (gate.sh).
- External gate only — executor self-report never closes an issue.

## Tier-gate mapping

| Artifact | Review depth |
|---|---|
| questions / research / design | dense (alignment — decides if we build the right thing) |
| structure / plan | spot-check |
| code (per issue) | `gate.sh` success_check (authoritative) |
