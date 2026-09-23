---
plan_id: integration-testing-qa-workflow-microservice
owner: divnjl2
risk_tier: T2
requires_approval: false
generated_by: athena
---

# Integration-Testing QA Workflow-Microservice — Build the domain-#2 microservice of the NEXUS QA farm bottom-up along the same L0/L1/L2 pie used by domain #1, but scoped to integration-level QA: tests run against REAL dependencies (docker-compose / testcontainers), gated on dependency health, per-boundary integration coverage, and test isolation.

## Goal (one sentence)
Build the domain-#2 microservice of the NEXUS QA farm bottom-up along the same L0/L1/L2 pie used by domain #1, but scoped to integration-level QA: tests run against REAL dependencies (docker-compose / testcontainers), gated on dependency health, per-boundary integration coverage, and test isolation.

## Acceptance (one criterion)
every task's success_check exits 0

## Non-goals (explicit)
- NO Implementing the target repository's product code or its service boundaries (the service
- NO Unit-level QA (domain #1, `qa_unit/`) and the other 21 QA domains (contract, e2e, perf,
- NO Auto-tuning thresholds or auto-applying environment fixes to shared/production
- NO Standing up the target repo's own docker-compose/testcontainers topology — this service
- NO Cross-repo orchestration policy — owned by the Hermes farm layer, not this microservice.

## Tasks

- [ ] task_id: T1.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/primitives/pytest_run_integration.py,qa_integration/tests/test_pytest_run_integration.py", "phase": "phase1", "success_check": "pytest qa_integration/tests/test_pytest_run_integration.py -q", "title": "Implement pytest_run_integration primitive: run a pytest node set against a live dependency stack, return structured pass/fail/duration JSON"}
  priority: 0
  max_retries: 2

- [ ] task_id: T1.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/primitives/changed_boundaries.py,qa_integration/tests/test_changed_boundaries.py", "phase": "phase1", "success_check": "pytest qa_integration/tests/test_changed_boundaries.py -q", "title": "Implement changed_boundaries primitive: git diff → changed service boundaries + reverse-dep closure"}
  priority: 0
  max_retries: 2

- [ ] task_id: T1.3
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/primitives/coverage_parse_integration.py,qa_integration/tests/test_coverage_parse_integration.py", "phase": "phase1", "success_check": "pytest qa_integration/tests/test_coverage_parse_integration.py -q", "title": "Implement coverage_parse_integration primitive: coverage.xml → per-boundary line/branch + delta vs base"}
  priority: 0
  max_retries: 2

- [ ] task_id: T1.4
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/primitives/dependency_health_probe.py,qa_integration/tests/test_dependency_health_probe.py", "phase": "phase1", "success_check": "pytest qa_integration/tests/test_dependency_health_probe.py -q", "title": "Implement dependency_health_probe primitive: probe each declared dependency's health endpoint, return healthy/unhealthy + latency JSON with a bounded timeout"}
  priority: 0
  max_retries: 2

- [ ] task_id: T2.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/run_changed_integration_tests.py,qa_integration/tests/test_select.py", "phase": "phase2", "success_check": "pytest qa_integration/tests/test_select.py::test_selects_boundary_scoped_only -q", "title": "Implement run_changed_integration_tests: changed_boundaries + pytest_run_integration over the affected boundary set"}
  priority: 1
  max_retries: 2

- [ ] task_id: T2.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/run_changed_integration_tests.py,qa_integration/tests/test_select.py", "phase": "phase2", "success_check": "pytest qa_integration/tests/test_select.py::test_no_relevant_change_runs_nothing -q", "title": "Handle the empty affected set: short-circuit to \"no relevant change\", exit 0, no full-run fallback"}
  priority: 1
  max_retries: 2

- [ ] task_id: T2.3
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/dependency_health_gate.py,qa_integration/tests/test_gate_dependency.py", "phase": "phase2", "success_check": "pytest qa_integration/tests/test_gate_dependency.py -q", "title": "Implement dependency_health_gate: probe all declared deps before trusting results; a down or timed-out dep fails loud and names the dependency"}
  priority: 1
  max_retries: 2

- [ ] task_id: T2.4
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/integration_coverage_gate.py,qa_integration/tests/test_gate_coverage.py", "phase": "phase2", "success_check": "pytest qa_integration/tests/test_gate_coverage.py -q", "title": "Implement integration_coverage_gate: per-boundary threshold block + zero-coverage-on-new-boundary hard block"}
  priority: 1
  max_retries: 2

- [ ] task_id: T2.5
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/run_changed_integration_tests.py,qa_integration/tests/test_select.py", "phase": "phase2", "success_check": "pytest qa_integration/tests/test_select.py::test_compose_change_full_fallback -q", "title": "Implement compose/shared-fixture fallback: force the full integration run when docker-compose or shared fixtures change"}
  priority: 1
  max_retries: 2

