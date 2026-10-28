# Scenarios: TDD benchmark

### S4.8 - Model POSIX metadata without host symlinks
- **verifies:** C-4.8
- **pins:** 1597e8c2bdeeec4a
- **run_cmd:** `python -m pytest tests/test_tdd_workspace.py::test_contained_links_are_inert_on_host_and_file_modes_are_recorded -q`
- **Given** regular executable files, a contained file link and a directory link
- **When** source is exported on the host
- **Then** metadata preserves target and mode, no host symlinks exist and the reader returns link identity.

### S6.7 - Restore POSIX identities in the test workspace
- **verifies:** C-6.7
- **pins:** a77ec94e77d3c286
- **run_cmd:** `python -m pytest tests/test_tdd_filesystem.py::test_restoration_preserves_inode_types_targets_and_executable_mode tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary tests/test_tdd_workspace.py::test_contained_links_are_inert_on_host_and_file_modes_are_recorded -q`
- **Given** a portable filesystem snapshot and isolated runtime
- **When** restoration precedes test execution
- **Then** links and executable bits are restored, overlays cannot traverse links and the runtime permits temporary executable files.

### S8.1 - Freeze before independent review
- **verifies:** C-8.1
- **pins:** bc354a04064e40a3
- **run_cmd:** `python -m pytest tests/test_tdd_trust.py::test_frozen_candidate_needs_separate_review_and_native_audit_C_8_1 -q`
- **Given** a passing native proposal
- **When** the trust arm freezes it
- **Then** it awaits review and no prediction exists until a successful native audit.

### S8.2 - Separate review context and shared model budget
- **verifies:** C-8.2
- **pins:** 9fec16f0ec52182d
- **run_cmd:** `python -m pytest tests/test_tdd_trust.py::test_frozen_candidate_needs_separate_review_and_native_audit_C_8_2 -q`
- **Given** the frozen candidate and its public source
- **When** an independent reviewer is called
- **Then** the review is candidate-bound, uses its own context and consumes the original total budget.

### S8.3 - Run actual native trust with isolated roles
- **verifies:** C-8.3
- **pins:** 1b86b5dbc495acb2
- **run_cmd:** `python -m pytest tests/test_tdd_trust.py::test_frozen_candidate_needs_separate_review_and_native_audit_C_8_3 -q`
- **Given** reviewer-owned valid and activated violation variants
- **When** native audit executes
- **Then** activation and candidate tests never share their submitted test files and the native evidence is retained.

### S8.4 - Missing evidence remains incomplete
- **verifies:** C-8.4
- **pins:** 09a228720226f547
- **run_cmd:** `python -m pytest tests/test_tdd_trust.py::test_incomplete_scope_and_exhausted_shared_budget_never_publish tests/test_tdd_trust.py::test_changed_candidate_native_artifact_or_review_is_rejected tests/test_tdd_trust.py::test_review_cannot_omit_bound_specs_or_add_free_model_calls tests/test_tdd_trust.py::test_truncated_review_is_charged_and_never_publishes -q`
- **Given** incomplete scope, exhausted budget or changed artifacts
- **When** a candidate is audited
- **Then** no prediction is published and evidence remains incomplete.

### S8.5 - Reject vacuous and overspecific specs
- **verifies:** C-8.5
- **pins:** 8e1c6e0b443e90e7
- **run_cmd:** `python -m pytest tests/test_tdd_trust.py::test_real_native_policy_rejects_vacuous_and_overspecific_specs -q`
- **Given** an always-green spec or one tied to source spelling
- **When** the real native policy sees a violation or valid alternative
- **Then** it records a false accept or false reject and rejects the spec.

### S8.6 - Dry-run review and trust
- **verifies:** C-8.6
- **pins:** 264ea4006bb407f9
- **run_cmd:** `python -m pytest tests/test_tdd_trust.py::test_review_and_trust_cli_are_dry_by_default -q`
- **Given** a frozen candidate
- **When** review and trust commands omit execute
- **Then** no model calls, execution or output artifacts occur.

### S7.1 - Run the native contract fast lane
- **verifies:** C-7.1
- **pins:** 45096300c35689e9
- **run_cmd:** `python -m pytest tests/test_tdd_native.py::test_native_check_runs_contract_ledger_and_exports_only_tests_C_7_1 -q`
- **Given** an authored contract, executable spec and proposed implementation
- **When** the native arm checks them
- **Then** real Athena modules produce a pinned ledger and scoped check with source fingerprints.

