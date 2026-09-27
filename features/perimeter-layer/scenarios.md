# Scenarios: Athena Perimeter Layer (v3.18)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>` mirroring the
> clause number. `pins:` is written by `athena contract pin --write`.

---

## C-1 — findings become verdicts (lib/findings.py)

### S1.1 — findings from four tools are read into one shape
- **verifies:** C-1.1
- **pins:** c4f9e5f53a57b658
- **run_cmd:** `python -m pytest tests/test_perimeter_findings.py::test_findings_from_four_tools_are_read_into_one_shape -q`
- **Given** tests/test_perimeter_findings.py
- **When** the spec `test_findings_from_four_tools_are_read_into_one_shape` is executed
- **Then** Vale, Bandit, gitleaks and Semgrep JSON each yield findings with tool, path, line, severity in {info, warning, error}, rule and message; malformed text yields no findings and no exception.

### S1.2 — findings are judged against a clause's severity threshold
- **verifies:** C-1.2
- **pins:** 97558018cbbcf301
- **run_cmd:** `python -m pytest tests/test_perimeter_findings.py::test_findings_are_judged_against_a_severity_threshold -q`
- **Given** tests/test_perimeter_findings.py
- **When** the spec `test_findings_are_judged_against_a_severity_threshold` is executed
- **Then** a finding at or above the threshold makes the verdict red and the reason names the worst finding with file and line; findings below it leave the verdict green with their count.

### S1.3 — a missing tool leaves the clause unrun and named
- **verifies:** C-1.3
- **pins:** 3b236a01a7679a6a
- **run_cmd:** `python -m pytest tests/test_perimeter_findings.py::test_a_missing_tool_leaves_the_clause_unrun_and_named -q`
- **Given** tests/test_perimeter_findings.py
- **When** the spec `test_a_missing_tool_leaves_the_clause_unrun_and_named` is executed
- **Then** with a resolver that finds no binary the verdict is neither green nor red, its state is unrun and the reason names the tool and an install hint; with the binary found the oracle's command is rendered.

### S1.4 — the frame's documents pass the prose style at severity error
- **verifies:** C-1.4
- **pins:** 68e21b29f1e7e8bc
- **run_cmd:** `python -m pytest tests/test_perimeter_findings.py::test_the_frames_documents_pass_the_prose_style_at_severity_error -q`
- **Given** tests/test_perimeter_findings.py
- **When** the spec `test_the_frames_documents_pass_the_prose_style_at_severity_error` is executed
- **Then** Vale with `features/perimeter-layer/vale/.vale.ini` (which names C-1.4) reports no error-level finding on the feature READMEs and the research digests; when vale is missing the spec is skipped with the install hint, never green.

### S1.5 — a judge's score is advisory until calibrated
- **verifies:** C-1.5
- **pins:** 65a320d38ccc0953
- **run_cmd:** `python -m pytest tests/test_perimeter_findings.py::test_a_judges_score_is_advisory_until_calibrated -q`
- **Given** tests/test_perimeter_findings.py
- **When** the spec `test_a_judges_score_is_advisory_until_calibrated` is executed
- **Then** a judge record carries the score and the judge's provenance and is advisory; only an agreement measured on at least twenty samples at or above the named level makes it able to refuse.

## C-2 — the external world enters as fixtures (lib/stands.py)

### S2.1 — a changed cassette taints the verdict like a spec edit
- **verifies:** C-2.1
- **pins:** bf5f8e2165b3dc17
- **run_cmd:** `python -m pytest tests/test_perimeter_stands.py::test_a_changed_cassette_taints_the_verdict_like_a_spec_edit -q`
- **Given** tests/test_perimeter_stands.py
- **When** the spec `test_a_changed_cassette_taints_the_verdict_like_a_spec_edit` is executed
- **Then** a verdict whose changed files include a path under `cassettes/` has it in `spec_touched` and is not green, while a path merely containing the word is untouched.