- [ ] task_id: T3.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/agent/envfix_finder.py,qa_integration/tests/test_envfix.py", "phase": "phase3", "success_check": "pytest qa_integration/tests/test_envfix.py::test_finds_issue_target -q", "title": "Implement env-issue finder: given a failed dependency-health probe, identify the fix target (compose service, env var, config key) with file+line"}
  priority: 2
  max_retries: 2

- [ ] task_id: T3.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "low", "files": "qa_integration/agent/envfix_generator.py,qa_integration/tests/test_envfix.py", "phase": "phase3", "success_check": "pytest qa_integration/tests/test_envfix.py::test_drafts_candidate_fix -q", "title": "Implement fix generator: draft the candidate fix content (compose patch / env var / config diff) from the identified issue"}
  priority: 2
  max_retries: 2

- [ ] task_id: T3.3
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "low", "files": "qa_integration/agent/envfix_pr.py,qa_integration/tests/test_envfix.py", "phase": "phase3", "success_check": "pytest qa_integration/tests/test_envfix.py::test_delivers_proposal_never_auto_applies -q", "title": "Implement proposal emitter: deliver the candidate fix as a PR/patch; hold no apply credential to shared or production environments"}
  priority: 2
  max_retries: 2

- [ ] task_id: T4.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/isolation_manager.py,qa_integration/tests/test_isolation.py", "phase": "phase4", "success_check": "pytest qa_integration/tests/test_isolation.py -q", "title": "Implement isolation manager: roll back or recreate dependency state after each test, detect cross-test bleed via a pre-test fingerprint and block the run, force serial execution when a dependency cannot be reset"}
  priority: 3
  max_retries: 2

- [ ] task_id: T4.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/slow_flaky_triage.py,qa_integration/tests/test_triage.py", "phase": "phase4", "success_check": "pytest qa_integration/tests/test_triage.py -q", "title": "Implement slow/flaky triage: quarantine over-time-budget tests without blocking, classify flaky only on confirmed same-commit pass+fail, track flaky separately so a consistent real failure stays red"}
  priority: 3
  max_retries: 2

- [ ] task_id: T5.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/report.py,qa_integration/tests/test_report.py", "phase": "phase5", "success_check": "pytest qa_integration/tests/test_report.py::test_emits_junit_and_allure -q", "title": "Implement reporter: serialise a run to JUnit XML + Allure result dir, both well-formed"}
  priority: 4
  max_retries: 2

- [ ] task_id: T5.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tools/report.py,qa_integration/tests/test_report.py", "phase": "phase5", "success_check": "pytest qa_integration/tests/test_report.py::test_report_has_required_metrics -q", "title": "Populate metrics block: pass rate, per-boundary coverage, dependency-health status, runtime, flaky rate"}
  priority: 4
  max_retries: 2

- [ ] task_id: T6.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"files": "qa_integration/ci/pr_gate.py,qa_integration/tests/test_ci_gate.py", "phase": "phase6", "success_check": "pytest qa_integration/tests/test_ci_gate.py::test_pr_gate_blocks_on_fail -q", "title": "Wire the PR gate: aggregate tool results into a single blocking (non-zero) CI status"}
  priority: 5
  max_retries: 2

- [ ] task_id: T6.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/ci/budget.py,qa_integration/tests/test_ci_gate.py", "phase": "phase6", "success_check": "pytest qa_integration/tests/test_ci_gate.py::test_budget_breach_is_first_class -q", "title": "Implement the wall-clock budget guard: emit a first-class budget_breach on overrun"}
  priority: 5
  max_retries: 2

- [ ] task_id: T6.3
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"files": "qa_integration/ci/hitl_manifest.py,qa_integration/hermes/workflow.yaml,qa_integration/tests/test_hitl.py", "phase": "phase6", "success_check": "pytest qa_integration/tests/test_hitl.py::test_hitl_manifest_enumerates_points -q", "title": "Emit hitl_manifest.json and register the microservice as a Hermes workflow"}
  priority: 5
  max_retries: 2

- [ ] task_id: T7.1
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"files": "qa_integration/tests/test_e2e.py", "phase": "phase7", "success_check": "pytest qa_integration/tests/test_e2e.py -q", "title": "Add an e2e run against a fixture target stack (docker-compose up): change → select → health → gate → report"}
  priority: 6
  max_retries: 2

- [ ] task_id: T7.2
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"files": "qa_integration/tests/test_hitl.py", "phase": "phase7", "success_check": "pytest qa_integration/tests/test_hitl.py::test_env_fix_requires_approval -q", "title": "Add HITL enforcement test: an environment fix cannot be applied without a recorded approval"}
  priority: 6
  max_retries: 2

- [ ] task_id: T7.3
  workflow: ATHENA_TASK
  dispatcher: script
  inputs: {"autonomy": "high", "files": "qa_integration/tests/", "phase": "phase7", "success_check": "pytest qa_integration -q", "title": "Full suite gate: run the entire qa_integration test suite green"}
  priority: 6
  max_retries: 2

## Linked
- generated by Athena `compile` from front `integration-testing-qa-workflow-microservice`
- executor: `apps/hermes/workflows/PLAN_RUN.yaml` (existing)