### S7.2 - Keep the reference out of the evaluator patch
- **verifies:** C-7.2
- **pins:** 621cd26009e0db08
- **run_cmd:** `python -m pytest tests/test_tdd_native.py::test_native_check_runs_contract_ledger_and_exports_only_tests_C_7_2 -q`
- **Given** a public reference proposal and changed tests
- **When** the candidate patch is derived
- **Then** only tests are exported and original public source remains unchanged.

### S7.3 - Reject unsafe native execution
- **verifies:** C-7.3
- **pins:** 0c09f1a0ae83711f
- **run_cmd:** `python -m pytest tests/test_tdd_native.py::test_reference_and_native_commands_cannot_escape_public_inputs -q`
- **Given** an absent reference, unknown paths or arbitrary commands
- **When** the proposal is checked
- **Then** no unsafe execution occurs.

### S7.4 - Share execution budgets and keep unknown baselines incomplete
- **verifies:** C-7.4
- **pins:** bd518d03a027407f
- **run_cmd:** `python -m pytest tests/test_tdd_native.py::test_native_gate_keeps_failed_and_inconclusive_baselines_distinct tests/test_tdd_native.py::test_native_check_cannot_spend_an_extra_test_budget -q`
- **Given** failed assertions or a consumed per-arm budget
- **When** native baseline specs run
- **Then** FAIL differs from INCOMPLETE and no extra execution budget appears.

### S6.1 - Pin environment-only runtime identity
- **verifies:** C-6.1
- **pins:** 605e8201203f8b48
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_environment_runtime_is_pinned_and_bound_to_one_snapshot_C_6_1 -q`
- **Given** an inspected dependency image
- **When** a runtime is bound to a public snapshot
- **Then** task-image tags and changed instance identity are rejected.

### S6.2 - Keep candidate overlays and mounts narrow
- **verifies:** C-6.6
- **pins:** e64a506e7ea0b6f5
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_candidate_overlay_cannot_replace_implementation_or_runner_config tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary -q`
- **Given** test files, implementation files and runner configuration overlays
- **When** a test tool is prepared
- **Then** only test overlays are accepted, payload uses stdin and only public input and empty output are mounted.

### S6.3 - Preserve test outcome types
- **verifies:** C-6.3
- **pins:** b86d662fea49147e
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary -q`
- **Given** passing, assertion, import, skipped and missing JUnit results
- **When** execution diagnostics are emitted
- **Then** infrastructure failures never become assertion witnesses.

### S6.4 - Remove the timed-out container
- **verifies:** C-6.4
- **pins:** 35bb1d0a1d69899c
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_timeout_cleans_only_its_container_and_never_counts_as_assertion -q`
- **Given** a test tool that exceeds its execution budget
- **When** the Docker client times out
- **Then** only the invocation's container is removed and the result remains TIMEOUT.

### S6.5 - Enforce generator test budgets
- **verifies:** C-6.5
- **pins:** 5dd3a7808dc9cdbc
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_generator_run_action_obeys_separate_test_budget_C_6_5 -q`
- **Given** one allowed test run and two run requests
- **When** generation continues
- **Then** only one execution occurs, runtime identity is retained and host commands never enter model context.

### S5.1 - Public direct-generation transcript
- **verifies:** C-5.1
- **pins:** c43e24c06376e50f
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_generator_reads_public_source_and_preserves_candidate_provenance tests/test_tdd_generator.py::test_changed_public_input_cannot_be_used_for_a_candidate -q`
- **Given** a public issue and a scripted reader
- **When** list, read and finish actions are requested
- **Then** the transcript contains only public source and the candidate remains unevaluated.

### S5.2 - Private paths and fixed turn budget
- **verifies:** C-5.2
- **pins:** 8709e38eb844ebf7
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_private_paths_are_denied_and_budget_has_no_hidden_retry -q`
- **Given** a private file outside the workspace
- **When** a model requests it repeatedly
- **Then** no private content reaches the transcript and no extra calls occur.

### S5.3 - Preserve incomplete generation evidence
- **verifies:** C-5.3
- **pins:** 8ed38a69536024f2
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_truncated_output_transport_error_and_context_exhaustion_are_incomplete -q`
- **Given** truncation, an exception containing credentials or an exhausted context budget
- **When** generation stops
- **Then** an incomplete receipt remains, no candidate exists and exception secrets are omitted.

