# Plan: TDD benchmark

- [ ] T4.8 Preserve portable POSIX link and mode metadata for the frozen cohort
  - success_check: `python -m pytest tests/test_tdd_workspace.py tests/test_tdd_filesystem.py -q`
  - verifies: S4.3, S4.8, S6.7
  - files: `evals/tddbench/workspace.py, evals/tddbench/fsmodel.py, evals/tddbench/execution.py, evals/tddbench/native.py, evals/tddbench/generator.py, tests/test_tdd_workspace.py, tests/test_tdd_filesystem.py, tests/test_tdd_execution.py`

- [ ] T8.1 Freeze candidates and execute independent native trust review
  - success_check: `python -m pytest tests/test_tdd_trust.py -q`
  - verifies: S8.1, S8.2, S8.3, S8.4, S8.5, S8.6
  - files: `evals/tddbench/trust.py, evals/tddbench/generator.py, evals/tddbench/native.py, evals/tddbench/__main__.py, tests/test_tdd_trust.py`

- [ ] T7.1 Execute the native Athena contract arm over a public reference proposal
  - success_check: `python -m pytest tests/test_tdd_native.py -q`
  - verifies: S7.1, S7.2, S7.3, S7.4
  - files: `evals/tddbench/native.py, evals/tddbench/generator.py, evals/tddbench/execution.py, evals/tddbench/__main__.py, tests/test_tdd_native.py`

- [ ] T6.1 Execute candidate tests inside public dependency runtimes
  - success_check: `python -m pytest tests/test_tdd_execution.py -q`
  - verifies: S6.1, S6.2, S6.3, S6.4, S6.5
  - files: `evals/tddbench/execution.py, evals/tddbench/generator.py, evals/tddbench/__main__.py, tests/test_tdd_execution.py`

- [ ] T5.1 Implement auditable direct-agent generation
  - success_check: `python -m pytest tests/test_tdd_generator.py -q`
  - verifies: S5.1, S5.2, S5.3, S5.4, S5.5
  - files: `evals/tddbench/generator.py, evals/tddbench/__main__.py, tests/test_tdd_generator.py`

- [ ] T4.4 Prepare offline code-tool isolation
  - success_check: `python -m pytest tests/test_tdd_workspace.py::test_sandbox_exposes_only_verified_public_workspace -q`
  - verifies: S4.4
  - files: `evals/tddbench/workspace.py, evals/tddbench/__main__.py, tests/test_tdd_workspace.py`
- [ ] T4.5 Bind issue bytes to the source receipt
  - success_check: `python -m pytest tests/test_tdd_workspace.py::test_issue_tampering_invalidates_workspace -q`
  - verifies: S4.5
  - files: `evals/tddbench/workspace.py, tests/test_tdd_workspace.py`

- [ ] T4.1 Export public issue and base source archive
  - success_check: `python -m pytest tests/test_tdd_workspace.py::test_workspace_contains_only_public_issue_and_base_files -q`
  - verifies: S4.1
  - files: `evals/tddbench/workspace.py, evals/tddbench/__main__.py, tests/test_tdd_workspace.py`
- [ ] T4.2 Reject private inputs before source access
  - success_check: `python -m pytest tests/test_tdd_workspace.py::test_sealed_or_out_of_cohort_inputs_never_reach_network -q`
  - verifies: S4.2
  - files: `evals/tddbench/workspace.py, tests/test_tdd_workspace.py`
- [ ] T4.3 Reject archive escapes without partial exports
  - success_check: `python -m pytest tests/test_tdd_workspace.py::test_unsafe_snapshot_never_leaves_partial_workspace -q`
  - verifies: S4.3
  - files: `evals/tddbench/workspace.py, tests/test_tdd_workspace.py`

