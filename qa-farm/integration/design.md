# Design: Integration-Testing QA Workflow-Microservice (CRISP)

> CRISP design — the technical `how`. Bridges `spec.md` (what/why, tech-free) to `plan.md`
> (tasks + success_checks). `design.md` is hashed into the provenance graph as
> `design_version`. Technology decisions live here, not in the spec.

## C — Context

- **Part of** the 23-domain NEXUS QA farm; this is domain **#2 (Integration Testing)**,
  built directly after the domain-#1 (Unit) pilot and sharing its L0/L1/L2 shape.
- **Consumes** the QA deep-research L0/L1/L2 maturity model: L0 = atomic MCP primitives,
  L1 = workflow tools, L2 = an autonomous agent, all orchestrated by Hermes with human
  gates.
- **Runs against** a *target* repository (the repo under QA), not against itself. Its own
  code lives in `qa_integration/` and is unit-tested like any product code (every
  `success_check` is a `pytest` over `qa_integration/tests/`).
- **Differs from domain #1** in one load-bearing way: every assertion here runs against
  REAL dependencies (a real Postgres, a real Redis, a real sibling service) brought up via
  `docker-compose` / `testcontainers-python`, never mocks or in-process fakes. That is why
  this domain needs a dependency-health gate and an isolation manager that domain #1 does
  not.
- **Boundary:** implementation of the target's product code, and standing up the target's
  own compose/testcontainers topology, are out of scope. This service only *tests, gates,
  proposes, triages, and reports* against an existing topology — the same boundary the
  human QA has, one layer up from unit.

## R — Requirements mapping (design decisions per requirement group)

| Req | Design decision | Tech |
|-----|-----------------|------|
| R1 change-scope | test-impact analysis over git diff mapped to declared boundaries + reverse-dep closure; fallback on compose/shared-fixture edits | `pytest-testmon`-style boundary diff, `git` diff, `docker compose config` diff |
| R2 dependency-health | probe every declared dependency's health endpoint before trusting results; down/timeout = loud fail, never a skip | `testcontainers-python` wait strategies, docker healthcheck, `tenacity` bounded retry+timeout |
| R3 integration coverage | per-boundary line/branch coverage; zero-coverage boundary is a hard block | `coverage.py` (per-boundary contexts), `pytest-cov`, `diff-cover` |
| R4 isolation | rollback/recreate dependency state; pre-test fingerprint check for bleed; forced serial for unresettable deps | DB transactional rollback / snapshot restore, `testcontainers-python` ephemeral containers, `pytest-xdist` with a serial marker |
| R5 slow/flaky | per-test time budget → quarantine; same-commit rerun confirms flaky; consistent failure stays red | `pytest-timeout`, `pytest-rerunfailures`, `pytest-randomly`, quarantine store |
| R6 reporting | structured, machine-readable, includes dependency health | JUnit XML + `allure-pytest` |
| R7 CI gate | blocking PR status; 10-minute budget guard | GitHub Actions / GitLab CE; wall-clock guard |
| R8 HITL | fix proposals never auto-apply; approval-gated apply; manifest of decision points | signed approval record + `hitl_manifest.json`; `gh` PR / git patch |

## I — Interfaces & architecture (the L0/L1/L2 pie)

```
                 ┌───────────────────────────────────────────────────────┐
   L2 AGENT      │  Env-Fix Proposal Agent (LangGraph / Hermes)           │
                 │  find dep-health issue -> draft fix -> open PR/patch   │
                 │  -> wait HITL, never apply itself                     │
                 └────────────────────────┬──────────────────────────────┘
                                          │ calls
                 ┌────────────────────────┴──────────────────────────────┐
   L1 TOOLS      │ run_changed_integration_tests                         │
                 │ dependency_health_gate . integration_coverage_gate     │
                 │ isolation_manager . slow_flaky_triage . report         │
                 └────────────────────────┬──────────────────────────────┘
                                          │ compose
                 ┌────────────────────────┴──────────────────────────────┐
   L0 PRIMITIVES │ pytest_run_integration . changed_boundaries            │
                 │ coverage_parse_integration . dependency_health_probe   │
                 │ (atomic, MCP-wrapped, pure I/O, exercise REAL deps     │
                 │  via docker-compose / testcontainers)                 │
                 └─────────────────────────────────────────────────────────┘
```

- **L0 primitives** are thin, pure, JSON-in/JSON-out wrappers (MCP-exposable). No policy —
  they run a tool against a live dependency stack and parse its output. Deterministic,
  individually unit-tested (the primitives' own tests are ordinary unit tests; only the
  *target*-facing runs exercise real infra).
