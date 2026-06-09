# Athena — Hermes-friendly Planner

A thin layer over two existing third-party repos:

- **QRSPI** — the planning prompt-chain front (`matanshavit/qrspi`, optionally `dfrysinger/qrspi-plus`).
- **Beads `bd`** — a durable task-graph on Dolt (`gastownhall/beads`).

Packaged as a **Claude Code plugin + MCP server**. **Hermes** (the NEXUS L2 orchestrator)
drives the planning cycle through MCP verbs and feeds a **Ralph loop** that executes one
issue at a time via **OpenHands** (isolated/autonomous) or **Claurst** (fast/lightweight).

Full spec: [`athena-final-opus-plan.md`](./athena-final-opus-plan.md).

## What we write vs. vendor (§0)

| Layer | Source | Ours? |
|---|---|---|
| QRSPI prompt-chain | vendored (`vendor/qrspi/`) | no — we adapt output format only |
| Beads `bd` task-graph | install (`gastownhall/beads` v1.x) | no |
| `plan2beads` (deterministic `plan.md` → `bd`) | **us** | **yes — the core** |
| Athena MCP server (verbs for Hermes) | **us** | **yes** |
| Ralph loop + external gate + executor router | **us** | **yes** |
| OpenHands / Claurst (executors) | install | no |

## Layout (§2)

```
nexus-athena/                      # [Phase 0 ✓] = built  |  [Phase N] = defined in §9, not yet built
├── .claude-plugin/plugin.json     # Claude Code plugin manifest                       [Phase 0 ✓]
├── lib/plan2beads.py              # DETERMINISTIC compiler skeleton (§5)              [Phase 0 ✓ — split in Phase 2]
├── vendor/qrspi/                  # vendored QRSPI templates @8d71051                 [Phase 0 ✓]
├── install.sh                     # bd + plugin + MCP + executor setup               [Phase 0 ✓]
│
├── skills/plan-format/SKILL.md    # canonical plan.md contract (§4)                   [Phase 1]
├── lib/plan_parser.py             # plan.md → dataclasses (§4)                        [Phase 2]
├── lib/bd_client.py               # the only subprocess boundary                      [Phase 2]
├── tests/                         # golden + idempotency + negative + bd-contract     [Phase 2]
├── commands/qrspi/                # adapted planning front: 1_question … 5_plan       [Phase 3]
├── commands/compile.md            # /athena.compile → plan2beads                      [Phase 3]
├── agents/                        # documentarian subagents (describe, never propose) [Phase 3]
├── mcp/athena_mcp/                # FastMCP server — verbs for Hermes (§6)            [Phase 4]
├── hooks/hooks.json               # SessionStart: bd prime; PreCompact: bd sync       [Phase 4]
└── ralph/                         # loop.sh + gate.sh + run_*.sh (§8)                 [Phase 5]
```

## Vendored QRSPI provenance

- Source: <https://github.com/matanshavit/qrspi>
- Pinned commit: **`8d710510643ab483708fd127bd7c9b4ca2951f48`**
- Vendored: 2026-06-09 — `commands/qrspi/*.md` (8 stages: question → research → design → structure → plan → worktree → implement → pr) + `agents/*.md` (4 documentarians).
- Note: the acronym **QRSPI** = Question, Research, Structure, Plan, Implement is a 5-letter mnemonic over an 8-phase pipeline; **Design / Worktree / PR are real stages without an acronym letter** (`S` = Structure, not Design). Athena consumes only the 5 alignment stages + the canonical `plan.md`; execution (worktree/implement/pr) is replaced by our Beads + Ralph layer.

## Quick start

```bash
bash install.sh        # installs bd (Beads v1.x), bd init, registers plugin + MCP, checks OpenHands V1
```

## Build status

Phase 0 (scaffold + vendoring + version pins) complete. Phases 1–7 are defined in
`athena-final-opus-plan.md` §9; each task carries an executable `success_check` and is
not closed until it returns exit 0.

## License

MIT (the vendored QRSPI templates retain their upstream MIT license — see `vendor/qrspi/LICENSE`).