### S5.4 - Explicit HTTP transport and usage
- **verifies:** C-5.4
- **pins:** 4277c0648c5ba634
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_http_transport_uses_explicit_config_and_records_usage_without_exposing_key -q`
- **Given** explicit model configuration and an environment credential
- **When** the HTTP transport sends a request
- **Then** request limits and authorization are correct and response evidence omits the key.

### S5.5 - Dry-run generation by default
- **verifies:** C-5.5
- **pins:** 32abc166ceab954d
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_generation_cli_defaults_to_no_model_calls -q`
- **Given** a valid public workspace
- **When** the generation CLI is called without execute
- **Then** it makes no model calls and creates no output directory.

### S4.4 - Constrain the code tool sandbox
- **verifies:** C-4.4
- **pins:** 00f0f62145eec6d7
- **run_cmd:** `python -m pytest tests/test_tdd_workspace.py::test_sandbox_exposes_only_verified_public_workspace -q`
- **Given** a verified workspace and empty output directory
- **When** a code tool sandbox is prepared
- **Then** only two mounts exist, input is read-only, network is disabled and changed source is rejected.

### S4.5 - Bind the exported issue text
- **verifies:** C-4.5
- **pins:** c2c4b439b6481f5e
- **run_cmd:** `python -m pytest tests/test_tdd_workspace.py::test_issue_tampering_invalidates_workspace -q`
- **Given** an exported issue whose text was replaced
- **When** the workspace is verified
- **Then** the issue fingerprint mismatch rejects it.

### S4.1 - Export base files and public issue
- **verifies:** C-4.1
- **pins:** 2e8fd5ee92dddbd0
- **run_cmd:** `python -m pytest tests/test_tdd_workspace.py::test_workspace_contains_only_public_issue_and_base_files -q`
- **Given** a public issue and a base revision archive
- **When** a new workspace is exported
- **Then** source files and fingerprints exist without repository history, and overwrite is refused.

### S4.2 - Reject sealed or out-of-cohort input
- **verifies:** C-4.2
- **pins:** 32a2b2d54c0bfb4c
- **run_cmd:** `python -m pytest tests/test_tdd_workspace.py::test_sealed_or_out_of_cohort_inputs_never_reach_network -q`
- **Given** private benchmark fields or an unknown instance
- **When** workspace export is attempted
- **Then** validation rejects input before network access.

### S4.3 - Reject unsafe archives atomically
- **verifies:** C-4.7
- **pins:** a17c466bb58398f4
- **run_cmd:** `python -m pytest tests/test_tdd_workspace.py::test_unsafe_snapshot_never_leaves_partial_workspace -q`
- **Given** traversal, history, links, aliases, duplicate paths or multiple archive roots
- **When** the exporter reads the source archive
- **Then** no partial workspace or outside file remains.

### S3.1 - Validate actual model submissions
- **verifies:** C-3.1
- **pins:** 2b917cabeee2fa6f
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_evaluation_predictions_are_validated_and_mounted -q`
- **Given** valid, duplicate, out-of-cohort and invalid submission files
- **When** an evaluation command is prepared
- **Then** valid predictions use the mounted path and invalid submissions are rejected.

### S3.2 - Exercise the evaluation CLI
- **verifies:** C-3.2
- **pins:** 64e04778e7ca3882
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_evaluation_cli_preserves_selection_and_denominators -q`
- **Given** thirty frozen evaluation instances and one returned report
- **When** the CLI prepares execution and emits a report
- **Then** it selects thirty evaluation instances and retains twenty-nine missing reports.

### S1.1 - test only tdd members are admitted
- **verifies:** C-1.1
- **pins:** 4aa50992df38ca72
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_only_tdd_members_are_admitted -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S1.2 - test generator inputs never contain solutions
- **verifies:** C-1.2
- **pins:** 94d9163f99e537d0
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_generator_inputs_never_contain_solutions -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S1.3 - test selection is frozen distinct and disjoint
- **verifies:** C-1.3
- **pins:** d847b3b65dec24f4
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_selection_is_frozen_distinct_and_disjoint -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S1.4 - test missing inputs never fall back
- **verifies:** C-1.4
- **pins:** f2e700e5eae705ac
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_missing_inputs_never_fall_back -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S1.5 - test source artifacts are fingerprinted
- **verifies:** C-1.5
- **pins:** 8aae903ad9938626
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_source_artifacts_are_fingerprinted -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S2.1 - test harness requires explicit git authorization
- **verifies:** C-2.1
- **pins:** cd005a41fbdd91c2
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_harness_requires_explicit_git_authorization -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S2.2 - test errors skips and missing reports are incomplete
- **verifies:** C-2.2
- **pins:** b41dbd032e81420d
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_errors_skips_and_missing_reports_are_incomplete -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S2.3 - test fail before requires same test to pass after
- **verifies:** C-2.3
- **pins:** cbc5ef117e45d019
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_fail_before_requires_same_test_to_pass_after -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S2.4 - test summary keeps all denominators
- **verifies:** C-2.4
- **pins:** 40615418ca1964f9
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_summary_keeps_all_denominators -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.

