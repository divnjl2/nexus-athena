# Plan: Athena Perimeter Layer

## Overview
Four of the nine limits of 2026-09-27 are wiring: the oracles, the stand-ins, the scanners and
the eval runners exist as open source, and none speaks the frame's language of clause, verdict
and stage. Pure functions per limit in their own module under `lib/` take text and injected
runners; the CLI wires the real tools. OSS wrapped, not rewritten: Vale, Bandit, gitleaks,
pip-audit, conftest (OPA), embedded-postgres, the AssertFlip recipe, ruptures.

## Out of Scope
- Running Vale, conftest or PostgreSQL inside the pure specs: those specs take recorded output or
  an injected runner; the three effectful specs (S1.4, S2.3, S3.2) run the real tool and skip
  with the install hint when it is absent.
- A UI oracle (Playwright) and PR-Agent as the reviewer: the shapes are here (C-1.1, C-3.4), the
  tools come when a component layer or a PR flow exists.
- The nightly schedule itself: a Task Scheduler entry on the host, registered by hand, windowless.

## Phase 1: Findings become verdicts
**Goal:** four tools' findings read into one shape and judged by a clause's threshold; a missing
tool is unrun; the frame's own documents pass a prose style; a judge is advisory until calibrated.
**Depends on:** none
### Tasks
- [ ] T1.1 Findings from four tools into one shape
  - success_check: `python -m pytest tests/test_perimeter_findings.py::test_findings_from_four_tools_are_read_into_one_shape -q`
  - files: `lib/findings.py`
  - verifies: S1.1
- [ ] T1.2 The threshold verdict and the missing tool
  - success_check: `python -m pytest tests/test_perimeter_findings.py::test_findings_are_judged_against_a_severity_threshold tests/test_perimeter_findings.py::test_a_missing_tool_leaves_the_clause_unrun_and_named -q`
  - files: `lib/findings.py`
  - verifies: S1.2, S1.3
- [ ] T1.3 The prose style and the frame's documents
  - success_check: `python -m pytest tests/test_perimeter_findings.py::test_the_frames_documents_pass_the_prose_style_at_severity_error -q`
  - files: `features/perimeter-layer/vale/.vale.ini, features/perimeter-layer/vale/styles/Athena/NoEmoji.yml, features/perimeter-layer/vale/styles/Athena/NoPlaceholder.yml, features/perimeter-layer/vale/styles/Athena/NoDoubleSpace.yml`
  - verifies: S1.4
- [ ] T1.4 The judge's record, advisory until calibrated
  - success_check: `python -m pytest tests/test_perimeter_findings.py::test_a_judges_score_is_advisory_until_calibrated -q`
  - files: `lib/findings.py`
  - verifies: S1.5

## Phase 2: The external world enters as fixtures
**Goal:** cassettes are spec artefacts with a freshness; a PostgreSQL stand from the embedded
binary; a red verdict becomes a reproduction packet admitted by the AssertFlip rule.
**Depends on:** none
### Tasks
- [ ] T2.1 Cassettes are spec artefacts, stale ones are named
  - success_check: `python -m pytest tests/test_perimeter_stands.py::test_a_changed_cassette_taints_the_verdict_like_a_spec_edit tests/test_perimeter_stands.py::test_a_stale_cassette_is_reported_with_its_age -q`
  - files: `lib/dispatch.py, lib/stands.py`
  - verifies: S2.1, S2.2
- [ ] T2.2 The embedded postgres stand
  - success_check: `python -m pytest tests/test_perimeter_stands.py::test_an_embedded_postgres_serves_a_spec_and_leaves_nothing_behind -q`
  - files: `lib/stands.py`
  - verifies: S2.3
- [ ] T2.3 The reproduction packet and its admission
  - success_check: `python -m pytest tests/test_perimeter_stands.py::test_a_red_verdict_becomes_a_reproduction_packet_that_asks_for_the_test_not_the_fix tests/test_perimeter_stands.py::test_a_reproduction_is_admitted_only_when_it_passes_as_written_and_fails_inverted -q`
  - files: `lib/stands.py`
  - verifies: S2.4, S2.5
- [ ] T2.4 athena repro
  - success_check: `python -m pytest tests/test_perimeter_wiring.py::test_athena_repro_dispatches_the_reproduction_and_prints_the_admission -q`
  - files: `athena.py`
  - verifies: S2.6

## Phase 3: Scan and policy are stages of the queue
**Goal:** the merge queue plans scanners from the changed files and refuses on a finding, evaluates
Rego policies over the merge record with conftest, and carries a model's review as advice.
**Depends on:** Phase 1 (T1.1, T1.2)
### Tasks
- [ ] T3.1 The scan stage: plan and verdict
  - success_check: `python -m pytest tests/test_perimeter_scan.py::test_the_scan_stage_is_planned_from_the_changed_files_and_refuses_on_a_finding -q`
  - files: `lib/scan.py`
  - verifies: S3.1
- [ ] T3.2 The policy input and the rego policies under conftest
  - success_check: `python -m pytest tests/test_perimeter_scan.py::test_the_policy_input_is_rendered_and_conftest_evaluates_the_rego_policies -q`
  - files: `lib/scan.py, features/perimeter-layer/policy/merge.rego`
  - verifies: S3.2
- [ ] T3.3 Scan and policy in the queue
  - success_check: `python -m pytest tests/test_perimeter_scan.py::test_the_queue_runs_scan_after_check_and_policy_before_fast_forward -q`
  - files: `lib/refinery.py, athena.py`
  - verifies: S3.3
- [ ] T3.4 A model's review, advisory
  - success_check: `python -m pytest tests/test_perimeter_scan.py::test_a_models_review_rides_in_the_merge_record_and_never_refuses -q`
  - files: `lib/scan.py`
  - verifies: S3.4

## Phase 4: The rungs are watched
**Goal:** a bench run appends a series row per executor; a one-sided CUSUM finds a drop and dates
it; a drop opens a bead once; a change of the task set is told apart from a change of the rung.
**Depends on:** none
### Tasks
- [ ] T4.1 Series rows and the set's digest
  - success_check: `python -m pytest tests/test_perimeter_drift.py::test_a_bench_run_appends_one_row_per_executor_with_the_sets_digest tests/test_perimeter_drift.py::test_a_change_of_the_set_is_reported_apart_from_a_change_of_the_rung -q`
  - files: `lib/drift.py`
  - verifies: S4.1, S4.4
- [ ] T4.2 The one-sided cusum and the bead command
  - success_check: `python -m pytest tests/test_perimeter_drift.py::test_a_drop_in_the_pass_rate_is_found_by_a_one_sided_cusum_and_dated tests/test_perimeter_drift.py::test_a_drop_emits_the_bd_command_that_opens_a_bead_once -q`
  - files: `lib/drift.py`
  - verifies: S4.2, S4.3
- [ ] T4.3 bench --series and athena drift
  - success_check: `python -m pytest tests/test_perimeter_wiring.py::test_bench_series_and_athena_drift_print_the_drops_with_their_commands -q`
  - files: `athena.py`
  - verifies: S4.5

### Manual Verification
- `athena check features/perimeter-layer/contract.md --front features/perimeter-layer/plan.md --run --text` green on every spec.
- One real merge through `athena merge` with the scan and policy stages on, refused once by a planted secret in the diff and once by a missing mutation stage.
- `athena bench --series` on the week's fixed set, then a model swap on one lane, then `athena drift` names the drop.
