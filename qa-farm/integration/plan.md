# Plan: Integration-Testing QA Workflow-Microservice

## Overview
Build the domain-#2 microservice of the NEXUS QA farm bottom-up along the same L0/L1/L2
pie used by domain #1, but scoped to integration-level QA: tests run against REAL
dependencies (docker-compose / testcontainers), gated on dependency health, per-boundary
integration coverage, and test isolation. The service tests a *target* repo's integration
surface; its own code is `qa_integration/` and every task is proven by an executable
`pytest` success_check whose result is a proof that a scenario in `scenarios.md` holds. The
end state is every EARS criterion validated by a green success_check with the provenance
chain `task → scenario → requirement` compiled by Athena.

## Out of Scope
- Implementing the target repository's product code or its service boundaries (the service
  tests, it does not build).
- Unit-level QA (domain #1, `qa_unit/`) and the other 21 QA domains (contract, e2e, perf,
  security, …) — separate microservices.
- Auto-tuning thresholds or auto-applying environment fixes to shared/production
  environments (both are HITL by design).
- Standing up the target repo's own docker-compose/testcontainers topology — this service
  consumes an existing one, it does not design it.
- Cross-repo orchestration policy — owned by the Hermes farm layer, not this microservice.

## Phase 1: L0 primitives — atomic, pure, MCP-wrapped
**Goal:** Thin JSON-in/JSON-out wrappers over the underlying tools, run against real
dependencies; deterministic, no policy.
**Depends on:** none
### Tasks
- [ ] T1.1 Implement pytest_run_integration primitive: run a pytest node set against a live dependency stack, return structured pass/fail/duration JSON
  - success_check: `pytest qa_integration/tests/test_pytest_run_integration.py -q`
  - files: `qa_integration/primitives/pytest_run_integration.py, qa_integration/tests/test_pytest_run_integration.py`
  - autonomy: high
- [ ] T1.2 Implement changed_boundaries primitive: git diff → changed service boundaries + reverse-dep closure
  - success_check: `pytest qa_integration/tests/test_changed_boundaries.py -q`
  - files: `qa_integration/primitives/changed_boundaries.py, qa_integration/tests/test_changed_boundaries.py`
  - autonomy: high
- [ ] T1.3 Implement coverage_parse_integration primitive: coverage.xml → per-boundary line/branch + delta vs base
  - success_check: `pytest qa_integration/tests/test_coverage_parse_integration.py -q`
  - files: `qa_integration/primitives/coverage_parse_integration.py, qa_integration/tests/test_coverage_parse_integration.py`
  - autonomy: high
- [ ] T1.4 Implement dependency_health_probe primitive: probe each declared dependency's health endpoint, return healthy/unhealthy + latency JSON with a bounded timeout
  - success_check: `pytest qa_integration/tests/test_dependency_health_probe.py -q`
  - files: `qa_integration/primitives/dependency_health_probe.py, qa_integration/tests/test_dependency_health_probe.py`
  - autonomy: high
### Manual Verification
- Call each primitive against a docker-compose fixture stack; confirm the JSON shape is
  stable and tool-agnostic.

## Phase 2: L1 workflow tools — composition + policy
**Goal:** Compose primitives into gate decisions; thresholds, boundaries, and declared
dependencies read from config.
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 Implement run_changed_integration_tests: changed_boundaries + pytest_run_integration over the affected boundary set
  - success_check: `pytest qa_integration/tests/test_select.py::test_selects_boundary_scoped_only -q`
  - files: `qa_integration/tools/run_changed_integration_tests.py, qa_integration/tests/test_select.py`
  - verifies: S1.1
  - autonomy: high
- [ ] T2.2 Handle the empty affected set: short-circuit to "no relevant change", exit 0, no full-run fallback
  - success_check: `pytest qa_integration/tests/test_select.py::test_no_relevant_change_runs_nothing -q`
  - files: `qa_integration/tools/run_changed_integration_tests.py, qa_integration/tests/test_select.py`
  - verifies: S1.2
  - autonomy: high