### S2.5 - test gold runs are always calibration
- **verifies:** C-2.5
- **pins:** d49d8027ecb5382e
- **run_cmd:** `python -m pytest tests/test_tdd_benchmark.py::test_gold_runs_are_always_calibration -q`
- **Given** declared benchmark inputs
- **When** the boundary is exercised
- **Then** only reproducible, blind, executed evidence is credited.


### S6.8 - Require selected source origin
- **verifies:** C-6.8
- **pins:** 9aef59c65f9bd10a
- **run_cmd:** `python -m pytest tests/test_tdd_filesystem.py::test_source_layout_resolution_and_origin_boundary tests/test_tdd_execution.py::test_source_origin_error_overrides_successful_junit -q`
- **Given** an inspected public runtime
- **When** execution evidence is collected
- **Then** only the declared source and runtime are credited.

### S6.9 - Expose inspected Python version
- **verifies:** C-6.9
- **pins:** f46a51dd4ae00612
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_generator_run_action_obeys_separate_test_budget_C_6_9 -q`
- **Given** an inspected public runtime
- **When** execution evidence is collected
- **Then** only the declared source and runtime are credited.

### S5.6 - Bound predictions to applicable test patches
- **verifies:** C-5.6
- **pins:** 2df96cf5a0231f3c
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_final_patch_rejects_implementation_metadata_and_stale_hunks_C_5_6 tests/test_tdd_generator.py::test_existing_test_patch_checks_context_and_preserves_untouched_lines -q`
- **Given** a verified public source and model final patches
- **When** finalization processes test changes, implementation edits and stale hunks
- **Then** only applicable test changes are published, and the public source remains unchanged.

### S6.10 - Admit only inspected runtime kinds
- **verifies:** C-6.10
- **pins:** e5ac6f5fcd8a9281
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_environment_runtime_is_pinned_and_bound_to_one_snapshot_C_6_10 tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 -q`
- **Given** upstream and public-installed runtime candidates
- **When** identity, snapshot binding and inspection are checked
- **Then** only a matching completely inspected runtime is admitted.

### S6.11 - Bind public installed sources and complete inspection
- **verifies:** C-6.11
- **pins:** 11010151ca6d2e9b
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 -q`
- **Given** upstream and public-installed runtime candidates
- **When** identity, snapshot binding and inspection are checked
- **Then** only a matching completely inspected runtime is admitted.

### S6.12 - Restore only fingerprinted public build outputs
- **verifies:** C-6.12
- **pins:** 0bfb30f9839c9067
- **run_cmd:** `python -m pytest tests/test_tdd_filesystem.py::test_public_build_artifacts_restore_exact_bytes_without_replacing_source tests/test_tdd_filesystem.py::test_build_artifacts_reject_public_paths_link_traversal_and_forged_manifest tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 -q`
- **Given** frozen public source and separately inventoried installation outputs
- **When** runtime metadata or restoration is checked
- **Then** exact additional outputs are copied while public source, path boundaries and inventory fingerprints are enforced.

### S6.13 - Use explicit UTF-8 runtime locale
- **verifies:** C-6.13
- **pins:** a14796abcec4f3bf
- **run_cmd:** `python -m pytest tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_13 tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary -q`
- **Given** runtime inspection and offline test containers
- **When** public source is processed
- **Then** locale flags are explicit and an inspected ASCII filesystem is rejected.

### S6.14 - Stage exact public source inside installed runtime
- **verifies:** C-6.14
- **pins:** d9f41626f087b522
- **run_cmd:** `python -m pytest tests/test_tdd_filesystem.py::test_installed_source_copy_hashes_only_declared_public_files tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary -q`
- **Given** declared public files, extra image files and a model-selected source mode
- **When** source is staged and an execution request is built
- **Then** only matching declared bytes are copied and the bound runtime controls source mode.

