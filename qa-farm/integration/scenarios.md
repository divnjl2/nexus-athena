# Scenarios: Integration-Testing QA Workflow-Microservice

> `/athena.scenarios` output. One executable Given-When-Then scenario per EARS acceptance
> criterion in `spec.md`. Stable IDs `S<requirement#>.<index>` map 1:1 to the EARS list.
> Prose Given/When/Then (NO Gherkin/Cucumber). Each scenario carries a `run_cmd` — a native
> `pytest` invocation that proves it. `verifies` back-links the spec requirement (`R<n>.<m>`).

---

## R1 — Change-scoped integration selection

### S1.1 — A boundary change runs only the covering integration tests
- **verifies:** R1.1
- **run_cmd:** `pytest qa_integration/tests/test_select.py::test_selects_boundary_scoped_only -q`
- **Given** a target repo with boundary A (service_a<->postgres) and boundary B (service_b<->redis)
- **When** only boundary A changes and the microservice selects tests
- **Then** the tests covering boundary A are scheduled and the tests covering boundary B are
  not.

### S1.2 — A change with no boundary under test runs nothing
- **verifies:** R1.2
- **run_cmd:** `pytest qa_integration/tests/test_select.py::test_no_relevant_change_runs_nothing -q`
- **Given** a commit that touches only documentation and unrelated files
- **When** the microservice computes the affected boundary set
- **Then** zero integration tests are scheduled and the run reports "no relevant change"
  without failing.

### S1.3 — A docker-compose change falls back to the full run
- **verifies:** R1.3
- **run_cmd:** `pytest qa_integration/tests/test_select.py::test_compose_change_full_fallback -q`
- **Given** a change that edits `docker-compose.yml` or shared integration test configuration
- **When** the microservice computes the affected boundary set
- **Then** the full integration suite is scheduled rather than an under-selected subset.

---

## R2 — Dependency-health gate

### S2.1 — Every declared dependency is probed before the run is trusted
- **verifies:** R2.1
- **run_cmd:** `pytest qa_integration/tests/test_gate_dependency.py::test_all_deps_probed_before_run -q`
- **Given** a run declaring three dependencies (postgres, redis, service_b)
- **When** the dependency-health gate starts the run
- **Then** all three dependencies are probed before any integration test executes.

### S2.2 — A down dependency fails the gate loudly, naming it
- **verifies:** R2.2
- **run_cmd:** `pytest qa_integration/tests/test_gate_dependency.py::test_down_dependency_fails_loud -q`
- **Given** a run where the `redis` dependency is unreachable
- **When** the dependency-health gate evaluates the run
- **Then** the gate result is FAIL, `redis` is named as the failing dependency, and no test
  depending on it is silently skipped.

### S2.3 — A health-probe timeout counts as failure, not a skip
- **verifies:** R2.3
- **run_cmd:** `pytest qa_integration/tests/test_gate_dependency.py::test_health_probe_timeout_is_failure -q`
- **Given** a dependency whose health probe does not respond within the configured timeout
- **When** the dependency-health gate evaluates the probe result
- **Then** the timeout is recorded as a failure of that dependency, not as a skipped check.

---

## R3 — Integration coverage gate

### S3.1 — Per-boundary coverage below threshold blocks
- **verifies:** R3.1
- **run_cmd:** `pytest qa_integration/tests/test_gate_coverage.py::test_below_boundary_threshold_blocks -q`
- **Given** a changed boundary whose integration coverage is 55% against a configured
  threshold of 75%
- **When** the integration coverage gate evaluates the boundary
- **Then** the gate result is FAIL with the failing boundary named.

### S3.2 — A new boundary with zero coverage is a hard block
- **verifies:** R3.2
- **run_cmd:** `pytest qa_integration/tests/test_gate_coverage.py::test_zero_coverage_new_boundary_blocks -q`
- **Given** a newly introduced service boundary with no integration test at all
- **When** the integration coverage gate evaluates the boundary
- **Then** the gate result is FAIL, treating 0% as a hard block rather than "no data → pass".

---

## R4 — Test isolation

### S4.1 — Dependency state is rolled back or recreated after each test
- **verifies:** R4.1
- **run_cmd:** `pytest qa_integration/tests/test_isolation.py::test_rollback_or_recreate_between_tests -q`
- **Given** an integration test that wrote rows to the database
- **When** the test completes
- **Then** the isolation manager rolls back the transaction or recreates the database
  fixture before the next test starts.

### S4.2 — Cross-test data bleed is detected and blocks the run
- **verifies:** R4.2
- **run_cmd:** `pytest qa_integration/tests/test_isolation.py::test_cross_test_bleed_detected_blocks -q`
- **Given** a test whose pre-test state fingerprint does not match the expected clean state
- **When** the isolation manager checks the fingerprint before the test runs
- **Then** the run is blocked and the colliding tests are reported by name.