### S2.2 — a stale cassette is reported with its age
- **verifies:** C-2.2
- **pins:** 115d28e0d3c06bd0
- **run_cmd:** `python -m pytest tests/test_perimeter_stands.py::test_a_stale_cassette_is_reported_with_its_age -q`
- **Given** tests/test_perimeter_stands.py
- **When** the spec `test_a_stale_cassette_is_reported_with_its_age` is executed
- **Then** given cassette paths with modification times and a freshness in days, the cassettes older than it are named with their age and the fresh ones are not; the report is advisory.

### S2.3 — an embedded postgres serves a spec and leaves nothing behind
- **verifies:** C-2.3
- **pins:** cb87719a06a94d27
- **run_cmd:** `python -m pytest tests/test_perimeter_stands.py::test_an_embedded_postgres_serves_a_spec_and_leaves_nothing_behind -q`
- **Given** tests/test_perimeter_stands.py
- **When** the spec `test_an_embedded_postgres_serves_a_spec_and_leaves_nothing_behind` is executed
- **Then** inside the stand a table is created and read back over the DSN on a loopback port; after the stand the data directory is gone and the port no longer accepts connections; without the package the spec is skipped with the install hint.

### S2.4 — a red verdict becomes a reproduction packet that asks for the test, not the fix
- **verifies:** C-2.4
- **pins:** 7c00de4ec3c447c4
- **run_cmd:** `python -m pytest tests/test_perimeter_stands.py::test_a_red_verdict_becomes_a_reproduction_packet_that_asks_for_the_test_not_the_fix -q`
- **Given** tests/test_perimeter_stands.py
- **When** the spec `test_a_red_verdict_becomes_a_reproduction_packet_that_asks_for_the_test_not_the_fix` is executed
- **Then** the packet carries the failing command, the tail and the changed files, asks first for a test that passes on the present behaviour and second for its inversion, and forbids editing the module under test.

### S2.5 — a reproduction is admitted only when it passes as written and fails inverted
- **verifies:** C-2.5
- **pins:** 100ee4d87af60c75
- **run_cmd:** `python -m pytest tests/test_perimeter_stands.py::test_a_reproduction_is_admitted_only_when_it_passes_as_written_and_fails_inverted -q`
- **Given** tests/test_perimeter_stands.py
- **When** the spec `test_a_reproduction_is_admitted_only_when_it_passes_as_written_and_fails_inverted` is executed
- **Then** exits (0, 1) admit; (0, 0), (1, 1) and (1, 0) refuse with a reason naming which half failed; both exits are in the record.

### S2.6 — athena repro dispatches the reproduction and prints the admission
- **verifies:** C-2.6
- **pins:** d43f878854af77c8
- **run_cmd:** `python -m pytest tests/test_perimeter_wiring.py::test_athena_repro_dispatches_the_reproduction_and_prints_the_admission -q`
- **Given** tests/test_perimeter_wiring.py
- **When** the spec `test_athena_repro_dispatches_the_reproduction_and_prints_the_admission` is executed
- **Then** with `--executor none` the command prints the packet it would send, naming the record's failing command and asking for the passing test before the inversion; with `--judge-exits 0,1` the admission line of C-2.5 is printed and the exit code follows it.

## C-3 — scan and policy are stages of the queue (lib/scan.py)

### S3.1 — the scan stage is planned from the changed files and refuses on a finding
- **verifies:** C-3.1
- **pins:** 396ba1370ba5fb6e
- **run_cmd:** `python -m pytest tests/test_perimeter_scan.py::test_the_scan_stage_is_planned_from_the_changed_files_and_refuses_on_a_finding -q`
- **Given** tests/test_perimeter_scan.py
- **When** the spec `test_the_scan_stage_is_planned_from_the_changed_files_and_refuses_on_a_finding` is executed
- **Then** Python files plan Bandit, any change plans gitleaks over the diff, a requirements file plans pip-audit, nothing else plans anything; with an injected runner returning findings the stage refuses at or above the threshold naming the finding, and passes below it.