- [ ] T2.3 Implement dependency_health_gate: probe all declared deps before trusting results; a down or timed-out dep fails loud and names the dependency
  - success_check: `pytest qa_integration/tests/test_gate_dependency.py -q`
  - files: `qa_integration/tools/dependency_health_gate.py, qa_integration/tests/test_gate_dependency.py`
  - verifies: S2.1 S2.2 S2.3
  - autonomy: high
- [ ] T2.4 Implement integration_coverage_gate: per-boundary threshold block + zero-coverage-on-new-boundary hard block
  - success_check: `pytest qa_integration/tests/test_gate_coverage.py -q`
  - files: `qa_integration/tools/integration_coverage_gate.py, qa_integration/tests/test_gate_coverage.py`
  - verifies: S3.1 S3.2
  - autonomy: high
- [ ] T2.5 Implement compose/shared-fixture fallback: force the full integration run when docker-compose or shared fixtures change
  - success_check: `pytest qa_integration/tests/test_select.py::test_compose_change_full_fallback -q`
  - files: `qa_integration/tools/run_changed_integration_tests.py, qa_integration/tests/test_select.py`
  - verifies: S1.3
  - autonomy: high
### Manual Verification
- Stop a declared dependency container; confirm the gate fails loud and names it.
- Touch `docker-compose.yml`; confirm selection falls back to the full run, not a subset.

## Phase 3: L2 Env-Fix Proposal Agent — propose, never apply
**Goal:** Turn a dependency-health or environment issue into a reviewed fix proposal; stop
at the HITL boundary.
**Depends on:** Phase 2
### Tasks
- [ ] T3.1 Implement env-issue finder: given a failed dependency-health probe, identify the fix target (compose service, env var, config key) with file+line
  - success_check: `pytest qa_integration/tests/test_envfix.py::test_finds_issue_target -q`
  - files: `qa_integration/agent/envfix_finder.py, qa_integration/tests/test_envfix.py`
  - autonomy: high
- [ ] T3.2 Implement fix generator: draft the candidate fix content (compose patch / env var / config diff) from the identified issue
  - success_check: `pytest qa_integration/tests/test_envfix.py::test_drafts_candidate_fix -q`
  - files: `qa_integration/agent/envfix_generator.py, qa_integration/tests/test_envfix.py`
  - autonomy: low
- [ ] T3.3 Implement proposal emitter: deliver the candidate fix as a PR/patch; hold no apply credential to shared or production environments
  - success_check: `pytest qa_integration/tests/test_envfix.py::test_delivers_proposal_never_auto_applies -q`
  - files: `qa_integration/agent/envfix_pr.py, qa_integration/tests/test_envfix.py`
  - verifies: S8.1
  - autonomy: low
### Manual Verification
- Force a dependency-health failure on a fixture stack; confirm a fix proposal is drafted
  and NO apply action is attempted by the agent.

## Phase 4: Isolation & slow/flaky triage — no bleed, no masking
**Goal:** Guarantee no test's dependency state survives into the next test, and isolate
slow/flaky noise without hiding a real failure.
**Depends on:** Phase 2
### Tasks
- [ ] T4.1 Implement isolation manager: roll back or recreate dependency state after each test, detect cross-test bleed via a pre-test fingerprint and block the run, force serial execution when a dependency cannot be reset
  - success_check: `pytest qa_integration/tests/test_isolation.py -q`
  - files: `qa_integration/tools/isolation_manager.py, qa_integration/tests/test_isolation.py`
  - verifies: S4.1 S4.2 S4.3
  - autonomy: high
- [ ] T4.2 Implement slow/flaky triage: quarantine over-time-budget tests without blocking, classify flaky only on confirmed same-commit pass+fail, track flaky separately so a consistent real failure stays red
  - success_check: `pytest qa_integration/tests/test_triage.py -q`
  - files: `qa_integration/tools/slow_flaky_triage.py, qa_integration/tests/test_triage.py`
  - verifies: S5.1 S5.2 S5.3
  - autonomy: high