### S5.7 - Export explicit Git creation metadata
- **verifies:** C-5.7
- **pins:** 175ee6bb5da1377b
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_final_patch_rejects_implementation_metadata_and_stale_hunks_C_5_7 tests/test_tdd_generator.py::test_existing_test_patch_checks_context_and_preserves_untouched_lines tests/test_tdd_generator.py::test_generator_reads_public_source_and_preserves_candidate_provenance -q`
- **Given** added-file, legacy missing-mode and existing-file final patches
- **When** the generator canonicalizes and publishes predictions
- **Then** new files receive Git creation metadata and existing-file edits do not.

### S8.7 - Review incident regression
- **verifies:** C-8.7
- **pins:** 4d6e76b4ada3aa40
- **run_cmd:** `python -m pytest tests/test_tdd_review_payload.py::test_review_uses_lossless_payload_before_original_context_check tests/test_tdd_review_payload.py -q`
- **Given** bounded public review inputs and recorded input failures
- **When** review representation or audit validation is applied
- **Then** lossless inputs, budgets and execution guards remain honest.

### S8.8 - Review incident regression
- **verifies:** C-8.8
- **pins:** 3737b91539a9cb69
- **run_cmd:** `python -m pytest tests/test_tdd_review_diagnostics.py::test_invalid_review_preserves_budget_and_diagnostic_without_execution -q`
- **Given** bounded public review inputs and recorded input failures
- **When** review representation or audit validation is applied
- **Then** lossless inputs, budgets and execution guards remain honest.

### S8.9 - Review incident regression
- **verifies:** C-8.9
- **pins:** a2deab6f15935993
- **run_cmd:** `python -m pytest tests/test_tdd_review_diagnostics.py::test_unsupported_options_have_actionable_errors tests/test_tdd_review_diagnostics.py::test_supported_command_selection_is_unchanged tests/test_tdd_review_diagnostics.py::test_valid_review_still_requires_real_native_challenges -q`
- **Given** bounded public review inputs and recorded input failures
- **When** review representation or audit validation is applied
- **Then** lossless inputs, budgets and execution guards remain honest.

### S5.8 - Disclose limits without granting extra execution
- **verifies:** C-5.8
- **pins:** ff2cac3739b4d452
- **run_cmd:** `python -m pytest tests/test_tdd_generator.py::test_model_sees_remaining_budget_without_receiving_extra_calls tests/test_tdd_generator.py::test_generator_reads_public_source_and_preserves_candidate_provenance tests/test_tdd_generation_budget.py -q`
- **Given** bounded generation and a reserved independent review
- **When** the model reads code or consumes a shared test run
- **Then** the transcript exposes accurate remaining limits without extra calls, test runs or publication.

### S8.11 - Disclose review costs before execution
- **verifies:** C-8.11
- **pins:** 73b49c5c3bbafda6
- **run_cmd:** `python -m pytest tests/test_tdd_review_budget.py::test_review_receives_shared_budget_and_bound_command_costs tests/test_tdd_review_budget.py -q`
- **Given** one or several commands bound to a frozen clause
- **When** independent review is requested
- **Then** accurate remaining limits and execution estimates reach the reviewer and transcript without extra budget.

### S8.10 - Deliver contrastive policy without changing execution decisions
- **verifies:** C-8.10
- **pins:** 7cad1f55a279fa54
- **run_cmd:** `python -m pytest tests/test_tdd_contrastive_review.py::test_contrastive_policy_reaches_reviewer_without_changing_native_outcomes tests/test_tdd_contrastive_review.py -q`
- **Given** separately reviewed valid and overspecific scripted candidates
- **When** the reviewer receives public context and contrastive instructions
- **Then** native execution still accepts the valid control and rejects the overspecific one within the same budget.

### S5.9 - Preserve existing named tests
- **verifies:** C-5.9
- **pins:** 13404406c499fd15
- **run_cmd:** `python -m pytest tests/test_tdd_preservation.py::test_changed_removed_and_shadowed_named_tests_are_rejected tests/test_tdd_preservation.py -q`
- **Given** an existing test file and a proposed overlay or patch
- **When** old tests are removed, changed, shadowed or retained with additive tests
- **Then** native, export and tool paths refuse destructive definitions before execution while allowing additions.