### S4.3 — An unresettable dependency forces serial execution
- **verifies:** R4.3
- **run_cmd:** `pytest qa_integration/tests/test_isolation.py::test_unresettable_dependency_forces_serial -q`
- **Given** a boundary whose dependency (a shared external sandbox) cannot be reset between
  tests
- **When** the isolation manager schedules tests for that boundary
- **Then** it forces serial execution for that boundary instead of allowing masked parallel
  bleed.

---

## R5 — Slow / flaky integration triage

### S5.1 — An over-budget test is quarantined, not blocking
- **verifies:** R5.1
- **run_cmd:** `pytest qa_integration/tests/test_triage.py::test_slow_test_quarantined_not_blocking -q`
- **Given** an integration test that exceeds its configured per-test time budget
- **When** the slow/flaky triage evaluates the run
- **Then** the test is quarantined as slow and the rest of the run is not blocked by it.

### S5.2 — Pass-and-fail on the same commit is classified flaky
- **verifies:** R5.2
- **run_cmd:** `pytest qa_integration/tests/test_triage.py::test_same_commit_pass_fail_is_flaky -q`
- **Given** an integration test that passes and fails across reruns on one unchanged commit
- **When** the flaky detector evaluates the reruns
- **Then** the test is classified flaky.

### S5.3 — A consistent failure stays red and is never masked
- **verifies:** R5.3
- **run_cmd:** `pytest qa_integration/tests/test_triage.py::test_consistent_failure_stays_red -q`
- **Given** a build with one flaky test and one consistently failing test
- **When** the microservice reports status after reruns
- **Then** the flaky test is recorded in a separate channel and the consistently failing
  test still fails the build.

---

## R6 — Reporting & metrics

### S6.1 — A completed run emits a structured JUnit + Allure report
- **verifies:** R6.1
- **run_cmd:** `pytest qa_integration/tests/test_report.py::test_emits_junit_and_allure -q`
- **Given** a completed integration run
- **When** the reporter serialises results
- **Then** a JUnit XML file and an Allure result directory are produced and are
  well-formed.

### S6.2 — The report contains the required metric fields
- **verifies:** R6.2
- **run_cmd:** `pytest qa_integration/tests/test_report.py::test_report_has_required_metrics -q`
- **Given** a serialised run report
- **When** its metrics block is read
- **Then** it contains pass rate, per-boundary coverage, dependency-health status, runtime,
  and flaky rate.

---

## R7 — CI gate integration

### S7.1 — On a pull request the microservice runs as a blocking gate
- **verifies:** R7.1
- **run_cmd:** `pytest qa_integration/tests/test_ci_gate.py::test_pr_gate_blocks_on_fail -q`
- **Given** a pull-request invocation whose gate result is FAIL
- **When** the CI integration reports status
- **Then** it returns a blocking (non-zero) status that prevents merge.

### S7.2 — The integration run honours the time budget
- **verifies:** R7.2
- **run_cmd:** `pytest qa_integration/tests/test_ci_gate.py::test_budget_breach_is_first_class -q`
- **Given** an integration run configured with a 10-minute budget that is exceeded
- **When** the run reaches the budget
- **Then** it reports a budget breach as a first-class signal rather than a silent timeout.

---

## R8 — Human-in-the-loop & safety

### S8.1 — An environment fix is delivered as a proposal, never auto-applied
- **verifies:** R8.1
- **run_cmd:** `pytest qa_integration/tests/test_envfix.py::test_delivers_proposal_never_auto_applies -q`
- **Given** a candidate environment/dependency fix drafted from a health-gate failure
- **When** the microservice delivers the fix
- **Then** it opens a pull request or patch and performs no apply action against any shared
  or production environment.

### S8.2 — Applying an environment fix requires a recorded approval
- **verifies:** R8.2
- **run_cmd:** `pytest qa_integration/tests/test_hitl.py::test_env_fix_requires_approval -q`
- **Given** an environment-fix proposal pending review
- **When** the microservice is asked to apply it without an approval record
- **Then** the action is refused and the fix is not applied.

### S8.3 — HITL points are enumerated in a machine-readable manifest
- **verifies:** R8.3
- **run_cmd:** `pytest qa_integration/tests/test_hitl.py::test_hitl_manifest_enumerates_points -q`
- **Given** the running microservice
- **When** its HITL manifest is requested
- **Then** the manifest lists at least the approve-environment-fix and ambiguous-flaky
  classification points in a machine-readable form.
