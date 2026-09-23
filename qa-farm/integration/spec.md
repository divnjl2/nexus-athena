# Specification: Integration-Testing QA Workflow-Microservice

> Spec-Kit `/specify` output — the logical root of the provenance graph.
> Owns **what + why** only. No technology, framework, or implementation detail.
> EARS acceptance criteria map 1:1 to scenarios (`S<requirement#>.<index>`).
>
> Domain #2 of the 23-domain NEXUS QA farm. Source intent: the QA deep-research
> artifacts (23 domains × L0/L1/L2 maturity). This microservice offloads the
> **Integration Testing** domain so the human QA owns strategy and HITL, not routine.

## Summary

An autonomous workflow-microservice that takes over the routine of integration-level QA
on a target repository. Unlike domain #1 (unit), it runs tests against REAL dependencies —
real databases, real message brokers, real sibling services — spun up via docker-compose /
testcontainers. On every change it selects and runs only the integration tests covering the
changed service boundary, refuses to trust a run unless every declared dependency is
reachable and healthy, enforces a per-boundary integration coverage gate, guarantees each
test's state is rolled back or recreated so nothing bleeds into the next test, quarantines
slow and flaky tests without masking a real regression, and emits a structured report. It
runs as a blocking pull-request gate inside a fixed time budget and exposes its
human-in-the-loop points as a manifest so the orchestrator (and the human QA) always knows
where a person must decide. The end state is every EARS criterion in `scenarios.md` proven
by an executable `success_check`.

Value: the human QA stops hand-running integration suites against flaky shared
environments, hand-verifying that "green" actually means the database was up, and
hand-triaging slow/flaky noise from real infrastructure. Those become the microservice's
job; the human keeps the judgement calls (approve an environment fix, classify ambiguous
flaky, move the gate).

---

## User Scenarios (User Stories)

- **US-1 — Run only what changed.** As a QA engineer, when a developer pushes a change that
  touches a service boundary, I want only the integration tests covering that boundary to
  run, so feedback is fast and real-dependency infra is only paid for when it matters.
- **US-2 — Trust the dependency-health gate.** As a QA engineer, I want the microservice to
  refuse to trust results when a declared dependency is down or unreachable, so a green run
  always means the real dependencies were actually exercised, never silently skipped.
- **US-3 — Trust the integration coverage gate.** As a QA engineer, I want the microservice
  to block a merge whose per-boundary integration coverage drops below the bar — or whose
  boundary has no integration test at all — so integration gaps cannot silently ship.
- **US-4 — Never chase state the last test left behind.** As a QA engineer, I want every
  integration test's dependency state rolled back or recreated, and cross-test data bleed
  detected and blocked, so a failure always means something real, not stale fixtures.
- **US-5 — Tame slow and flaky integration noise without hiding it.** As a QA engineer, I
  want over-budget tests quarantined and flaky tests classified and tracked separately from
  real failures, so retries never mask a regression.
- **US-6 — See one honest report.** As a QA engineer, I want a single structured report
  with pass rate, per-boundary coverage, dependency-health status, runtime, and flaky rate,
  so I can reason about the run without scraping logs or shelling into containers.
- **US-7 — Get a proposed environment fix, not just a red dependency gate.** As a QA
  engineer, when a dependency-health failure has an environment-level cause, I want a
  candidate fix (compose / env-var / config patch) drafted for me to review, so recovering
  the environment is an approval instead of a manual hunt.
- **US-8 — Know where I must decide.** As a QA lead, I want the microservice to declare its
  HITL points, so the orchestrator routes exactly those to a human and automates the rest.

---

## Edge Cases

Each edge case is something a competent implementation MUST handle deliberately.

- **EC-1 — No relevant change.** A commit touches only docs / unrelated files. The service
  runs zero integration tests and reports "no relevant change" — it does not fall back to a
  full run, and it does not fail.
- **EC-2 — docker-compose / shared-fixture change.** A change to `docker-compose.yml`,
  shared test infra config, or a shared fixture invalidates impact analysis. The service
  MUST fall back to the full integration run rather than under-select.
- **EC-3 — New boundary with zero integration tests.** A changed service boundary has no
  covering integration test at all. The gate MUST treat 0% integration coverage on that
  boundary as a hard block, not as "no data → pass".
- **EC-4 — A declared dependency is down.** At run start, one declared dependency (DB,
  broker, sibling service) is unreachable or fails its health check. The service MUST FAIL
  loud, naming the dependency — it MUST NEVER silently skip the tests that depend on it.
