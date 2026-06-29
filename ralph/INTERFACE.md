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

## Multi-agent executor layer (`ralph/adapter.py`)

Execution is **agent-agnostic**. The same plan is driven to done by whichever executor you
have — they are interchangeable behind one `ExecutorAdapter` contract:

| Adapter | `name` | When |
|---|---|---|
| `ClaudeCodeAdapter` | `claude_code` | default |
| `OpenCodeAdapter` | `opencode` | default alt |
| `OpenHandsAdapter` | `openhands` | sandboxed; `autonomy:high` issues |
| `HermesAdapter` | `hermes` | the autonomous swarm |

```
issue ─ select_adapter() ─►  adapter.run_issue()  ─►  external gate  ─►  close_with_provenance()
        routing: agent:<name> label > autonomy:high→openhands > default
```

- `adapter.command(issue, workdir)` is **pure** (returns the CLI argv) → testable without
  running an agent. `run_issue()` executes it.
- **One issue = one Ralph iteration**, fresh context, external gate authoritative — unchanged.

## The code ↔ spec link is written in ONE place (`close_with_provenance`)

Every adapter — Claude Code, OpenCode, OpenHands, Hermes — closes the loop through the
**same** `close_with_provenance(issue_key, ExecResult, spec_version, scenario_version, run)`.
That single function fills the bidirectional link (v4) identically regardless of which agent
did the work, so **swapping the executor never changes the provenance graph**:

```
bd label add implements           <issue>    # the reserved v3 edge, now filled
bd label add commit:<sha>         <issue>    # native Beads commit↔issue linkage
bd label add spec_version:<sv>    <issue>    # version stitching (drift detection)
bd label add scenario_version:<scv> <issue>
bd label add agent:<name>         <issue>    # which executor (the ONLY per-agent difference)
bd close <issue>
```

`implements` is a **label**, not a `bd link --type` (the native types are
blocks|tracks|related|parent-child|discovered-from — `implements` isn't one), and that is
exactly what `trace_up(commit)` and the drift detector query via `bd list --label`. Only a
**passed external gate** triggers the close; a fail leaves the issue open (livelock guard).

See `athena-opus-plan-v4-bidirectional.md` for the full two-sided trace this enables
(`trace_down(spec)→commit`, `trace_up(commit)→spec`, `detect_drift`).

## Why DEFERRED

Keeping the scope boundary at "graph populated" lets the three planning layers
(CRISP → Spec-Kit → compile) stabilize before execution is wired. The adapter layer above is
sufficient to graft any executor later WITHOUT touching the planner (`plan2beads` / parsers /
MCP) — and the provenance link is the same for all of them.