- [ ] T3.1 Validate generated prediction files and expose evaluation mode
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_evaluation_predictions_are_validated_and_mounted -q`
  - verifies: S3.1
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T3.2 Preserve the evaluation cohort in CLI reports
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_evaluation_cli_preserves_selection_and_denominators -q`
  - verifies: S3.2
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`

## Phase 1: External harness and frozen evaluation
### Tasks
- [ ] T1.1 Implement C-1.1
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_only_tdd_members_are_admitted -q`
  - verifies: S1.1
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.2 Implement C-1.2
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_generator_inputs_never_contain_solutions -q`
  - verifies: S1.2
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.3 Implement C-1.3
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_selection_is_frozen_distinct_and_disjoint -q`
  - verifies: S1.3
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.4 Implement C-1.4
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_missing_inputs_never_fall_back -q`
  - verifies: S1.4
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.5 Implement C-1.5
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_source_artifacts_are_fingerprinted -q`
  - verifies: S1.5
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.6 Implement C-2.1
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_harness_requires_explicit_git_authorization -q`
  - verifies: S2.1
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.7 Implement C-2.2
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_errors_skips_and_missing_reports_are_incomplete -q`
  - verifies: S2.2
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.8 Implement C-2.3
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_fail_before_requires_same_test_to_pass_after -q`
  - verifies: S2.3
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.9 Implement C-2.4
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_summary_keeps_all_denominators -q`
  - verifies: S2.4
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`
- [ ] T1.10 Implement C-2.5
  - success_check: `python -m pytest tests/test_tdd_benchmark.py::test_gold_runs_are_always_calibration -q`
  - verifies: S2.5
  - files: `evals/tddbench/adapter.py, evals/tddbench/__main__.py, tests/test_tdd_benchmark.py`

- [ ] T6.8 Require selected source origin
  - success_check: `python -m pytest tests/test_tdd_filesystem.py::test_source_layout_resolution_and_origin_boundary tests/test_tdd_execution.py::test_source_origin_error_overrides_successful_junit -q`
  - verifies: S6.8
  - files: `evals/tddbench/execution.py, evals/tddbench/fsmodel.py, evals/tddbench/generator.py, evals/tddbench/trust.py, tests/test_tdd_execution.py, tests/test_tdd_filesystem.py`

- [ ] T6.9 Expose inspected Python version
  - success_check: `python -m pytest tests/test_tdd_execution.py::test_generator_run_action_obeys_separate_test_budget_C_6_5 -q`
  - verifies: S6.9
  - files: `evals/tddbench/execution.py, evals/tddbench/fsmodel.py, evals/tddbench/generator.py, evals/tddbench/trust.py, tests/test_tdd_execution.py, tests/test_tdd_filesystem.py`

- [ ] T5.6 Validate test-only predictions in all arms
  - success_check: `python -m pytest tests/test_tdd_generator.py::test_final_patch_rejects_implementation_metadata_and_stale_hunks_C_5_6 tests/test_tdd_generator.py::test_existing_test_patch_checks_context_and_preserves_untouched_lines -q`
  - verifies: S5.6
  - files: `evals/tddbench/patches.py, evals/tddbench/generator.py, tests/test_tdd_generator.py`

- [ ] T6.10 Admit only inspected runtime kinds
  - success_check: `python -m pytest tests/test_tdd_execution.py::test_environment_runtime_is_pinned_and_bound_to_one_snapshot_C_6_1 tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 -q`
  - verifies: S6.10
  - files: `evals/tddbench/execution.py, evals/tddbench/__main__.py, tests/test_tdd_execution.py`

- [ ] T6.11 Bind public installed sources and complete inspection
  - success_check: `python -m pytest tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 -q`
  - verifies: S6.11
  - files: `evals/tddbench/execution.py, evals/tddbench/__main__.py, tests/test_tdd_execution.py`

- [ ] T6.12 Restore fingerprinted public build artifacts
  - success_check: `python -m pytest tests/test_tdd_filesystem.py::test_public_build_artifacts_restore_exact_bytes_without_replacing_source tests/test_tdd_filesystem.py::test_build_artifacts_reject_public_paths_link_traversal_and_forged_manifest tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 -q`
  - verifies: S6.12
  - files: `evals/tddbench/build_artifacts.py, evals/tddbench/execution.py, tests/test_tdd_filesystem.py, tests/test_tdd_execution.py`

- [ ] T6.13 Preserve public Unicode filenames in Python 3.6 containers
  - success_check: `python -m pytest tests/test_tdd_execution.py::test_public_installed_runtime_requires_snapshot_labels_and_complete_inspection_C_6_11 tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary -q`
  - verifies: S6.13
  - files: `evals/tddbench/execution.py, evals/tddbench/workspace.py, tests/test_tdd_execution.py`

- [ ] T6.14 Stage verified public source without host-sharing overhead
  - success_check: `python -m pytest tests/test_tdd_filesystem.py::test_installed_source_copy_hashes_only_declared_public_files tests/test_tdd_execution.py::test_test_tool_preserves_typed_results_and_container_boundary -q`
  - verifies: S6.14
  - files: `evals/tddbench/fsmodel.py, evals/tddbench/execution.py, tests/test_tdd_filesystem.py, tests/test_tdd_execution.py`

- [ ] T5.7 Export Git-compatible new test files
  - success_check: `python -m pytest tests/test_tdd_generator.py::test_final_patch_rejects_implementation_metadata_and_stale_hunks_C_5_6 tests/test_tdd_generator.py::test_existing_test_patch_checks_context_and_preserves_untouched_lines tests/test_tdd_generator.py::test_generator_reads_public_source_and_preserves_candidate_provenance -q`
  - verifies: S5.7
  - files: `evals/tddbench/native.py, evals/tddbench/patches.py, tests/test_tdd_generator.py`

- [ ] T8.7 Address recorded review interface failures
  - success_check: `python -m pytest tests/test_tdd_review_payload.py -q`
  - verifies: S8.7
  - files: `evals/tddbench/trust.py, evals/tddbench/native.py, tests/test_tdd_review_payload.py, tests/test_tdd_review_diagnostics.py`

- [ ] T8.8 Address recorded review interface failures
  - success_check: `python -m pytest tests/test_tdd_review_diagnostics.py::test_invalid_review_preserves_budget_and_diagnostic_without_execution -q`
  - verifies: S8.8
  - files: `evals/tddbench/trust.py, evals/tddbench/native.py, tests/test_tdd_review_payload.py, tests/test_tdd_review_diagnostics.py`

- [ ] T8.9 Address recorded review interface failures
  - success_check: `python -m pytest tests/test_tdd_review_diagnostics.py::test_unsupported_options_have_actionable_errors tests/test_tdd_review_diagnostics.py::test_supported_command_selection_is_unchanged tests/test_tdd_review_diagnostics.py::test_valid_review_still_requires_real_native_challenges -q`
  - verifies: S8.9
  - files: `evals/tddbench/trust.py, evals/tddbench/native.py, tests/test_tdd_review_payload.py, tests/test_tdd_review_diagnostics.py`

- [ ] T5.8 Disclose execution budgets to generation
  - success_check: `python -m pytest tests/test_tdd_generator.py::test_model_sees_remaining_budget_without_receiving_extra_calls tests/test_tdd_generator.py::test_generator_reads_public_source_and_preserves_candidate_provenance tests/test_tdd_generation_budget.py -q`
  - verifies: S5.8
  - files: `evals/tddbench/generator.py, tests/test_tdd_generator.py, tests/test_tdd_generation_budget.py`

- [ ] T8.11 Disclose reviewer resources and pending execution phase
  - success_check: `python -m pytest tests/test_tdd_review_budget.py -q`
  - verifies: S8.11
  - files: `evals/tddbench/trust.py, tests/test_tdd_review_budget.py`

- [ ] T8.10 Ask reviewers for contrastive alternatives
  - success_check: `python -m pytest tests/test_tdd_contrastive_review.py -q`
  - verifies: S8.10
  - files: `evals/tddbench/trust.py, tests/test_tdd_contrastive_review.py`

- [ ] T5.9 Preserve existing named tests
  - success_check: `python -m pytest tests/test_tdd_preservation.py -q`
  - verifies: S5.9
  - files: `evals/tddbench/test_preservation.py, evals/tddbench/native.py, evals/tddbench/execution.py, tests/test_tdd_preservation.py`