### Manual Verification
- Inject a test that leaves dirty state; confirm the next test detects the bleed and the
  run blocks.
- Inject one over-budget test, one flaky test, and one real failure; confirm the
  quarantine/flaky classification is correct and the build stays red on the real failure.

## Phase 5: Reporting & metrics — one honest report
**Goal:** Emit structured JUnit + Allure with the required metric fields, including
dependency health.
**Depends on:** Phase 2
### Tasks
- [ ] T5.1 Implement reporter: serialise a run to JUnit XML + Allure result dir, both well-formed
  - success_check: `pytest qa_integration/tests/test_report.py::test_emits_junit_and_allure -q`
  - files: `qa_integration/tools/report.py, qa_integration/tests/test_report.py`
  - verifies: S6.1
  - autonomy: high
- [ ] T5.2 Populate metrics block: pass rate, per-boundary coverage, dependency-health status, runtime, flaky rate
  - success_check: `pytest qa_integration/tests/test_report.py::test_report_has_required_metrics -q`
  - files: `qa_integration/tools/report.py, qa_integration/tests/test_report.py`
  - verifies: S6.2
  - autonomy: high
### Manual Verification
- Open the Allure report; confirm every required metric field, including dependency
  health, is present and populated.

## Phase 6: CI + Hermes integration — blocking gate, HITL manifest
**Goal:** Run as a blocking PR gate within budget and register HITL points with Hermes.
**Depends on:** Phase 3, Phase 4, Phase 5
### Tasks
- [ ] T6.1 Wire the PR gate: aggregate tool results into a single blocking (non-zero) CI status
  - success_check: `pytest qa_integration/tests/test_ci_gate.py::test_pr_gate_blocks_on_fail -q`
  - files: `qa_integration/ci/pr_gate.py, qa_integration/tests/test_ci_gate.py`
  - verifies: S7.1
  - autonomy: default
- [ ] T6.2 Implement the wall-clock budget guard: emit a first-class budget_breach on overrun
  - success_check: `pytest qa_integration/tests/test_ci_gate.py::test_budget_breach_is_first_class -q`
  - files: `qa_integration/ci/budget.py, qa_integration/tests/test_ci_gate.py`
  - verifies: S7.2
  - autonomy: high
- [ ] T6.3 Emit hitl_manifest.json and register the microservice as a Hermes workflow
  - success_check: `pytest qa_integration/tests/test_hitl.py::test_hitl_manifest_enumerates_points -q`
  - files: `qa_integration/ci/hitl_manifest.py, qa_integration/hermes/workflow.yaml, qa_integration/tests/test_hitl.py`
  - verifies: S8.3
  - autonomy: default
### Manual Verification
- Open a failing PR on a fixture repo; confirm merge is blocked and the manifest is
  published.

## Phase 7: Verification harness — prove the whole loop
**Goal:** Lock the Success Criteria as automated checks end-to-end on a sample target stack.
**Depends on:** Phase 6
### Tasks
- [ ] T7.1 Add an e2e run against a fixture target stack (docker-compose up): change → select → health → gate → report
  - success_check: `pytest qa_integration/tests/test_e2e.py -q`
  - files: `qa_integration/tests/test_e2e.py`
  - autonomy: default
- [ ] T7.2 Add HITL enforcement test: an environment fix cannot be applied without a recorded approval
  - success_check: `pytest qa_integration/tests/test_hitl.py::test_env_fix_requires_approval -q`
  - files: `qa_integration/tests/test_hitl.py`
  - verifies: S8.2
  - autonomy: default
- [ ] T7.3 Full suite gate: run the entire qa_integration test suite green
  - success_check: `pytest qa_integration -q`
  - files: `qa_integration/tests/`
  - autonomy: high
### Manual Verification
- Run `pytest qa_integration -q`; confirm zero failures and that the provenance chain
  compiles in Athena.