### S3.2 — the policy input is rendered and conftest evaluates the rego policies
- **verifies:** C-3.2
- **pins:** e00afe38c42f2015
- **run_cmd:** `python -m pytest tests/test_perimeter_scan.py::test_the_policy_input_is_rendered_and_conftest_evaluates_the_rego_policies -q`
- **Given** tests/test_perimeter_scan.py
- **When** the spec `test_the_policy_input_is_rendered_and_conftest_evaluates_the_rego_policies` is executed
- **Then** the input JSON carries the record, the changed paths and the stages seen; conftest over `features/perimeter-layer/policy/` (which names C-3.2) passes a complete input and denies one missing provenance, one touching a sealed path and one without the mutation stage, each by its message; without conftest the spec is skipped with the install hint.

### S3.3 — the queue runs scan after check and policy before fast-forward
- **verifies:** C-3.3
- **pins:** 69c53436e4c409c2
- **run_cmd:** `python -m pytest tests/test_perimeter_scan.py::test_the_queue_runs_scan_after_check_and_policy_before_fast_forward -q`
- **Given** tests/test_perimeter_scan.py
- **When** the spec `test_the_queue_runs_scan_after_check_and_policy_before_fast_forward` is executed
- **Then** the refinery's STAGES read admit, rebase, check, scan, mutation, policy, fast-forward in that order, and `athena merge --help` names the flags that skip scan and policy explicitly.

### S3.4 — a model's review rides in the merge record and never refuses
- **verifies:** C-3.4
- **pins:** cb5aedcbd6dd9035
- **run_cmd:** `python -m pytest tests/test_perimeter_scan.py::test_a_models_review_rides_in_the_merge_record_and_never_refuses -q`
- **Given** tests/test_perimeter_scan.py
- **When** the spec `test_a_models_review_rides_in_the_merge_record_and_never_refuses` is executed
- **Then** attaching a review to a merge record keeps the record's ok unchanged, adds the review text and the reviewer's provenance under `review`, and marks it advisory.

## C-4 — the rungs are watched (lib/drift.py)

### S4.1 — a bench run appends one row per executor with the set's digest
- **verifies:** C-4.1
- **pins:** 998a951a48e81e6d
- **run_cmd:** `python -m pytest tests/test_perimeter_drift.py::test_a_bench_run_appends_one_row_per_executor_with_the_sets_digest -q`
- **Given** tests/test_perimeter_drift.py
- **When** the spec `test_a_bench_run_appends_one_row_per_executor_with_the_sets_digest` is executed
- **Then** from a bench table and provenance per executor the rows carry ts, executor, model id, runtime version, set digest, tasks, green and rate; two runs of the same set share the digest.

### S4.2 — a drop in the pass rate is found by a one-sided cusum and dated
- **verifies:** C-4.2
- **pins:** cf1b325bcbde6f51
- **run_cmd:** `python -m pytest tests/test_perimeter_drift.py::test_a_drop_in_the_pass_rate_is_found_by_a_one_sided_cusum_and_dated -q`
- **Given** tests/test_perimeter_drift.py
- **When** the spec `test_a_drop_in_the_pass_rate_is_found_by_a_one_sided_cusum_and_dated` is executed
- **Then** a flat series yields no drop; a series that falls from 0.8 to 0.4 yields a drop whose start index is at the fall; fewer points than the minimum yields no verdict.

### S4.3 — a drop emits the bd command that opens a bead once
- **verifies:** C-4.3
- **pins:** 439d559656f41f6b
- **run_cmd:** `python -m pytest tests/test_perimeter_drift.py::test_a_drop_emits_the_bd_command_that_opens_a_bead_once -q`
- **Given** tests/test_perimeter_drift.py
- **When** the spec `test_a_drop_emits_the_bd_command_that_opens_a_bead_once` is executed
- **Then** the command is `bd create` with a title naming the executor, model, runtime and the drop, and the same drop reported twice yields the command once.

### S4.4 — a change of the set is reported apart from a change of the rung
- **verifies:** C-4.4
- **pins:** f57b416f719b955e
- **run_cmd:** `python -m pytest tests/test_perimeter_drift.py::test_a_change_of_the_set_is_reported_apart_from_a_change_of_the_rung -q`
- **Given** tests/test_perimeter_drift.py
- **When** the spec `test_a_change_of_the_set_is_reported_apart_from_a_change_of_the_rung` is executed
- **Then** rows whose digest differs from the previous row are excluded from the CUSUM and named as a set change in the report.

