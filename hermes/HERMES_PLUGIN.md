# Athena — Hermes plugin (MCP planner + workflows)

The Hermes-side half of the Athena framework. The Claude Code plugin lets a Claude agent
drive the pipeline interactively; THIS lets the **Hermes swarm** drive the same pipeline
autonomously via MCP verbs + workflows.

Two surfaces:
1. **MCP planner** (`mcp/athena_mcp`) — 17 `planner_*` verbs the Hermes agent calls.
2. **Workflows** (`hermes/*.yaml`) — `dispatcher: script` steps for the deterministic tail
   (compile → master-plan → PLAN_RUN execution). See `INTEGRATION.md` for the execution bridge.

## 1. Register the MCP server into Hermes

Add to the Hermes instance's MCP config (hermes-agent `mcpServers`, or the cex-ops profile's
MCP block). `<ATHENA_REPO>` = absolute path (e.g. `C:/Users/пк/Repos/nexus-athena`):

```json
{
  "mcpServers": {
    "athena": {
      "command": "uv",
      "args": ["run", "python", "-m", "athena_mcp.server"],
      "cwd": "<ATHENA_REPO>/mcp/athena_mcp"
    }
  }
}
```

Verify: the Hermes agent should see the 17 `planner_*` tools (`planner_spec`, `planner_align`,
`planner_scenarios`, `planner_compile`, `planner_trace_proof`, ...).

## 2. The verbs (what the swarm drives)

| Stage | Verb | Returns |
|---|---|---|
| spec (root) | `planner_spec(intent)` | dispatch descriptor → host runs `/specify`; spec.md + spec_version |
| align (how) | `planner_align(intent)` | CRISP question→research→design→structure sequence + tier gates |
| scenarios (v3.1) | `planner_scenarios(spec_path)` | EARS→GWT scenarios, scenario_version pinned to spec_version |
| tasks | `planner_plan` / Spec-Kit tasks | the front (tasks.md / plan.md) |
| compile | `planner_compile(front, apply=True)` | front → bd provenance graph |
| verify (v3.1) | `planner_verify(scenarios)` | run the harness → {passed, failed} |
| trace | `planner_trace_down/up/proof` | query the graph: what grew / why / is requirement proved now |
| replan | `planner_replan(trigger)` | backedge (spec_invalid / scenario_failed) → re-derive |
| report | `planner_report` | bd stats across epics |

The CRISP/Spec-Kit verbs return **dispatch descriptors** (`{"command": "/crisp.research",
"note": "host runs the prompt"}`) — the Hermes agent executes the prompt in its loop, then
feeds the artifact path to the next verb. `planner_compile` is deterministic (pure AST → bd).

## 3. Driving playbook (autonomous chain)

A Hermes agent run, one intent → provenance graph:

```
1. planner_spec(intent)              → execute /specify → spec.md, note spec_version
2. planner_scenarios(spec.md)        → execute → scenarios (each a requirement proof)
3. planner_align(intent)             → execute question→research→design (answer "how" forks autonomously)
4. (speckit on) Spec-Kit plan+tasks  → tasks.md   |   (off) planner_plan → plan.md
5. planner_validate(front)           → seams: AST well-formed, compile-pure, schema
6. planner_compile(front, apply=True)→ bd graph: spec→design→epic→task + verifies/satisfies
7. planner_trace_proof(spec_version) → confirm every requirement has a verifying scenario
8. (deferred) ATHENA_PLAN workflow → master-plan → PLAN_RUN executes tasks → checkbox writeback
```

Autonomy rule: on `planner_question` forks the swarm answers only "how" (the spec owns "what").
On `scenario_failed` → `planner_replan` routes code-fix vs spec-fix (§5 v3.1).

## 4. Honest constraint (read before trusting Hermes-driven plan quality)

Spec-Kit's `/specify`, `/clarify` are **Claude-Code-native** slash-command skills. A Hermes
instance on a weaker local model may execute them less faithfully than Claude Code (measured:
the real pipeline on Claude = 92% mean recall across a 5-task set). Two mitigations:
- run the planning front through the Claude Code plugin (or a `claude -p` sub-step) and hand
  Hermes the resulting front for the deterministic compile/execute tail; OR
- accept lower plan recall on the local model and lean on `planner_verify` + the seams as the
  fail-closed gate (objective gate over self-report).

The MCP + workflows make the swarm CAPABLE of driving the pipeline; plan quality is then a
function of which model executes the agent loop, measured by `evals/` independently.