- **EC-5 — Cross-test data bleed.** A test leaves state that a later test unknowingly
  depends on or is corrupted by. The service MUST detect the bleed and MUST block the run
  rather than silently passing on contaminated state.
- **EC-6 — Flaky masquerading as a real failure.** A test fails once, passes on rerun. The
  service classifies it as flaky ONLY on confirmed pass/fail on the *same* commit, and never
  by unlimited blind retries.
- **EC-7 — Time budget exceeded.** The integration run cannot finish in budget. The service
  reports a budget breach as a first-class signal, not a silent timeout.

---

## Acceptance Criteria (EARS)

Requirement keys `R<n>.<m>`; each is validated by scenario `S<n>.<m>` in `scenarios.md`.

### R1 — Change-scoped integration selection
- **R1.1** WHEN a commit changes a service boundary, the system SHALL run only the
  integration tests covering that boundary.
- **R1.2** WHEN a change touches no boundary under integration test, the system SHALL run no
  integration tests and SHALL report "no relevant change".
- **R1.3** WHEN docker-compose, shared fixtures, or integration test configuration change,
  the system SHALL fall back to the full integration run.

### R2 — Dependency-health gate
- **R2.1** WHEN a run starts, the system SHALL probe every declared dependency's health
  endpoint before executing any integration test.
- **R2.2** WHEN any declared dependency reports unhealthy or unreachable, the system SHALL
  fail the gate loudly, naming the dependency, and SHALL NOT silently skip the tests that
  depend on it.
- **R2.3** WHEN a dependency health probe times out, the system SHALL treat the timeout as
  a failure, not as a skip.

### R3 — Integration coverage gate
- **R3.1** WHEN per-boundary integration coverage is below the configured threshold, the
  system SHALL fail the gate and SHALL name the failing boundary.
- **R3.2** WHEN a service boundary has zero integration test coverage, the system SHALL
  treat it as a hard block, not as "no data → pass".

### R4 — Test isolation
- **R4.1** WHEN an integration test completes, the system SHALL roll back or recreate its
  dependency state so no data persists into the next test.
- **R4.2** WHEN cross-test data bleed is detected, the system SHALL block the run and SHALL
  report the colliding tests.
- **R4.3** WHEN a boundary's dependency cannot be reset between tests, the system SHALL
  force serial execution for that boundary rather than allowing masked parallel bleed.

### R5 — Slow / flaky integration triage
- **R5.1** WHEN an integration test exceeds its configured time budget, the system SHALL
  quarantine it as slow rather than blocking the whole run.
- **R5.2** WHEN a test both passes and fails on the same commit across reruns, the system
  SHALL classify it as flaky.
- **R5.3** WHEN a test fails consistently across reruns, the system SHALL keep the build
  red — retries SHALL NOT mask a real failure.

### R6 — Reporting & metrics
- **R6.1** WHEN a run completes, the system SHALL emit a structured, machine-readable report
  in JUnit and Allure form.
- **R6.2** The report SHALL include pass rate, per-boundary coverage, dependency-health
  status, runtime, and flaky rate.

### R7 — CI gate integration
- **R7.1** WHEN invoked on a pull request, the system SHALL run as a blocking gate.
- **R7.2** The system SHALL complete the integration run within the configured time budget
  (default 10 minutes) or SHALL report a budget breach.

### R8 — Human-in-the-loop & safety
- **R8.1** WHEN a candidate environment or dependency fix is ready, the system SHALL
  deliver it as a proposal (pull request or patch) and SHALL NOT apply it automatically to
  any shared or production environment.
- **R8.2** WHEN an environment-fix proposal is requested to be applied without a recorded
  human approval, the system SHALL refuse the action.
- **R8.3** The system SHALL enumerate its human-in-the-loop points in a machine-readable
  manifest for the orchestrator.

---

## Clarifications

- **Boundary** is configuration, not inference: a declared list of service/dependency pairs
  (e.g. `service_a<->postgres`, `service_a<->service_b`) in `boundaries.toml`. Selection and
  the coverage gate key off it.
- **Declared dependencies** are explicit: a `dependencies.toml` / docker-compose service
  list. The health gate probes exactly that list — nothing is inferred, so silence never
  becomes trust.
- **"Affected integration tests"** is defined by test-impact analysis over the changed files
  mapped to their boundary, plus that boundary's reverse-dependency closure; the fallback in
  R1.3 exists because that closure is unreliable when shared infra moves.
- **Environment-fix proposals** are always additive/advisory and always behind R8.1/R8.2 —
  there is no configuration path that auto-applies them to a shared or production
  environment.