- **L1 workflow tools** compose primitives into a decision: `dependency_health_gate` =
  `dependency_health_probe` over every declared dependency → PASS only if all are healthy;
  `integration_coverage_gate` = `coverage_parse_integration` + per-boundary thresholds →
  PASS/FAIL; `isolation_manager` = reset/fingerprint/serialize policy around
  `pytest_run_integration`. Policy (thresholds, `boundaries.toml`, `dependencies.toml`)
  lives here, read from config.
- **L2 agent** is the only stateful/LLM piece: it turns a dependency-health/environment
  issue into a proposed fix and drives the PR/patch, then *stops* at the HITL boundary. It
  never applies a fix to a shared or production environment itself.
- **Config** (`qa_integration.toml`): `boundary_coverage_threshold=75`,
  `health_timeout_s=5`, `budget_seconds=600`, `slow_test_budget_s=30`, `rerun=2`.

### HITL points (R8.3 manifest)
1. **approve-environment-fix** — a person reviews & approves before an environment/
   dependency fix proposal is applied to any shared or production environment.
2. **classify-ambiguous-flaky** — when flaky confidence < 0.8, a person makes the call.
3. **move-gate-threshold** — changing a coverage/health/budget threshold is a human
   decision, never auto-tuned.
4. **waive-dependency-outage** — if a known-flaky external dependency is down for reasons
   outside the target repo's control, only a human can record an explicit, logged waiver;
   the system never infers one on its own.

## S — Strategy for failure & edge cases

- **EC-1 no-change** → `changed_boundaries` returns ∅ → short-circuit to "no relevant
  change", exit 0. Never a full-run fallback (that is EC-2 only).
- **EC-2 compose/fixture change** → detected by path match (`docker-compose.yml`,
  `docker-compose.override.yml`, shared `conftest.py`, `.env.test`) → force full run
  (R1.3). Under-selection is the danger.
- **EC-3 zero-coverage new boundary** → `coverage_parse_integration` reports 0% on that
  boundary → hard FAIL, distinct from "no data".
- **EC-4 dependency down** → `dependency_health_probe`/`dependency_health_gate` fails loud
  and names the dependency (R2.2); a timeout is treated identically to a hard-down
  response (R2.3), never as a skip.
- **EC-5 cross-test bleed** → a pre-test state fingerprint mismatch is detected by
  `isolation_manager` before the test body runs → the run is blocked and the colliding
  tests are named (R4.2).
- **EC-6 flaky masquerade** → classify flaky ONLY on confirmed pass+fail on the *same*
  commit hash; a real failure with consistent fails stays red. `rerun` is capped (default
  2).
- **EC-7 budget breach** → a wall-clock guard emits a `budget_breach` result object; the
  run does not hang and does not silently pass.

## P — Plan hook

`plan.md` phases follow the pie bottom-up, folding isolation and slow/flaky triage into one
phase (both are "don't trust stale/noisy state" concerns at the same L1 layer) to keep the
farm's 7-phase shape: Phase 1 L0 primitives → Phase 2 L1 tools (selection + dependency
health + coverage) → Phase 3 L2 Env-Fix Proposal Agent → Phase 4 isolation + slow/flaky
triage → Phase 5 reporting → Phase 6 CI + Hermes wiring → Phase 7 verification harness.
Every task's `success_check` is a `pytest` over `qa_integration/`, and every task
`verifies` a scenario `S<n>.<m>`, so the provenance chain `task → scenario → requirement`
is complete and compilable by `athena.py`.

## Reuse (don't reinvent)

- **Athena** itself compiles this plan → Beads graph → Hermes master-plan, exactly as it
  did for domain #1 (`qa-farm/unit/`). We author the front; Athena does the graph.
- **Hermes** provides the persistent orchestration + HITL routing (`hermes/ATHENA_TASK.yaml`
  pattern) — the L2 agent registers as a Hermes workflow, not a bespoke daemon.
- **Domain #1's scaffolding** is reused where the shape matches: the quarantine-store
  concept and the `hitl_manifest.json` schema are the same shape as `qa_unit/`'s, extended
  with dependency-health and per-boundary fields — not reinvented.
- Existing OSS does the heavy lifting (pytest/testcontainers/coverage.py/allure); the
  microservice is *glue + policy + the agent*, not a new test framework and not a new
  container orchestrator.