### S4.5 — bench --series and athena drift print the drops with their commands
- **verifies:** C-4.5
- **pins:** 95888e63fe806396
- **run_cmd:** `python -m pytest tests/test_perimeter_wiring.py::test_bench_series_and_athena_drift_print_the_drops_with_their_commands -q`
- **Given** tests/test_perimeter_wiring.py
- **When** the spec `test_bench_series_and_athena_drift_print_the_drops_with_their_commands` is executed
- **Then** `athena drift` over a prepared series file prints one line per executor with the verdict and, for a drop, the bd command; `athena bench --help` names `--series`.

## C-5 — the substrate (lib/host.py)

### S5.1 — the host floors park a dispatch and name the resource
- **verifies:** C-5.1
- **pins:** e02f0e00311ad772
- **run_cmd:** `python -m pytest tests/test_perimeter_host.py::test_the_host_floors_park_a_dispatch_and_name_the_resource -q`
- **Given** tests/test_perimeter_host.py
- **When** the spec `test_the_host_floors_park_a_dispatch_and_name_the_resource` is executed
- **Then** with injected readers a host under the RAM floor or a GPU under the VRAM floor is parked with the resource and both numbers in the reason; above both floors it is admitted; a reader that fails leaves the resource unknown and parks, saying so.

### S5.2 — a lane with no state is woken through the router before it is parked
- **verifies:** C-5.2
- **pins:** 1836929d85ea7e94
- **run_cmd:** `python -m pytest tests/test_perimeter_host.py::test_a_lane_with_no_state_is_woken_through_the_router_before_it_is_parked -q`
- **Given** tests/test_perimeter_host.py
- **When** the spec `test_a_lane_with_no_state_is_woken_through_the_router_before_it_is_parked` is executed
- **Then** the wake request targets the router with the lane's model and a one-token body; a health that turns 200 within the timeout ends the wait as woken; one that never does ends as parked with the seconds waited.

### S5.3 — strangers on a gpu are named against its allow list and reported once
- **verifies:** C-5.3
- **pins:** 449d5f5968786fba
- **run_cmd:** `python -m pytest tests/test_perimeter_host.py::test_strangers_on_a_gpu_are_named_against_its_allow_list_and_reported_once -q`
- **Given** tests/test_perimeter_host.py
- **When** the spec `test_strangers_on_a_gpu_are_named_against_its_allow_list_and_reported_once` is executed
- **Then** processes whose executable path matches no allow pattern of that GPU are strangers; the bd command names the GPU, pid and executable; the same pid on the next read yields no second command.

### S5.4 — a heavy gate runs under the governor when present and says so
- **verifies:** C-5.4
- **pins:** 9a77eca56058efd7
- **run_cmd:** `python -m pytest tests/test_perimeter_host.py::test_a_heavy_gate_runs_under_the_governor_when_present_and_says_so -q`
- **Given** tests/test_perimeter_host.py
- **When** the spec `test_a_heavy_gate_runs_under_the_governor_when_present_and_says_so` is executed
- **Then** with the governor found the argv is prefixed by it with the commit ceiling and kill-on-close; without it the argv is unchanged and the note says ungoverned.

### S5.5 — the daemon applies the floors and the wake and the merge governs the mutation stage
- **verifies:** C-5.5
- **pins:** dc586cf079c2fd82
- **run_cmd:** `python -m pytest tests/test_perimeter_wiring.py::test_the_daemon_applies_the_floors_and_the_wake_and_the_merge_governs_the_mutation_stage -q`
- **Given** tests/test_perimeter_wiring.py
- **When** the spec `test_the_daemon_applies_the_floors_and_the_wake_and_the_merge_governs_the_mutation_stage` is executed
- **Then** `athena daemon --dry-run --host-floors ram=8G,vram=2G --host-json <file>` prints the park with the resource when the file is under a floor and the dry tick when above; `athena daemon -h` names `--wake` and `--gpu-allowlist`; `athena merge -h` names `--governor-gb`.

